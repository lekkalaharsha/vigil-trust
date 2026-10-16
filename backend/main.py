"""Backend entrypoint: wires storage + verifier into the FastAPI app and
serves it with uvicorn.

    .venv/Scripts/python.exe -m backend.main
"""

from __future__ import annotations

import sys

import uvicorn
from cryptography.hazmat.primitives.asymmetric import ec

from backend.api.app import create_app
from backend.checkpoints.store import CheckpointService
from backend.config import load_backend_config
from backend.device_registry.registry import DeviceRegistry
from backend.quarantine.store import QuarantineStore
from backend.verifier.trusted_store import TrustedStore
from edge.trust.identity import load_identity_from_files


def build_app():
    config = load_backend_config()
    registry = DeviceRegistry(config.registry_db_path)
    trusted_store = TrustedStore(config.trusted_db_path)
    quarantine = QuarantineStore(config.quarantine_db_path)

    identity = load_identity_from_files(config.checkpoint_key_path)
    assert isinstance(identity.private_key, ec.EllipticCurvePrivateKey)
    checkpoints = CheckpointService(config.checkpoints_db_path, identity.private_key)

    return create_app(registry, trusted_store, quarantine, checkpoints), config


def main() -> int:
    try:
        app, config = build_app()
    except FileNotFoundError as exc:
        print(
            "[backend] missing required key material: "
            f"{exc}\nRun: .venv/Scripts/python.exe scripts/generate_backend_key.py",
            file=sys.stderr,
        )
        return 1
    uvicorn.run(app, host=config.host, port=config.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
