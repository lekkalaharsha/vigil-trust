from edge.trust.canonical import CanonicalEvent, CanonicalEventError, canonical_bytes, event_digest_hex
import pytest


def make_event(**overrides):
    base = dict(
        gateway_id="gw-1",
        vehicle_profile_id="demo-v1",
        boot_epoch=42,
        sequence=0,
        capture_time=1.0,
        can_channel="sim0",
        can_id=0x100,
        is_extended_id=False,
        is_fd=False,
        dlc=8,
        raw_payload=b"\x01\x02\x03\x04\x05\x06\x07\x08",
        previous_event_hash="0" * 64,
        batch_id="batch-1",
        policy_version=1,
    )
    base.update(overrides)
    return CanonicalEvent(**base)


def test_same_logical_event_produces_same_bytes_and_digest():
    e1 = make_event()
    e2 = make_event()
    assert canonical_bytes(e1) == canonical_bytes(e2)
    assert event_digest_hex(e1) == event_digest_hex(e2)


def test_different_payload_changes_digest():
    e1 = make_event()
    e2 = make_event(raw_payload=b"\x01\x02\x03\x04\x05\x06\x07\x09")
    assert event_digest_hex(e1) != event_digest_hex(e2)


def test_requires_exactly_one_payload_field():
    with pytest.raises(CanonicalEventError):
        CanonicalEvent(
            gateway_id="gw-1", vehicle_profile_id="demo-v1", boot_epoch=1, sequence=0,
            capture_time=1.0, can_channel="sim0", can_id=1, is_extended_id=False, is_fd=False,
            dlc=8, previous_event_hash="0" * 64, batch_id="b", policy_version=1,
        )


def test_invalid_dlc_rejected():
    with pytest.raises(CanonicalEventError):
        make_event(dlc=999)


def test_missing_field_in_dict_input_raises():
    d = make_event().to_dict()
    del d["sequence"]
    with pytest.raises(CanonicalEventError):
        canonical_bytes(d)
