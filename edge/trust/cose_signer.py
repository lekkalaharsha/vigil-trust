"""COSE_Sign1-style signing container (ECDSA P-256 / SHA-256, alg ES256).

pycose does not currently pin cleanly against this project's dependency set,
so per CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 1 ("do not invent
cryptographic algorithms") this module implements the RFC 9052 COSE_Sign1
*structure* (Sig_structure, protected header, raw r||s ECDSA signature) on
top of pyca/cryptography, which does the actual signing math. It is not a
certified COSE implementation -- see docs/LIMITATIONS.md. Test vectors live
in tests/unit/test_cose_signer.py.

alg label -7 = ES256, per the IANA COSE Algorithms registry (RFC 9053).
"""

from __future__ import annotations

from dataclasses import dataclass

import cbor2
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

ALG_ES256 = -7
COSE_ALG_HEADER = 1
SIG1_CONTEXT = "Signature1"
P256_SIGNATURE_LEN = 64  # r (32 bytes) || s (32 bytes)


class SignatureError(ValueError):
    pass


def _protected_header_bytes() -> bytes:
    return cbor2.dumps({COSE_ALG_HEADER: ALG_ES256}, canonical=True)


def _sig_structure_bytes(protected: bytes, payload: bytes, external_aad: bytes = b"") -> bytes:
    return cbor2.dumps([SIG1_CONTEXT, protected, external_aad, payload], canonical=True)


def _der_to_raw(der_signature: bytes) -> bytes:
    r, s = utils.decode_dss_signature(der_signature)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def _raw_to_der(raw_signature: bytes) -> bytes:
    if len(raw_signature) != P256_SIGNATURE_LEN:
        raise SignatureError(f"expected {P256_SIGNATURE_LEN}-byte raw signature, got {len(raw_signature)}")
    r = int.from_bytes(raw_signature[:32], "big")
    s = int.from_bytes(raw_signature[32:], "big")
    return utils.encode_dss_signature(r, s)


@dataclass(frozen=True)
class CoseSign1:
    protected: bytes
    payload: bytes
    signature: bytes

    def to_cbor(self) -> bytes:
        return cbor2.dumps([self.protected, {}, self.payload, self.signature], canonical=True)

    @staticmethod
    def from_cbor(data: bytes) -> "CoseSign1":
        decoded = cbor2.loads(data)
        if not (isinstance(decoded, list) and len(decoded) == 4):
            raise SignatureError("malformed COSE_Sign1 structure")
        protected, _unprotected, payload, signature = decoded
        return CoseSign1(protected=protected, payload=payload, signature=signature)


def sign(payload: bytes, private_key: ec.EllipticCurvePrivateKey) -> CoseSign1:
    protected = _protected_header_bytes()
    sig_structure = _sig_structure_bytes(protected, payload)
    der_signature = private_key.sign(sig_structure, ec.ECDSA(hashes.SHA256()))
    raw_signature = _der_to_raw(der_signature)
    return CoseSign1(protected=protected, payload=payload, signature=raw_signature)


def verify(message: CoseSign1, public_key: ec.EllipticCurvePublicKey) -> bool:
    """Returns False for any defect in untrusted input (malformed header,
    unsupported/unexpected alg, wrong-length signature, invalid signature).
    Never raises on attacker-controlled input."""
    try:
        header = cbor2.loads(message.protected)
    except Exception:  # noqa: BLE001 - untrusted input
        return False
    if not isinstance(header, dict) or header.get(COSE_ALG_HEADER) != ALG_ES256:
        return False
    sig_structure = _sig_structure_bytes(message.protected, message.payload)
    try:
        der_signature = _raw_to_der(message.signature)
        public_key.verify(der_signature, sig_structure, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, SignatureError, ValueError, TypeError):
        return False
    return True
