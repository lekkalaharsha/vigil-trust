import pytest

from backend.quarantine.store import QuarantineStore


def test_add_and_recent(tmp_path):
    store = QuarantineStore(tmp_path / "quarantine.db")
    store.add("gw-1", "SIGNATURE_INVALID", detail="bad sig")
    store.add("gw-1", "REPLAY")
    recent = store.recent()
    assert len(recent) == 2
    assert recent[0]["reason_code"] == "REPLAY"
    store.close()


def test_rejects_unknown_reason_code(tmp_path):
    store = QuarantineStore(tmp_path / "quarantine.db")
    with pytest.raises(ValueError):
        store.add("gw-1", "NOT_A_REAL_REASON_CODE")
    store.close()


def test_reason_histogram(tmp_path):
    store = QuarantineStore(tmp_path / "quarantine.db")
    store.add("gw-1", "REPLAY")
    store.add("gw-1", "REPLAY")
    store.add("gw-1", "DUPLICATE")
    histogram = store.reason_histogram()
    assert histogram == {"REPLAY": 2, "DUPLICATE": 1}
    store.close()
