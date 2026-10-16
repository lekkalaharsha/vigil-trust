"""Normal-path end-to-end test: simulator frames -> signed envelopes ->
durable queue -> HTTPS transport -> backend verification -> trusted store.
Covers VIGIL_TRUST_Implementation_SOP.md section 4 "first software gate".
"""

from __future__ import annotations

from edge.acquisition.simulator import SimulatorSource


def test_normal_frames_are_accepted_and_appear_in_trusted_store(harness):
    source = SimulatorSource(frame_count=12, realtime=False)
    for frame in source.frames():
        envelope = harness.gateway_state.build_and_sign(frame)
        harness.queue.enqueue(envelope)

    assert harness.queue.depth() == 12

    results = harness.drain_all()
    assert sum(r.attempted for r in results) == 12
    assert sum(r.accepted for r in results) == 12
    assert sum(r.rejected for r in results) == 0
    assert all(r.transport_error is None for r in results)

    assert harness.queue.depth() == 0
    assert harness.trusted_store.count() == 12
    assert harness.quarantine.count() == 0


def test_checkpoint_is_issued_and_advances(harness):
    source = SimulatorSource(frame_count=5, realtime=False)
    for frame in source.frames():
        harness.queue.enqueue(harness.gateway_state.build_and_sign(frame))

    before = harness.checkpoint_store.get(harness.gateway_id)
    harness.drain()
    after = harness.checkpoint_store.get(harness.gateway_id)
    assert before != after


def test_second_batch_continues_chain_correctly(harness):
    source = SimulatorSource(frame_count=20, realtime=False)
    for i, frame in enumerate(source.frames()):
        harness.queue.enqueue(harness.gateway_state.build_and_sign(frame))
        if i == 4:
            harness.drain_all()
    harness.drain_all()
    assert harness.trusted_store.count() == 20
    assert harness.quarantine.count() == 0
