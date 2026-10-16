"""Shared harness for the standalone attack-lab CLI scripts.

Each script in this package is runnable directly (`python -m attack_lab.tamper`)
and prints a PASS/FAIL line based on whether the backend's rejection reason
code matched what the attack is supposed to trigger. The same scenarios are
also covered as pytest assertions in tests/security/test_attack_lab.py --
these scripts exist so a reviewer/judge can run one command per attack and
see output directly, without reading test code.

Everything here runs against a disposable temp-directory backend + the
local simulator. Nothing here ever touches a real vehicle or network.
"""

from __future__ import annotations

import base64
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.checkpoints.store import CheckpointService
from backend.device_registry.registry import TRUSTED, DeviceRegistry
from backend.quarantine.store import QuarantineStore
from backend.verifier.trusted_store import TrustedStore
from edge.trust import cose_signer, merkle
from edge.trust.checkpoints import BatchCommitment
from edge.trust.envelope import GatewayState
from edge.trust.identity import device_id_from_public_key, generate_keypair


class AttackLabHarness:
    def __init__(self, tmp_dir: Path) -> None:
        self.device_key = generate_keypair()
        self.gateway_id = device_id_from_public_key(self.device_key.public_key())
        public_key_pem = self.device_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

        self.registry = DeviceRegistry(tmp_dir / "registry.db")
        self.registry.register(self.gateway_id, "demo-v1", public_key_pem, status=TRUSTED)
        self.trusted_store = TrustedStore(tmp_dir / "trusted.db")
        self.quarantine = QuarantineStore(tmp_dir / "quarantine.db")
        self.checkpoints = CheckpointService(tmp_dir / "checkpoints.db", generate_keypair())

        app = create_app(self.registry, self.trusted_store, self.quarantine, self.checkpoints)
        self.client = TestClient(app, base_url="http://backend.test")
        self.gateway_state = GatewayState(gateway_id=self.gateway_id, vehicle_profile_id="demo-v1", private_key=self.device_key)
        self.last_checkpoint = "0" * 64

    def close(self) -> None:
        self.client.close()
        self.registry.close()
        self.trusted_store.close()
        self.quarantine.close()
        self.checkpoints.close()

    def submit(self, envelopes, *, signing_key=None, gateway_id=None, previous_checkpoint_digest=None, batch_root=None):
        signing_key = signing_key or self.device_key
        gateway_id = gateway_id or self.gateway_id
        if previous_checkpoint_digest is None:
            previous_checkpoint_digest = self.last_checkpoint
        if batch_root is None:
            batch_root = merkle.build_merkle_root([e.event_hash for e in envelopes])

        commitment = BatchCommitment(
            gateway_id=gateway_id,
            boot_epoch=envelopes[0].boot_epoch,
            first_sequence=envelopes[0].sequence,
            last_sequence=envelopes[-1].sequence,
            previous_checkpoint_digest=previous_checkpoint_digest,
            batch_root=batch_root,
        )
        signed_commitment = cose_signer.sign(commitment.canonical_bytes(), signing_key)
        response = self.client.post(
            "/ingest/batch",
            json={
                "gateway_id": gateway_id,
                "batch_commitment": base64.b64encode(signed_commitment.to_cbor()).decode("ascii"),
                "events": [base64.b64encode(e.cose_cbor).decode("ascii") for e in envelopes],
            },
        )
        body = response.json()
        if body.get("checkpoint"):
            self.last_checkpoint = body["checkpoint"]
        return body


@contextmanager
def temp_harness():
    tmp_dir = Path(tempfile.mkdtemp(prefix="vigil_attack_lab_"))
    harness = AttackLabHarness(tmp_dir)
    try:
        yield harness
    finally:
        harness.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def report(scenario: str, expected_reason: str, actual_reasons: set[str]) -> bool:
    ok = expected_reason in actual_reasons
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {scenario}: expected reason {expected_reason!r}, observed {sorted(actual_reasons)}")
    return ok


def exit_with(ok: bool) -> None:
    sys.exit(0 if ok else 1)
