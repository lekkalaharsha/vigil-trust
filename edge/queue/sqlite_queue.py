"""Durable store-and-forward queue for signed envelopes.

Backed by SQLite so the gateway survives process restart without losing
buffered (not-yet-acknowledged) telemetry. Entries are appended in capture
order and always drained in that same order (sequence is monotonic per
boot_epoch so FIFO drain preserves chain/sequence validity).
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from edge.trust.envelope import SignedEnvelope

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gateway_id TEXT NOT NULL,
    boot_epoch INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    batch_id TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    cose_cbor BLOB NOT NULL,
    enqueued_at REAL NOT NULL,
    sent_at REAL,
    UNIQUE(gateway_id, boot_epoch, sequence)
);
CREATE INDEX IF NOT EXISTS idx_queue_pending ON queue (sent_at, id);
"""


@dataclass(frozen=True)
class QueuedItem:
    id: int
    envelope: SignedEnvelope


class SqliteQueue:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def enqueue(self, envelope: SignedEnvelope) -> int:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """
                INSERT INTO queue (gateway_id, boot_epoch, sequence, batch_id, event_hash, cose_cbor, enqueued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.gateway_id,
                    envelope.boot_epoch,
                    envelope.sequence,
                    envelope.batch_id,
                    envelope.event_hash,
                    envelope.cose_cbor,
                    time.time(),
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def pending(self, limit: int = 100) -> list[QueuedItem]:
        cur = self._conn.execute(
            """
            SELECT id, gateway_id, boot_epoch, sequence, batch_id, event_hash, cose_cbor
            FROM queue WHERE sent_at IS NULL ORDER BY id ASC LIMIT ?
            """,
            (limit,),
        )
        items = []
        for row in cur.fetchall():
            row_id, gateway_id, boot_epoch, sequence, batch_id, event_hash, cose_cbor = row
            envelope = SignedEnvelope(
                gateway_id=gateway_id,
                boot_epoch=boot_epoch,
                sequence=sequence,
                batch_id=batch_id,
                event_hash=event_hash,
                cose_cbor=cose_cbor,
            )
            items.append(QueuedItem(id=row_id, envelope=envelope))
        return items

    def mark_sent(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._conn.execute(
            f"UPDATE queue SET sent_at = ? WHERE id IN ({placeholders})",
            (time.time(), *ids),
        )
        self._conn.commit()

    def depth(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM queue WHERE sent_at IS NULL")
        return cur.fetchone()[0]

    def total_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM queue")
        return cur.fetchone()[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SqliteQueue":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
