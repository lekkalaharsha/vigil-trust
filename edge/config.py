"""Edge configuration from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeConfig:
    gateway_id: str = os.environ.get("VIGIL_GATEWAY_ID", "gw-demo-01")
    vehicle_profile_id: str = os.environ.get("VIGIL_VEHICLE_PROFILE_ID", "demo-v1")
    acquisition_mode: str = os.environ.get("VIGIL_ACQUISITION_MODE", "simulator")
    replay_log_path: str = os.environ.get("VIGIL_REPLAY_LOG", "data/synthetic_can.log")
    device_key_path: str = os.environ.get(
        "VIGIL_DEVICE_KEY_PATH", "certs/devices/gw-demo-01.key"
    )
    backend_url: str = os.environ.get("VIGIL_BACKEND_URL", "http://127.0.0.1:8443")
    data_dir: str = os.environ.get("VIGIL_EDGE_DATA_DIR", "data/edge")
    batch_size: int = int(os.environ.get("VIGIL_BATCH_SIZE", "20"))
    drain_interval_s: float = float(os.environ.get("VIGIL_DRAIN_INTERVAL_S", "1.0"))

    @property
    def queue_db_path(self) -> str:
        return f"{self.data_dir}/queue.db"

    @property
    def checkpoint_db_path(self) -> str:
        return f"{self.data_dir}/checkpoint.db"


def load_edge_config() -> EdgeConfig:
    return EdgeConfig()
