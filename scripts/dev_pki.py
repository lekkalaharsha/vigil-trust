#!/usr/bin/env python
"""Generate a local demo PKI: a self-signed CA, a backend/broker TLS server
cert, and per-device client certs used for mTLS *and* as the device's
ECDSA P-256 COSE signing key.

This is a DEMO CA for the hackathon prototype only. It is not an
operational PKI: no CRL/OCSP, no HSM-backed root key, no real
organizational identity vetting. Never reuse these keys/certs outside this
local demo. Generated private keys are written under certs/ and .gitignore
excludes certs/ entirely -- nothing here should ever be committed.

Usage:
    python scripts/dev_pki.py --device gw-demo-01 --device gw-demo-02
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parent.parent
CERTS_DIR = ROOT / "certs"
DEVICES_DIR = CERTS_DIR / "devices"

ONE_YEAR = datetime.timedelta(days=365)


def _write_key(key: ec.EllipticCurvePrivateKey, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _write_cert(cert: x509.Certificate, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def generate_ca() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "VIGIL-TRUST Demo Root CA (NOT FOR PRODUCTION)")]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + ONE_YEAR)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, key_cert_sign=True, crl_sign=True,
            content_commitment=False, key_encipherment=False, data_encipherment=False,
            key_agreement=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def generate_leaf(
    common_name: str,
    ca_key: ec.EllipticCurvePrivateKey,
    ca_cert: x509.Certificate,
    server_auth: bool,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + ONE_YEAR)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    )
    eku = [x509.oid.ExtendedKeyUsageOID.SERVER_AUTH] if server_auth else [x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]
    builder = builder.add_extension(x509.ExtendedKeyUsage(eku), critical=False)
    if server_auth:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1"))]),
            critical=False,
        )
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", action="append", default=[], help="device_id to provision a client cert for (repeatable)")
    parser.add_argument("--out", default=str(CERTS_DIR), help="output directory for generated PKI material")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    devices_dir = out_dir / "devices"

    ca_key, ca_cert = generate_ca()
    _write_key(ca_key, out_dir / "ca.key")
    _write_cert(ca_cert, out_dir / "ca.crt")
    print(f"[dev_pki] wrote demo CA: {out_dir / 'ca.crt'}")

    backend_key, backend_cert = generate_leaf("localhost", ca_key, ca_cert, server_auth=True)
    _write_key(backend_key, out_dir / "backend.key")
    _write_cert(backend_cert, out_dir / "backend.crt")
    print(f"[dev_pki] wrote backend server cert: {out_dir / 'backend.crt'}")

    devices = args.device or ["gw-demo-01"]
    for device_id in devices:
        device_key, device_cert = generate_leaf(device_id, ca_key, ca_cert, server_auth=False)
        _write_key(device_key, devices_dir / f"{device_id}.key")
        _write_cert(device_cert, devices_dir / f"{device_id}.crt")
        public_pem = device_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        (devices_dir / f"{device_id}.pub.pem").write_bytes(public_pem)
        print(f"[dev_pki] wrote device cert + signing key: {devices_dir / f'{device_id}.key'}")

    print("\n[dev_pki] DEMO PKI ONLY. Do not use outside this local prototype.")
    print(f"[dev_pki] next: register devices in the backend registry, e.g.:")
    print(f"           .venv/Scripts/python.exe -m scripts.register_device --device-id {devices[0]} "
          f"--public-key-path {devices_dir / (devices[0] + '.pub.pem')} --vehicle-profile demo-v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
