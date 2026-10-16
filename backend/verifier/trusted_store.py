"""Trusted telemetry database + per-(gateway, boot_epoch) continuity state.

Only events that pass every verification checkpoint in verifier.py are ever
inserted here. The UNIQUE constraint on (gateway_id, boot_epoch, sequence)
is a second, DB-enforced line of defense against duplicate/replayed
sequence numbers even if application logic has a bug.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS trusted_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gateway_id TEXT NOT NULL,
    boot_epoch INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    batch_id TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    can_id INTEGER NOT NULL,
    can_channel TEXT NOT NULL,
    capture_time REAL NOT NULL,
    accepted_at REAL NOT NULL,
    event_cbor BLOB NOT NULL,
    UNIQUE(gateway_id, boot_epoch, sequence)
);
CREATE INDEX IF NOT EXISTS idx_trusted_gw_can ON trusted_events (gateway_id, can_id, capture_time);

CREATE TABLE IF NOT EXISTS gateway_chain_state (
    gateway_id TEXT NOT NULL,
    boot_epoch INTEGER NOT NULL,
    highest_sequence INTEGER NOT NULL,
    last_event_hash TEXT NOT NULL,
    last_previous_checkpoint_digest TEXT,
    PRIMARY KEY (gateway_id, boot_epoch)
);
"""


@dataclass(frozen=True)
class ChainState:
    gateway_id: str
    boot_epoch: int
    highest_sequence: int
    last_event_hash: str
    last_previous_checkpoint_digest: str | None


class TrustedStore:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def chain_state(self, gateway_id: str, boot_epoch: int) -> ChainState | None:
        cur = self._conn.execute(
            """
            SELECT gateway_id, boot_epoch, highest_sequence, last_event_hash, last_previous_checkpoint_digest
            FROM gateway_chain_state WHERE gateway_id = ? AND boot_epoch = ?
            """,
            (gateway_id, boot_epoch),
        )
        row = cur.fetchone()
        return ChainState(*row) if row else None

    def sequence_already_seen(self, gateway_id: str, boot_epoch: int, sequence: int) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM trusted_events WHERE gateway_id = ? AND boot_epoch = ? AND sequence = ?",
            (gateway_id, boot_epoch, sequence),
        )
        return cur.fetchone() is not None

    def event_hash_already_seen(self, event_hash: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM trusted_events WHERE event_hash = ?", (event_hash,))
        return cur.fetchone() is not None

    def insert_event(
        self,
        gateway_id: str,
        boot_epoch: int,
        sequence: int,
        batch_id: str,
        event_hash: str,
        can_id: int,
        can_channel: str,
        capture_time: float,
        event_cbor: bytes,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO trusted_events
                (gateway_id, boot_epoch, sequence, batch_id, event_hash, can_id, can_channel, capture_time, accepted_at, event_cbor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (gateway_id, boot_epoch, sequence, batch_id, event_hash, can_id, can_channel, capture_time, time.time(), event_cbor),
        )
        self._conn.commit()

    def update_chain_state(
        self,
        gateway_id: str,
        boot_epoch: int,
        highest_sequence: int,
        last_event_hash: str,
        last_previous_checkpoint_digest: str | None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO gateway_chain_state (gateway_id, boot_epoch, highest_sequence, last_event_hash, last_previous_checkpoint_digest)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(gateway_id, boot_epoch) DO UPDATE SET
                highest_sequence = excluded.highest_sequence,
                last_event_hash = excluded.last_event_hash,
                last_previous_checkpoint_digest = excluded.last_previous_checkpoint_digest
            """,
            (gateway_id, boot_epoch, highest_sequence, last_event_hash, last_previous_checkpoint_digest),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 100, gateway_id: str | None = None) -> list[dict[str, Any]]:
        if gateway_id:
            cur = self._conn.execute(
                """
                SELECT gateway_id, boot_epoch, sequence, can_id, can_channel, capture_time, accepted_at, event_hash
                FROM trusted_events WHERE gateway_id = ? ORDER BY id DESC LIMIT ?
                """,
                (gateway_id, limit),
            )
        else:
            cur = self._conn.execute(
                """
                SELECT gateway_id, boot_epoch, sequence, can_id, can_channel, capture_time, accepted_at, event_hash
                FROM trusted_events ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
        columns = ["gateway_id", "boot_epoch", "sequence", "can_id", "can_channel", "capture_time", "accepted_at", "event_hash"]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM trusted_events").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
