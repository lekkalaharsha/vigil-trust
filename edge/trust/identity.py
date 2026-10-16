"""Device identity: ECDSA P-256 keypair load/generate and device_id derivation.

For the hackathon prototype the private key lives in a local PEM file
(SoftwareSigner backend, see edge/trust/cose_signer.py and
firmware/uno_q_mcu/README.md for the hardware-backed target). Private keys
are never committed to Git -- see scripts/dev_pki.py and .gitignore.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    private_key: ec.EllipticCurvePrivateKey | None
    public_key: ec.EllipticCurvePublicKey

    @property
    def has_private_key(self) -> bool:
        return self.private_key is not None


def device_id_from_public_key(public_key: ec.EllipticCurvePublicKey) -> str:
    """Stable device identifier: sha256 of the SubjectPublicKeyInfo, hex, truncated to 32 chars."""
    spki = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(spki).hexdigest()[:32]


def generate_keypair() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def load_identity_from_files(private_key_path: Path | str, public_key_path: Path | str | None = None) -> DeviceIdentity:
    private_key_path = Path(private_key_path)
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("only EC P-256 private keys are supported")
    public_key = private_key.public_key()
    return DeviceIdentity(
        device_id=device_id_from_public_key(public_key),
        private_key=private_key,
        public_key=public_key,
    )


def load_public_identity_from_file(public_key_path: Path | str) -> DeviceIdentity:
    public_key_path = Path(public_key_path)
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError("only EC P-256 public keys are supported")
    return DeviceIdentity(
        device_id=device_id_from_public_key(public_key),
        private_key=None,
        public_key=public_key,
    )


def write_keypair(private_key: ec.EllipticCurvePrivateKey, private_key_path: Path, public_key_path: Path) -> None:
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
