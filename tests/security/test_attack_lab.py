"""Deterministic attack-lab scenarios, run against the same in-memory
harness as the normal-path tests (tests/integration/conftest.py). Each test
corresponds to one scenario in CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md's
"Attack lab" section and VIGIL_TRUST_Implementation_SOP.md section 7.

These only ever attack the local simulator data, never a real vehicle.
"""

from __future__ import annotations

import base64

import cbor2

from backend.device_registry.registry import REVOKED
from edge.acquisition.simulator import SimulatorSource
from edge.trust import cose_signer, merkle
from edge.trust.checkpoints import BatchCommitment
from edge.trust.cose_signer import CoseSign1
from edge.trust.envelope import GatewayState
from edge.trust.identity import device_id_from_public_key, generate_keypair


def _make_frames(n: int):
    return list(SimulatorSource(frame_count=n, realtime=False).frames())


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _submit(harness, gateway_id, signing_key, envelopes, *, previous_checkpoint_digest=None, batch_root=None):
    """Build and POST a batch commitment for an arbitrary list of
    (already-built) envelopes, with optional forged batch_root / checkpoint
    reference, and return the parsed JSON response."""
    if previous_checkpoint_digest is None:
        previous_checkpoint_digest = harness.checkpoint_store.get(gateway_id)
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

    response = harness.http_client.post(
        "/ingest/batch",
        json={
            "gateway_id": gateway_id,
            "batch_commitment": _b64(signed_commitment.to_cbor()),
            "events": [_b64(e.cose_cbor) for e in envelopes],
        },
    )
    return response.json()


def test_scenario_1_unauthorized_spoofed_device(harness):
    """An unregistered device's signed event must be rejected as UNKNOWN_DEVICE."""
    attacker_key = generate_keypair()
    attacker_id = device_id_from_public_key(attacker_key.public_key())
    attacker_state = GatewayState(gateway_id=attacker_id, vehicle_profile_id="demo-v1", private_key=attacker_key)
    envelope = attacker_state.build_and_sign(_make_frames(1)[0])

    body = _submit(harness, attacker_id, attacker_key, [envelope], previous_checkpoint_digest="0" * 64)
    assert "UNKNOWN_DEVICE" in body["rejected"].values()
    assert harness.trusted_store.count() == 0


def test_scenario_2_signed_payload_modified_after_signing(harness):
    """Tampering with a COSE_Sign1 payload after signing must fail signature
    verification (SIGNATURE_INVALID)."""
    envelope = harness.gateway_state.build_and_sign(_make_frames(1)[0])

    cose = CoseSign1.from_cbor(envelope.cose_cbor)
    decoded = cbor2.loads(cose.payload)
    decoded["can_id"] = decoded["can_id"] + 1  # attacker edits the field in place
    tampered_payload = cbor2.dumps(decoded, canonical=True)
    tampered_cose = CoseSign1(protected=cose.protected, payload=tampered_payload, signature=cose.signature)
    tampered_envelope = envelope.__class__(
        gateway_id=envelope.gateway_id, boot_epoch=envelope.boot_epoch, sequence=envelope.sequence,
        batch_id=envelope.batch_id, event_hash=envelope.event_hash, cose_cbor=tampered_cose.to_cbor(),
    )

    body = _submit(harness, harness.gateway_id, harness.gateway_state.private_key, [tampered_envelope])
    assert list(body["rejected"].values()) == ["SIGNATURE_INVALID"]
    assert harness.trusted_store.count() == 0


def test_scenario_3_replay_previously_accepted_event(harness):
    """Resubmitting the exact same already-accepted batch must be rejected
    (REPLAY: that event_hash has already been committed to the trusted
    store, independent of current chain position)."""
    envelopes = [harness.gateway_state.build_and_sign(f) for f in _make_frames(3)]
    first = _submit(harness, harness.gateway_id, harness.gateway_state.private_key, envelopes)
    assert len(first["accepted"]) == 3
    harness.checkpoint_store.set(harness.gateway_id, first["checkpoint"])

    second = _submit(
        harness, harness.gateway_id, harness.gateway_state.private_key, envelopes,
        previous_checkpoint_digest=first["checkpoint"],
    )
    assert second["accepted"] == []
    assert set(second["rejected"].values()) == {"REPLAY"}
    assert harness.trusted_store.count() == 3


def test_scenario_4_duplicate_event_within_one_batch(harness):
    """The same signed event appearing twice inside one batch submission has
    its second occurrence rejected as DUPLICATE. The batch_root here is
    declared over only the single genuinely-unique leaf (what an honest
    commitment for this event set would look like); a naive attacker who
    instead declares a root over both copies gets the stronger
    BATCH_ROOT_INVALID outcome for the whole batch, since the Merkle root
    must match exactly what the backend ends up accepting."""
    envelope = harness.gateway_state.build_and_sign(_make_frames(1)[0])
    body = _submit(
        harness, harness.gateway_id, harness.gateway_state.private_key, [envelope, envelope],
        batch_root=merkle.build_merkle_root([envelope.event_hash]),
    )
    assert body["accepted"] == [envelope.event_hash]
    assert body["rejected"].get(envelope.event_hash) == "DUPLICATE"
    assert harness.trusted_store.count() == 1


def test_scenario_5_reorder_buffered_records(harness):
    """Swapping two buffered records before upload must be rejected by
    chain/sequence validation (OUT_OF_ORDER or CHAIN_MISMATCH)."""
    envelopes = [harness.gateway_state.build_and_sign(f) for f in _make_frames(3)]
    reordered = [envelopes[0], envelopes[2], envelopes[1]]
    body = _submit(harness, harness.gateway_id, harness.gateway_state.private_key, reordered)
    assert len(body["accepted"]) < 3
    assert set(body["rejected"].values()) & {"OUT_OF_ORDER", "CHAIN_MISMATCH"}


def test_scenario_6_change_previous_hash(harness):
    """An attacker cannot forge the previous_event_hash field without a
    valid device signature -- re-signing with any other key is rejected as
    SIGNATURE_INVALID against the registered device's public key."""
    envelope = harness.gateway_state.build_and_sign(_make_frames(1)[0])
    cose = CoseSign1.from_cbor(envelope.cose_cbor)
    decoded = cbor2.loads(cose.payload)
    decoded["previous_event_hash"] = "f" * 64
    forged_payload = cbor2.dumps(decoded, canonical=True)
    attacker_key = generate_keypair()
    forged_cose = cose_signer.sign(forged_payload, attacker_key)
    forged_envelope = envelope.__class__(
        gateway_id=envelope.gateway_id, boot_epoch=envelope.boot_epoch, sequence=envelope.sequence,
        batch_id=envelope.batch_id, event_hash=envelope.event_hash, cose_cbor=forged_cose.to_cbor(),
    )

    body = _submit(harness, harness.gateway_id, harness.gateway_state.private_key, [forged_envelope])
    assert list(body["rejected"].values()) == ["SIGNATURE_INVALID"]


def test_scenario_7_modify_batch_root(harness):
    """A batch commitment whose declared batch_root does not match the
    recomputed Merkle root over accepted events is rejected wholesale as
    BATCH_ROOT_INVALID, even though every individual event signature is
    valid."""
    envelopes = [harness.gateway_state.build_and_sign(f) for f in _make_frames(3)]
    body = _submit(
        harness, harness.gateway_id, harness.gateway_state.private_key, envelopes, batch_root="0" * 64
    )
    assert body["accepted"] == []
    assert set(body["rejected"].values()) == {"BATCH_ROOT_INVALID"}
    assert harness.trusted_store.count() == 0


def test_scenario_8_offline_queue_then_reconnect_continuity(harness):
    """Simulated network disconnect: drain fails (TransportError), queue
    depth grows; on reconnect, draining succeeds and continuity holds."""
    from edge.transport.base import TransportError

    class FlakyTransport:
        def __init__(self, real):
            self._real = real
            self.online = False

        def submit_batch(self, *args, **kwargs):
            if not self.online:
                raise TransportError("simulated network outage")
            return self._real.submit_batch(*args, **kwargs)

        def close(self):
            self._real.close()

    flaky = FlakyTransport(harness.transport)
    harness.drainer._transport = flaky  # swap transport under the drainer

    for frame in _make_frames(6):
        harness.queue.enqueue(harness.gateway_state.build_and_sign(frame))

    result = harness.drain()
    assert result.transport_error is not None
    assert harness.queue.depth() == 6

    flaky.online = True
    results = harness.drain_all()
    assert sum(r.accepted for r in results) == 6
    assert harness.queue.depth() == 0
    assert harness.trusted_store.count() == 6


def test_scenario_9_reconnect_with_wrong_checkpoint(harness):
    """A batch commitment referencing a stale/incorrect previous checkpoint
    digest is rejected as CHECKPOINT_MISMATCH."""
    envelopes = [harness.gateway_state.build_and_sign(f) for f in _make_frames(2)]
    first = _submit(harness, harness.gateway_id, harness.gateway_state.private_key, envelopes)
    assert len(first["accepted"]) == 2

    next_envelope = harness.gateway_state.build_and_sign(_make_frames(1)[0])
    body = _submit(
        harness, harness.gateway_id, harness.gateway_state.private_key, [next_envelope],
        previous_checkpoint_digest="deadbeef" * 8,
    )
    assert set(body["rejected"].values()) == {"CHECKPOINT_MISMATCH"}


def test_scenario_10_revoked_device_rejected(harness):
    """A device explicitly revoked in the registry is rejected wholesale as
    DEVICE_REVOKED, regardless of otherwise-valid signatures."""
    harness.registry.set_status(harness.gateway_id, REVOKED)
    envelope = harness.gateway_state.build_and_sign(_make_frames(1)[0])
    body = _submit(harness, harness.gateway_id, harness.gateway_state.private_key, [envelope])
    assert set(body["rejected"].values()) == {"DEVICE_REVOKED"}
    assert harness.trusted_store.count() == 0
    assert "DEVICE_REVOKED" in [r["reason_code"] for r in harness.quarantine.recent()]
