"""Shared integration-test harness: a fully wired in-memory backend (FastAPI
app served over an ASGI transport, no real socket/port needed) plus a
matching edge GatewayState for one registered demo device.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.checkpoints.store import CheckpointService
from backend.device_registry.registry import TRUSTED, DeviceRegistry
from backend.quarantine.store import QuarantineStore
from backend.verifier.trusted_store import TrustedStore
from edge.pipeline import Drainer
from edge.queue.checkpoint_store import CheckpointStore
from edge.queue.sqlite_queue import SqliteQueue
from edge.transport.https import HttpsTransport
from edge.trust.envelope import GatewayState
from edge.trust.identity import device_id_from_public_key, generate_keypair


@dataclass
class Harness:
    gateway_id: str
    gateway_state: GatewayState
    queue: SqliteQueue
    checkpoint_store: CheckpointStore
    transport: HttpsTransport
    drainer: Drainer
    registry: DeviceRegistry
    trusted_store: TrustedStore
    quarantine: QuarantineStore
    checkpoints: CheckpointService
    http_client: TestClient

    def drain(self):
        return self.drainer.drain_once()

    def drain_all(self) -> list:
        """Drains every pending batch_id in order (drain_once only submits
        one batch at a time, matching the real edge main loop)."""
        results = []
        while self.queue.depth() > 0:
            result = self.drainer.drain_once()
            results.append(result)
            if result.transport_error or result.attempted == 0:
                break
        return results

    def close(self) -> None:
        self.http_client.close()
        self.queue.close()
        self.registry.close()
        self.trusted_store.close()
        self.quarantine.close()


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    device_key = generate_keypair()
    device_id = device_id_from_public_key(device_key.public_key())
    public_key_pem = device_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    registry = DeviceRegistry(tmp_path / "registry.db")
    registry.register(device_id, "demo-v1", public_key_pem, status=TRUSTED)

    trusted_store = TrustedStore(tmp_path / "trusted.db")
    quarantine = QuarantineStore(tmp_path / "quarantine.db")

    backend_key = generate_keypair()
    checkpoints = CheckpointService(tmp_path / "checkpoints.db", backend_key)

    app = create_app(registry, trusted_store, quarantine, checkpoints)
    http_client = TestClient(app, base_url="http://backend.test")
    transport = HttpsTransport(base_url="http://backend.test", client=http_client)

    gateway_state = GatewayState(gateway_id=device_id, vehicle_profile_id="demo-v1", private_key=device_key, batch_size=5)
    queue = SqliteQueue(tmp_path / "queue.db")
    checkpoint_store = CheckpointStore(tmp_path / "checkpoint_store.db")
    drainer = Drainer(device_id, queue, checkpoint_store, transport, device_key)

    harness = Harness(
        gateway_id=device_id,
        gateway_state=gateway_state,
        queue=queue,
        checkpoint_store=checkpoint_store,
        transport=transport,
        drainer=drainer,
        registry=registry,
        trusted_store=trusted_store,
        quarantine=quarantine,
        checkpoints=checkpoints,
        http_client=http_client,
    )
    yield harness
    harness.close()
