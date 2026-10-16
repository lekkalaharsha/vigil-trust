"""Drains the durable queue in batch_id order, builds a signed batch
commitment per batch, and submits it over the configured transport. Also
owns the store-and-forward behavior: if the transport raises TransportError
(network down), draining stops and the queue keeps growing until the next
drain attempt succeeds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import ec

from edge.queue.checkpoint_store import CheckpointStore
from edge.queue.sqlite_queue import SqliteQueue
from edge.trust import cose_signer, merkle
from edge.trust.checkpoints import BatchCommitment
from edge.transport.base import Transport, TransportError

logger = logging.getLogger("vigil.edge.pipeline")


@dataclass
class DrainResult:
    attempted: int
    accepted: int
    rejected: int
    transport_error: str | None = None


class Drainer:
    def __init__(
        self,
        gateway_id: str,
        queue: SqliteQueue,
        checkpoint_store: CheckpointStore,
        transport: Transport,
        private_key: ec.EllipticCurvePrivateKey,
        batch_limit: int = 50,
    ) -> None:
        self._gateway_id = gateway_id
        self._queue = queue
        self._checkpoints = checkpoint_store
        self._transport = transport
        self._key = private_key
        self._batch_limit = batch_limit

    def drain_once(self) -> DrainResult:
        items = self._queue.pending(limit=self._batch_limit)
        if not items:
            return DrainResult(attempted=0, accepted=0, rejected=0)

        # Submit only the contiguous prefix sharing one batch_id so the
        # commitment's first/last sequence always matches what was sent.
        first_batch_id = items[0].envelope.batch_id
        batch_items = []
        for item in items:
            if item.envelope.batch_id != first_batch_id:
                break
            batch_items.append(item)

        boot_epoch = batch_items[0].envelope.boot_epoch
        first_sequence = batch_items[0].envelope.sequence
        last_sequence = batch_items[-1].envelope.sequence
        event_hashes = [item.envelope.event_hash for item in batch_items]
        batch_root = merkle.build_merkle_root(event_hashes)
        previous_checkpoint_digest = self._checkpoints.get(self._gateway_id)

        commitment = BatchCommitment(
            gateway_id=self._gateway_id,
            boot_epoch=boot_epoch,
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            previous_checkpoint_digest=previous_checkpoint_digest,
            batch_root=batch_root,
        )
        signed_commitment = cose_signer.sign(commitment.canonical_bytes(), self._key)

        try:
            result = self._transport.submit_batch(
                gateway_id=self._gateway_id,
                cose_messages=[item.envelope.cose_cbor for item in batch_items],
                batch_commitment_cbor=signed_commitment.to_cbor(),
            )
        except TransportError as exc:
            logger.warning("drain failed, queue depth=%d: %s", self._queue.depth(), exc)
            return DrainResult(attempted=len(batch_items), accepted=0, rejected=0, transport_error=str(exc))

        accepted_ids = [
            item.id for item in batch_items if item.envelope.event_hash in result.accepted_event_hashes
        ]
        self._queue.mark_sent(accepted_ids)
        if result.new_checkpoint_digest:
            self._checkpoints.set(self._gateway_id, result.new_checkpoint_digest)

        if result.rejected:
            # Rejected-but-acknowledged events are still removed from the
            # local queue (the backend has made a final decision and
            # quarantined them); they are not silently retried forever.
            rejected_hashes = set(result.rejected.keys())
            rejected_ids = [item.id for item in batch_items if item.envelope.event_hash in rejected_hashes]
            self._queue.mark_sent(rejected_ids)

        return DrainResult(
            attempted=len(batch_items),
            accepted=len(result.accepted_event_hashes),
            rejected=len(result.rejected),
        )
