import pytest

from edge.trust import chain


def test_chain_is_deterministic():
    h1 = chain.next_chain_hash(b"event-bytes", chain.GENESIS_HASH)
    h2 = chain.next_chain_hash(b"event-bytes", chain.GENESIS_HASH)
    assert h1 == h2
    assert len(h1) == 64


def test_different_previous_hash_changes_result():
    h1 = chain.next_chain_hash(b"event-bytes", chain.GENESIS_HASH)
    h2 = chain.next_chain_hash(b"event-bytes", "1" * 64)
    assert h1 != h2


def test_verify_chain_link():
    h = chain.next_chain_hash(b"event-bytes", chain.GENESIS_HASH)
    assert chain.verify_chain_link(b"event-bytes", chain.GENESIS_HASH, h) is True
    assert chain.verify_chain_link(b"tampered", chain.GENESIS_HASH, h) is False


def test_rejects_malformed_previous_hash():
    with pytest.raises(ValueError):
        chain.next_chain_hash(b"x", "not-a-valid-hash")
