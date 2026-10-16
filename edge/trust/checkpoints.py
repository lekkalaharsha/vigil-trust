"""Batch commitments and backend acceptance checkpoints.

Architecture doc sections 6.3/6.4. A batch commitment is produced and signed
by the gateway (same ECDSA P-256 device key as individual events, via
cose_signer). A backend acceptance checkpoint is produced and signed by the
backend's demo checkpoint key after it has verified a batch. The gateway
stores the last accepted checkpoint and references it on the next upload;
the backend rejects a batch whose declared previous_checkpoint_digest does
not match what it last issued for that gateway/boot_epoch.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import cbor2


@dataclass(frozen=True)
class BatchCommitment:
    gateway_id: str
    boot_epoch: int
    first_sequence: int
    last_sequence: int
    previous_checkpoint_digest: str
    batch_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "boot_epoch": self.boot_epoch,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "previous_checkpoint_digest": self.previous_checkpoint_digest,
            "batch_root": self.batch_root,
        }

    def canonical_bytes(self) -> bytes:
        return cbor2.dumps(self.to_dict(), canonical=True)


@dataclass(frozen=True)
class AcceptanceCheckpoint:
    gateway_id: str
    boot_epoch: int
    highest_accepted_sequence: int
    accepted_batch_root: str
    previous_checkpoint_digest: str
    backend_time: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "boot_epoch": self.boot_epoch,
            "highest_accepted_sequence": self.highest_accepted_sequence,
            "accepted_batch_root": self.accepted_batch_root,
            "previous_checkpoint_digest": self.previous_checkpoint_digest,
            "backend_time": self.backend_time,
        }

    def canonical_bytes(self) -> bytes:
        return cbor2.dumps(self.to_dict(), canonical=True)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


GENESIS_CHECKPOINT_DIGEST = "0" * 64
