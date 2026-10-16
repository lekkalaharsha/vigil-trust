"""Backend configuration from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendConfig:
    host: str = os.environ.get("VIGIL_BACKEND_HOST", "127.0.0.1")
    port: int = int(os.environ.get("VIGIL_BACKEND_PORT", "8443"))
    data_dir: str = os.environ.get("VIGIL_BACKEND_DATA_DIR", "data/backend")
    checkpoint_key_path: str = os.environ.get(
        "VIGIL_BACKEND_CHECKPOINT_KEY", "certs/backend_signing/checkpoint.key"
    )

    @property
    def registry_db_path(self) -> str:
        return f"{self.data_dir}/registry.db"

    @property
    def trusted_db_path(self) -> str:
        return f"{self.data_dir}/trusted.db"

    @property
    def quarantine_db_path(self) -> str:
        return f"{self.data_dir}/quarantine.db"

    @property
    def checkpoints_db_path(self) -> str:
        return f"{self.data_dir}/checkpoints.db"


def load_backend_config() -> BackendConfig:
    return BackendConfig()
