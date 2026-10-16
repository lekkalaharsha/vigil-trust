import hashlib

import pytest

from edge.trust import merkle


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def test_deterministic_root_for_same_input():
    hashes = [h("a"), h("b"), h("c"), h("d")]
    assert merkle.build_merkle_root(hashes) == merkle.build_merkle_root(hashes)


def test_order_sensitive():
    hashes = [h("a"), h("b"), h("c")]
    reordered = [h("a"), h("c"), h("b")]
    assert merkle.build_merkle_root(hashes) != merkle.build_merkle_root(reordered)


def test_single_leaf():
    root = merkle.build_merkle_root([h("only")])
    assert len(root) == 64


def test_odd_number_of_leaves_does_not_crash():
    hashes = [h(str(i)) for i in range(5)]
    root = merkle.build_merkle_root(hashes)
    assert len(root) == 64


def test_empty_batch_rejected():
    with pytest.raises(merkle.MerkleError):
        merkle.build_merkle_root([])


def test_changing_one_leaf_changes_root():
    hashes = [h("a"), h("b"), h("c"), h("d")]
    tampered = [h("a"), h("B"), h("c"), h("d")]
    assert merkle.build_merkle_root(hashes) != merkle.build_merkle_root(tampered)
