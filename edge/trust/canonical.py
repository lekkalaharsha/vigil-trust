"""Canonical CAN Trust Envelope (CTE) event schema and deterministic serialization.

The event schema matches docs/PROTOCOL.md and
VIGIL_TRUST_Research_and_Architecture.md section 6.1. Canonical serialization
uses RFC 8949 "core deterministic encoding" via cbor2(canonical=True), which
sorts map keys by the bytewise encoding of the key and uses the shortest
integer/float encodings. The same logical event always produces the same
bytes and the same SHA-256 digest; this is covered by
tests/unit/test_canonical.py.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any

import cbor2

SCHEMA_VERSION = 1

REQUIRED_FIELDS = (
    "version",
    "vehicle_profile_id",
    "gateway_id",
    "boot_epoch",
    "sequence",
    "capture_time",
    "can_channel",
    "can_id",
    "is_extended_id",
    "is_fd",
    "dlc",
    "previous_event_hash",
    "batch_id",
    "policy_version",
)


class CanonicalEventError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalEvent:
    """In-memory representation of one CAN Trust Envelope event.

    Exactly one of raw_payload / raw_payload_digest must be present, matching
    the data model in the architecture doc ("raw_payload OR
    raw_payload_digest").
    """

    gateway_id: str
    vehicle_profile_id: str
    boot_epoch: int
    sequence: int
    capture_time: float
    can_channel: str
    can_id: int
    is_extended_id: bool
    is_fd: bool
    dlc: int
    previous_event_hash: str
    batch_id: str
    policy_version: int
    raw_payload: bytes | None = None
    raw_payload_digest: str | None = None
    decoded_signals: dict[str, Any] | None = None
    version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (self.raw_payload is None) == (self.raw_payload_digest is None):
            raise CanonicalEventError(
                "exactly one of raw_payload or raw_payload_digest must be set"
            )
        if self.dlc < 0 or self.dlc > 64:
            raise CanonicalEventError(f"invalid dlc: {self.dlc}")
        if self.can_id < 0:
            raise CanonicalEventError(f"invalid can_id: {self.can_id}")
        if self.sequence < 0:
            raise CanonicalEventError(f"invalid sequence: {self.sequence}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["raw_payload"] is None:
            d.pop("raw_payload")
        else:
            d.pop("raw_payload_digest")
        if d["decoded_signals"] is None:
            d.pop("decoded_signals")
        return d

    @staticmethod
    def payload_digest(raw_payload: bytes) -> str:
        return hashlib.sha256(raw_payload).hexdigest()


def canonical_bytes(event: dict[str, Any] | CanonicalEvent) -> bytes:
    """Deterministic CBOR encoding of an event. Same logical event -> same bytes."""
    data = event.to_dict() if isinstance(event, CanonicalEvent) else dict(event)
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise CanonicalEventError(f"missing required fields: {missing}")
    return cbor2.dumps(data, canonical=True)


def event_digest(event: dict[str, Any] | CanonicalEvent) -> bytes:
    """SHA-256 digest of the canonical CBOR encoding."""
    return hashlib.sha256(canonical_bytes(event)).digest()


def event_digest_hex(event: dict[str, Any] | CanonicalEvent) -> str:
    return event_digest(event).hex()


def decode_canonical(data: bytes) -> dict[str, Any]:
    return cbor2.loads(data)
