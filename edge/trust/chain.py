"""Previous-event hash chaining.

H_n = SHA-256(canonical_event_n || H_(n-1))  (architecture doc section 6.2)

This provides order-sensitive tamper evidence for events produced by one
gateway within one boot session. It does NOT by itself defend against an
attacker who controls the entire buffered segment before it is ever observed
by the backend (truncation attack) -- see docs/THREAT_MODEL.md and
docs/LIMITATIONS.md.
"""

from __future__ import annotations

import hashlib

GENESIS_HASH = "0" * 64


def next_chain_hash(canonical_event_bytes: bytes, previous_event_hash: str) -> str:
    if len(previous_event_hash) != 64:
        raise ValueError("previous_event_hash must be a 64-hex-char sha256 digest")
    previous_bytes = bytes.fromhex(previous_event_hash)
    return hashlib.sha256(canonical_event_bytes + previous_bytes).hexdigest()


def verify_chain_link(canonical_event_bytes: bytes, previous_event_hash: str, claimed_hash: str) -> bool:
    return next_chain_hash(canonical_event_bytes, previous_event_hash) == claimed_hash
