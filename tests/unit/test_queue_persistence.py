"""Durable queue must survive process restart without losing buffered
(not-yet-sent) telemetry -- CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md "Automated
tests" requirement."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ec

from edge.queue.sqlite_queue import SqliteQueue
from edge.trust.envelope import GatewayState
from edge.acquisition.simulator import SimulatorSource


def _make_envelopes(n, gateway_id="gw-1"):
    key = ec.generate_private_key(ec.SECP256R1())
    state = GatewayState(gateway_id=gateway_id, vehicle_profile_id="demo-v1", private_key=key, batch_size=n + 1)
    return [state.build_and_sign(f) for f in SimulatorSource(frame_count=n, realtime=False).frames()]


def test_queue_survives_restart(tmp_path):
    db_path = tmp_path / "queue.db"
    envelopes = _make_envelopes(5)

    queue = SqliteQueue(db_path)
    for e in envelopes:
        queue.enqueue(e)
    assert queue.depth() == 5
    queue.close()

    reopened = SqliteQueue(db_path)
    assert reopened.depth() == 5
    items = reopened.pending()
    assert [i.envelope.sequence for i in items] == [0, 1, 2, 3, 4]
    reopened.close()


def test_mark_sent_removes_from_pending(tmp_path):
    queue = SqliteQueue(tmp_path / "queue.db")
    for e in _make_envelopes(3):
        queue.enqueue(e)
    items = queue.pending()
    queue.mark_sent([items[0].id, items[1].id])
    assert queue.depth() == 1
    assert queue.total_count() == 3
    queue.close()


def test_duplicate_sequence_for_same_gateway_boot_rejected_by_schema(tmp_path):
    """DB-level defense in depth: UNIQUE(gateway_id, boot_epoch, sequence)."""
    import sqlite3

    queue = SqliteQueue(tmp_path / "queue.db")
    envelopes = _make_envelopes(1)
    queue.enqueue(envelopes[0])
    try:
        queue.enqueue(envelopes[0])
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised
    queue.close()
