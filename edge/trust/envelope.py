"""Gateway-side trust envelope construction: frame -> canonical event -> signed
CAN Trust Envelope (CTE), with running sequence/chain/batch state.

One GatewayState instance represents one boot session (one boot_epoch).
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric import ec

from edge.acquisition.base import CanFrame
from edge.trust import canonical, chain, cose_signer
from edge.trust.canonical import CanonicalEvent
from edge.trust.cose_signer import CoseSign1

POLICY_VERSION = 1


@dataclass(frozen=True)
class SignedEnvelope:
    """What actually gets queued/transmitted: the COSE_Sign1 CBOR bytes plus
    the plaintext fields a backend/dashboard needs for routing without
    verifying the signature first (it still MUST verify before trusting
    anything)."""

    gateway_id: str
    boot_epoch: int
    sequence: int
    batch_id: str
    event_hash: str
    """H_n = SHA-256(canonical_event_n || H_(n-1)) -- the post-chaining hash,
    i.e. what architecture doc section 6.2 calls H_n and what batch_root is
    a Merkle root over. Not a plain identity digest of the event alone."""
    cose_cbor: bytes


def new_boot_epoch() -> int:
    """Per-boot random identifier (architecture doc section 6.1)."""
    return int.from_bytes(os.urandom(4), "big")


@dataclass
class GatewayState:
    gateway_id: str
    vehicle_profile_id: str
    private_key: ec.EllipticCurvePrivateKey
    boot_epoch: int = field(default_factory=new_boot_epoch)
    sequence: int = field(default=0)
    previous_event_hash: str = field(default=chain.GENESIS_HASH)
    batch_size: int = field(default=20)
    _batch_id: str = field(default_factory=lambda: uuid.uuid4().hex, init=False)
    _batch_count: int = field(default=0, init=False)

    def _maybe_roll_batch(self) -> None:
        if self._batch_count >= self.batch_size:
            self._batch_id = uuid.uuid4().hex
            self._batch_count = 0

    def build_and_sign(self, frame: CanFrame, capture_time: float | None = None) -> SignedEnvelope:
        self._maybe_roll_batch()
        event = CanonicalEvent(
            gateway_id=self.gateway_id,
            vehicle_profile_id=self.vehicle_profile_id,
            boot_epoch=self.boot_epoch,
            sequence=self.sequence,
            capture_time=capture_time if capture_time is not None else frame.timestamp,
            can_channel=frame.channel,
            can_id=frame.can_id,
            is_extended_id=frame.is_extended_id,
            is_fd=frame.is_fd,
            dlc=frame.dlc,
            raw_payload=frame.data,
            previous_event_hash=self.previous_event_hash,
            batch_id=self._batch_id,
            policy_version=POLICY_VERSION,
        )
        event_bytes = canonical.canonical_bytes(event)
        chain_hash = chain.next_chain_hash(event_bytes, self.previous_event_hash)
        signed = cose_signer.sign(event_bytes, self.private_key)

        envelope = SignedEnvelope(
            gateway_id=self.gateway_id,
            boot_epoch=self.boot_epoch,
            sequence=self.sequence,
            batch_id=self._batch_id,
            event_hash=chain_hash,
            cose_cbor=signed.to_cbor(),
        )

        self.sequence += 1
        self.previous_event_hash = chain_hash
        self._batch_count += 1
        return envelope

    def reset_for_new_boot(self) -> None:
        self.boot_epoch = new_boot_epoch()
        self.sequence = 0
        self.previous_event_hash = chain.GENESIS_HASH
        self._batch_id = uuid.uuid4().hex
        self._batch_count = 0
