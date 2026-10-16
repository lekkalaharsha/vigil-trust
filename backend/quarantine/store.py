"""Quarantine database: every rejected record is retained with an explicit
reason code for investigation/demo purposes. Nothing in quarantine is ever
promoted automatically into the trusted table."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS quarantine_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gateway_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    detail TEXT,
    raw_cbor BLOB,
    quarantined_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quarantine_reason ON quarantine_events (reason_code);
"""

VALID_REASON_CODES = frozenset(
    {
        "UNKNOWN_DEVICE",
        "DEVICE_REVOKED",
        "CERTIFICATE_INVALID",
        "SIGNATURE_INVALID",
        "SCHEMA_INVALID",
        "REPLAY",
        "DUPLICATE",
        "OUT_OF_ORDER",
        "CHAIN_MISMATCH",
        "CHECKPOINT_MISMATCH",
        "BATCH_ROOT_INVALID",
        "POLICY_REJECTED",
    }
)


class QuarantineStore:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add(self, gateway_id: str, reason_code: str, detail: str = "", raw_cbor: bytes | None = None) -> None:
        if reason_code not in VALID_REASON_CODES:
            raise ValueError(f"unknown reason code: {reason_code!r}")
        self._conn.execute(
            "INSERT INTO quarantine_events (gateway_id, reason_code, detail, raw_cbor, quarantined_at) VALUES (?, ?, ?, ?, ?)",
            (gateway_id, reason_code, detail, raw_cbor, time.time()),
        )
        self._conn.commit()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT gateway_id, reason_code, detail, quarantined_at FROM quarantine_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        columns = ["gateway_id", "reason_code", "detail", "quarantined_at"]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def reason_histogram(self) -> dict[str, int]:
        cur = self._conn.execute("SELECT reason_code, COUNT(*) FROM quarantine_events GROUP BY reason_code")
        return dict(cur.fetchall())

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM quarantine_events").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
