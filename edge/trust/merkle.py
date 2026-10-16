"""Deterministic Merkle tree over an ordered list of event hashes.

Leaf hashes are domain-separated (0x00 prefix) and internal nodes are
domain-separated (0x01 prefix) to prevent second-preimage / leaf-as-node
confusion attacks (CVE-class issue common to naive Merkle implementations).
An odd node at any level is promoted unchanged (duplicate-free design) to
avoid the classic "duplicate last leaf" forgery.
"""

from __future__ import annotations

import hashlib

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


class MerkleError(ValueError):
    pass


def _leaf_hash(event_hash_hex: str) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + bytes.fromhex(event_hash_hex)).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def build_merkle_root(ordered_event_hashes_hex: list[str]) -> str:
    if not ordered_event_hashes_hex:
        raise MerkleError("cannot build a Merkle root over an empty batch")
    level = [_leaf_hash(h) for h in ordered_event_hashes_hex]
    while len(level) > 1:
        next_level = []
        i = 0
        while i < len(level):
            if i + 1 < len(level):
                next_level.append(_node_hash(level[i], level[i + 1]))
            else:
                next_level.append(level[i])
            i += 2
        level = next_level
    return level[0].hex()
