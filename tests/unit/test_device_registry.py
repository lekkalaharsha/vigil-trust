from backend.device_registry.registry import REVOKED, TRUSTED, DeviceRegistry
from edge.trust.identity import generate_keypair
from cryptography.hazmat.primitives import serialization


def _pub_pem(key) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")


def test_register_and_lookup(tmp_path):
    registry = DeviceRegistry(tmp_path / "registry.db")
    key = generate_keypair()
    registry.register("gw-1", "demo-v1", _pub_pem(key))
    record = registry.get("gw-1")
    assert record is not None
    assert record.status == TRUSTED
    assert record.public_key.public_numbers() == key.public_key().public_numbers()
    registry.close()


def test_unknown_device_returns_none(tmp_path):
    registry = DeviceRegistry(tmp_path / "registry.db")
    assert registry.get("does-not-exist") is None
    registry.close()


def test_revocation(tmp_path):
    registry = DeviceRegistry(tmp_path / "registry.db")
    key = generate_keypair()
    registry.register("gw-1", "demo-v1", _pub_pem(key))
    registry.set_status("gw-1", REVOKED)
    assert registry.get("gw-1").status == REVOKED
    registry.close()
