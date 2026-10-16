"""Device registry: gateway identity -> public key + trust state.

A device is only ever enrolled here by an operator (scripts/dev_pki.py for
the demo, or a future admin API) -- the backend never auto-trusts a device
it has not seen in this table.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

TRUSTED = "trusted"
REVOKED = "revoked"

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    vehicle_profile_id TEXT NOT NULL,
    public_key_pem TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('trusted', 'revoked')),
    registered_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    vehicle_profile_id: str
    public_key_pem: str
    status: str
    registered_at: float
    updated_at: float

    @property
    def public_key(self) -> ec.EllipticCurvePublicKey:
        key = serialization.load_pem_public_key(self.public_key_pem.encode("ascii"))
        if not isinstance(key, ec.EllipticCurvePublicKey):
            raise ValueError(f"device {self.device_id} public key is not an EC key")
        return key


class DeviceRegistry:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def register(self, device_id: str, vehicle_profile_id: str, public_key_pem: str, status: str = TRUSTED) -> None:
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO devices (device_id, vehicle_profile_id, public_key_pem, status, registered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                vehicle_profile_id = excluded.vehicle_profile_id,
                public_key_pem = excluded.public_key_pem,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (device_id, vehicle_profile_id, public_key_pem, status, now, now),
        )
        self._conn.commit()

    def set_status(self, device_id: str, status: str) -> None:
        if status not in (TRUSTED, REVOKED):
            raise ValueError(f"invalid status {status!r}")
        self._conn.execute(
            "UPDATE devices SET status = ?, updated_at = ? WHERE device_id = ?",
            (status, time.time(), device_id),
        )
        self._conn.commit()

    def get(self, device_id: str) -> DeviceRecord | None:
        cur = self._conn.execute(
            "SELECT device_id, vehicle_profile_id, public_key_pem, status, registered_at, updated_at "
            "FROM devices WHERE device_id = ?",
            (device_id,),
        )
        row = cur.fetchone()
        return DeviceRecord(*row) if row else None

    def list_all(self) -> list[DeviceRecord]:
        cur = self._conn.execute(
            "SELECT device_id, vehicle_profile_id, public_key_pem, status, registered_at, updated_at FROM devices"
        )
        return [DeviceRecord(*row) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
