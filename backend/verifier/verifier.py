"""Core backend verification pipeline.

Order of checks per docs/PROTOCOL.md (mirrors CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST
"Required rejection reason codes" and VIGIL_TRUST_Research_and_Architecture.md
section 6.6):

  1. Device lookup -> UNKNOWN_DEVICE
  2. Device status -> DEVICE_REVOKED
  3. Batch commitment signature -> SIGNATURE_INVALID (whole batch)
  4. Per event: COSE parse -> SCHEMA_INVALID
  5. Per event: signature -> SIGNATURE_INVALID
  6. Per event: canonical schema -> SCHEMA_INVALID
  7. Per event: sequence vs chain state -> REPLAY / DUPLICATE / OUT_OF_ORDER
  8. Per event: previous_event_hash vs chain state -> CHAIN_MISMATCH
  9. Batch: recomputed Merkle root vs declared -> BATCH_ROOT_INVALID (whole batch)
  10. Batch: previous_checkpoint_digest vs backend record -> CHECKPOINT_MISMATCH (whole batch)

Unverified telemetry is never written to TrustedStore; every rejection is
written to QuarantineStore with one of the reason codes above.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from edge.trust import canonical, chain, cose_signer, merkle
from edge.trust.cose_signer import CoseSign1, SignatureError

from backend.checkpoints.store import CheckpointService
from backend.device_registry.registry import REVOKED, DeviceRegistry
from backend.quarantine.store import QuarantineStore
from backend.verifier.trusted_store import TrustedStore


@dataclass
class VerifiedBatch:
    accepted_event_hashes: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    new_checkpoint_digest: str | None = None


class BatchLevelRejection(Exception):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class Verifier:
    def __init__(
        self,
        registry: DeviceRegistry,
        trusted_store: TrustedStore,
        quarantine: QuarantineStore,
        checkpoints: CheckpointService,
    ) -> None:
        self._registry = registry
        self._trusted = trusted_store
        self._quarantine = quarantine
        self._checkpoints = checkpoints

    def verify_batch(self, gateway_id: str, cose_messages: list[bytes], batch_commitment_cbor: bytes) -> VerifiedBatch:
        device = self._registry.get(gateway_id)
        if device is None:
            for raw in cose_messages:
                self._quarantine.add(gateway_id, "UNKNOWN_DEVICE", raw_cbor=raw)
            return VerifiedBatch(rejected={f"unindexed-{i}": "UNKNOWN_DEVICE" for i in range(len(cose_messages))})

        if device.status == REVOKED:
            for raw in cose_messages:
                self._quarantine.add(gateway_id, "DEVICE_REVOKED", raw_cbor=raw)
            return VerifiedBatch(rejected={f"unindexed-{i}": "DEVICE_REVOKED" for i in range(len(cose_messages))})

        public_key = device.public_key

        try:
            commitment = self._parse_and_verify_commitment(batch_commitment_cbor, public_key)
        except BatchLevelRejection as exc:
            for raw in cose_messages:
                self._quarantine.add(gateway_id, exc.reason_code, detail=exc.detail, raw_cbor=raw)
            return VerifiedBatch(rejected={f"unindexed-{i}": exc.reason_code for i in range(len(cose_messages))})

        boot_epoch = commitment["boot_epoch"]
        chain_state = self._trusted.chain_state(gateway_id, boot_epoch)
        pending_last_hash = chain_state.last_event_hash if chain_state else chain.GENESIS_HASH
        pending_highest_sequence = chain_state.highest_sequence if chain_state else -1

        result = VerifiedBatch()
        accepted_rows: list[dict] = []
        seen_in_batch: set[str] = set()

        for raw in cose_messages:
            event_hash, reason, row = self._verify_one_event(
                raw, public_key, pending_last_hash, pending_highest_sequence, seen_in_batch, self._trusted
            )
            if reason is not None:
                self._quarantine.add(gateway_id, reason, raw_cbor=raw)
                result.rejected[event_hash or f"unindexed-{len(result.rejected)}"] = reason
                continue
            accepted_rows.append(row)
            seen_in_batch.add(event_hash)
            result.accepted_event_hashes.append(event_hash)
            pending_last_hash = event_hash
            pending_highest_sequence = row["sequence"]

        if not accepted_rows:
            return result

        recomputed_root = merkle.build_merkle_root([row["event_hash"] for row in accepted_rows])
        if recomputed_root != commitment["batch_root"]:
            for row in accepted_rows:
                self._quarantine.add(gateway_id, "BATCH_ROOT_INVALID", raw_cbor=row["raw"])
            return VerifiedBatch(
                rejected={**result.rejected, **{row["event_hash"]: "BATCH_ROOT_INVALID" for row in accepted_rows}}
            )

        expected_previous_checkpoint = self._checkpoints.last_checkpoint_digest(gateway_id, boot_epoch)
        if commitment["previous_checkpoint_digest"] != expected_previous_checkpoint:
            for row in accepted_rows:
                self._quarantine.add(gateway_id, "CHECKPOINT_MISMATCH", raw_cbor=row["raw"])
            return VerifiedBatch(
                rejected={**result.rejected, **{row["event_hash"]: "CHECKPOINT_MISMATCH" for row in accepted_rows}}
            )

        for row in accepted_rows:
            self._trusted.insert_event(
                gateway_id=gateway_id,
                boot_epoch=boot_epoch,
                sequence=row["sequence"],
                batch_id=row["batch_id"],
                event_hash=row["event_hash"],
                can_id=row["can_id"],
                can_channel=row["can_channel"],
                capture_time=row["capture_time"],
                event_cbor=row["event_bytes"],
            )

        final_hash = accepted_rows[-1]["event_hash"]
        final_sequence = accepted_rows[-1]["sequence"]
        self._trusted.update_chain_state(
            gateway_id, boot_epoch, final_sequence, final_hash, commitment["previous_checkpoint_digest"]
        )
        new_checkpoint = self._checkpoints.issue(
            gateway_id=gateway_id,
            boot_epoch=boot_epoch,
            highest_accepted_sequence=final_sequence,
            accepted_batch_root=recomputed_root,
            previous_checkpoint_digest=commitment["previous_checkpoint_digest"],
        )
        result.new_checkpoint_digest = new_checkpoint.digest()
        return result

    @staticmethod
    def _parse_and_verify_commitment(batch_commitment_cbor: bytes, public_key) -> dict:
        try:
            cose_message = CoseSign1.from_cbor(batch_commitment_cbor)
        except SignatureError as exc:
            raise BatchLevelRejection("SCHEMA_INVALID", str(exc)) from exc
        if not cose_signer.verify(cose_message, public_key):
            raise BatchLevelRejection("SIGNATURE_INVALID", "batch commitment signature invalid")
        import cbor2

        try:
            commitment = cbor2.loads(cose_message.payload)
        except Exception as exc:  # noqa: BLE001 - untrusted input
            raise BatchLevelRejection("SCHEMA_INVALID", f"malformed batch commitment: {exc}") from exc
        required = {
            "gateway_id",
            "boot_epoch",
            "first_sequence",
            "last_sequence",
            "previous_checkpoint_digest",
            "batch_root",
        }
        missing = required - commitment.keys()
        if missing:
            raise BatchLevelRejection("SCHEMA_INVALID", f"batch commitment missing fields: {missing}")
        return commitment

    @staticmethod
    def _verify_one_event(
        raw: bytes,
        public_key,
        pending_last_hash: str,
        pending_highest_sequence: int,
        seen_in_batch: set[str],
        trusted_store: TrustedStore,
    ) -> tuple[str | None, str | None, dict | None]:
        try:
            cose_message = CoseSign1.from_cbor(raw)
        except SignatureError:
            return None, "SCHEMA_INVALID", None

        if not cose_signer.verify(cose_message, public_key):
            return None, "SIGNATURE_INVALID", None

        try:
            decoded = canonical.decode_canonical(cose_message.payload)
        except Exception:  # noqa: BLE001 - untrusted input
            return None, "SCHEMA_INVALID", None

        missing = [f for f in canonical.REQUIRED_FIELDS if f not in decoded]
        if missing or not ("raw_payload" in decoded or "raw_payload_digest" in decoded):
            return None, "SCHEMA_INVALID", None

        sequence = decoded["sequence"]
        event_hash = chain.next_chain_hash(cose_message.payload, decoded["previous_event_hash"])

        # Replay-cache style checks come before chain/order checks: a
        # resent historical record is rejected as DUPLICATE/REPLAY
        # regardless of whether the chain state has since moved on.
        if event_hash in seen_in_batch:
            return event_hash, "DUPLICATE", None
        if trusted_store.event_hash_already_seen(event_hash):
            return event_hash, "REPLAY", None
        if sequence <= pending_highest_sequence:
            # Stale sequence number with content that does not match what was
            # originally accepted at that position.
            return event_hash, "REPLAY", None

        if decoded["previous_event_hash"] != pending_last_hash:
            return event_hash, "CHAIN_MISMATCH", None

        if sequence != pending_highest_sequence + 1:
            return event_hash, "OUT_OF_ORDER", None

        row = {
            "raw": raw,
            "event_bytes": cose_message.payload,
            "event_hash": event_hash,
            "sequence": sequence,
            "batch_id": decoded["batch_id"],
            "can_id": decoded["can_id"],
            "can_channel": decoded["can_channel"],
            "capture_time": decoded["capture_time"],
        }
        return event_hash, None, row
