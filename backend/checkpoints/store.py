"""Backend acceptance checkpoint issuance and lookup.

After a batch is fully verified and imported, the backend issues a signed
AcceptanceCheckpoint (architecture doc section 6.4) and stores it keyed by
(gateway_id, boot_epoch). The gateway references the resulting digest on
its next batch; a mismatch is rejected as CHECKPOINT_MISMATCH.

LIMITATION (documented, not hidden): this checkpoint anchors continuity only
from the moment the backend first observes a gateway/boot session. Data
produced entirely offline before any checkpoint exists cannot be
cross-checked against an external anchor -- see docs/LIMITATIONS.md.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from edge.trust import cose_signer
from edge.trust.checkpoints import AcceptanceCheckpoint, GENESIS_CHECKPOINT_DIGEST

SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gateway_id TEXT NOT NULL,
    boot_epoch INTEGER NOT NULL,
    checkpoint_digest TEXT NOT NULL,
    highest_accepted_sequence INTEGER NOT NULL,
    accepted_batch_root TEXT NOT NULL,
    previous_checkpoint_digest TEXT NOT NULL,
    cose_cbor BLOB NOT NULL,
    backend_time REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_gw ON checkpoints (gateway_id, boot_epoch, id);
"""


class CheckpointService:
    def __init__(self, db_path: Path | str, backend_private_key: ec.EllipticCurvePrivateKey) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._key = backend_private_key

    def last_checkpoint_digest(self, gateway_id: str, boot_epoch: int) -> str:
        cur = self._conn.execute(
            """
            SELECT checkpoint_digest FROM checkpoints
            WHERE gateway_id = ? AND boot_epoch = ? ORDER BY id DESC LIMIT 1
            """,
            (gateway_id, boot_epoch),
        )
        row = cur.fetchone()
        return row[0] if row else GENESIS_CHECKPOINT_DIGEST

    def issue(
        self,
        gateway_id: str,
        boot_epoch: int,
        highest_accepted_sequence: int,
        accepted_batch_root: str,
        previous_checkpoint_digest: str,
    ) -> AcceptanceCheckpoint:
        checkpoint = AcceptanceCheckpoint(
            gateway_id=gateway_id,
            boot_epoch=boot_epoch,
            highest_accepted_sequence=highest_accepted_sequence,
            accepted_batch_root=accepted_batch_root,
            previous_checkpoint_digest=previous_checkpoint_digest,
            backend_time=time.time(),
        )
        signed = cose_signer.sign(checkpoint.canonical_bytes(), self._key)
        self._conn.execute(
            """
            INSERT INTO checkpoints
                (gateway_id, boot_epoch, checkpoint_digest, highest_accepted_sequence,
                 accepted_batch_root, previous_checkpoint_digest, cose_cbor, backend_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gateway_id,
                boot_epoch,
                checkpoint.digest(),
                highest_accepted_sequence,
                accepted_batch_root,
                previous_checkpoint_digest,
                signed.to_cbor(),
                checkpoint.backend_time,
            ),
        )
        self._conn.commit()
        return checkpoint

    def close(self) -> None:
        self._conn.close()
