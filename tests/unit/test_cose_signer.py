from cryptography.hazmat.primitives.asymmetric import ec

from edge.trust import cose_signer


def test_sign_and_verify_roundtrip():
    key = ec.generate_private_key(ec.SECP256R1())
    payload = b"hello vigil"
    signed = cose_signer.sign(payload, key)
    assert cose_signer.verify(signed, key.public_key()) is True


def test_tampered_payload_fails_verification():
    key = ec.generate_private_key(ec.SECP256R1())
    signed = cose_signer.sign(b"original", key)
    tampered = cose_signer.CoseSign1(protected=signed.protected, payload=b"tampered!", signature=signed.signature)
    assert cose_signer.verify(tampered, key.public_key()) is False


def test_wrong_key_fails_verification():
    key = ec.generate_private_key(ec.SECP256R1())
    other_key = ec.generate_private_key(ec.SECP256R1())
    signed = cose_signer.sign(b"payload", key)
    assert cose_signer.verify(signed, other_key.public_key()) is False


def test_cbor_round_trip_preserves_signature():
    key = ec.generate_private_key(ec.SECP256R1())
    signed = cose_signer.sign(b"payload", key)
    wire = signed.to_cbor()
    restored = cose_signer.CoseSign1.from_cbor(wire)
    assert cose_signer.verify(restored, key.public_key()) is True


def test_corrupted_protected_header_alg_rejected():
    import cbor2

    key = ec.generate_private_key(ec.SECP256R1())
    signed = cose_signer.sign(b"payload", key)
    bad_protected = cbor2.dumps({1: -999}, canonical=True)
    bad = cose_signer.CoseSign1(protected=bad_protected, payload=signed.payload, signature=signed.signature)
    assert cose_signer.verify(bad, key.public_key()) is False
