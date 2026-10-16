"""Persists the last backend-issued acceptance checkpoint digest the gateway
has seen, so the first upload after a reconnect can reference it (architecture
doc section 6.4)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from edge.trust.checkpoints import GENESIS_CHECKPOINT_DIGEST

SCHEMA = """
CREATE TABLE IF NOT EXISTS last_checkpoint (
    gateway_id TEXT PRIMARY KEY,
    checkpoint_digest TEXT NOT NULL
);
"""


class CheckpointStore:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def get(self, gateway_id: str) -> str:
        cur = self._conn.execute(
            "SELECT checkpoint_digest FROM last_checkpoint WHERE gateway_id = ?", (gateway_id,)
        )
        row = cur.fetchone()
        return row[0] if row else GENESIS_CHECKPOINT_DIGEST

    def set(self, gateway_id: str, checkpoint_digest: str) -> None:
        self._conn.execute(
            """
            INSERT INTO last_checkpoint (gateway_id, checkpoint_digest) VALUES (?, ?)
            ON CONFLICT(gateway_id) DO UPDATE SET checkpoint_digest = excluded.checkpoint_digest
            """,
            (gateway_id, checkpoint_digest),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
