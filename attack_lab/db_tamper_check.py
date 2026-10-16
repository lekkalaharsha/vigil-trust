#!/usr/bin/env python
"""Attack/utility 10: backend database copy tamper-verification.

Independently re-walks the hash chain stored in a trusted_events table (a
live DB or an offline COPY of one) and confirms that each row's event_hash
equals SHA-256(stored_event_cbor || previous_row's event_hash), per
gateway/boot_epoch, in sequence order. This re-derives the architecture
doc's H_n chain directly from storage rather than trusting the event_hash
column at face value, so if a stored event_cbor blob is modified in place
(e.g. a tampered copy of the SQLite file), every subsequent row's recomputed
hash stops matching from that point forward.

LIMITATION: this detects tampering with ROWS ALREADY IN THE DATABASE. It
cannot detect that an entire suffix of the chain was deleted outright and
replaced with a self-consistent forged chain, unless that chain is also
compared against an externally anchored AcceptanceCheckpoint (see
edge/trust/checkpoints.py and docs/LIMITATIONS.md).

Usage:
    python -m attack_lab.db_tamper_check path/to/trusted.db
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from edge.trust import chain


def check_db(db_path: Path) -> tuple[bool, list[str]]:
    conn = sqlite3.connect(db_path)
    problems: list[str] = []
    gateways = conn.execute("SELECT DISTINCT gateway_id, boot_epoch FROM trusted_events").fetchall()
    for gateway_id, boot_epoch in gateways:
        rows = conn.execute(
            """
            SELECT sequence, event_hash, event_cbor FROM trusted_events
            WHERE gateway_id = ? AND boot_epoch = ? ORDER BY sequence ASC
            """,
            (gateway_id, boot_epoch),
        ).fetchall()
        previous_hash = chain.GENESIS_HASH
        for sequence, event_hash, event_cbor in rows:
            recomputed = chain.next_chain_hash(bytes(event_cbor), previous_hash)
            if recomputed != event_hash:
                problems.append(
                    f"gateway={gateway_id} boot_epoch={boot_epoch} sequence={sequence}: "
                    f"stored event_hash={event_hash} does not match recomputed={recomputed} "
                    "-- row content or chain has been altered"
                )
            previous_hash = event_hash  # continue walking using the DB's claimed value,
            # so a single corrupted row is reported precisely instead of cascading
            # false positives across the rest of the (possibly untouched) chain.
    conn.close()
    return (len(problems) == 0, problems)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m attack_lab.db_tamper_check <path-to-trusted.db>", file=sys.stderr)
        return 2
    ok, problems = check_db(Path(argv[0]))
    if ok:
        print("[PASS] db_tamper_check: chain is self-consistent, no tampering detected")
        return 0
    print(f"[FAIL] db_tamper_check: {len(problems)} chain inconsistency(ies) detected")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
