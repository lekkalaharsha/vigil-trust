from pathlib import Path

import pytest

from edge.acquisition.replay import ReplayParseError, ReplaySource, parse_line
from edge.acquisition.simulator import SimulatorSource


def test_simulator_is_deterministic():
    frames_a = list(SimulatorSource(frame_count=50, realtime=False).frames())
    frames_b = list(SimulatorSource(frame_count=50, realtime=False).frames())
    assert [f.data for f in frames_a] == [f.data for f in frames_b]
    assert [f.can_id for f in frames_a] == [f.can_id for f in frames_b]


def test_replay_parses_fixture_log():
    log_path = Path(__file__).resolve().parents[2] / "data" / "synthetic_can.log"
    frames = list(ReplaySource(log_path).frames())
    assert len(frames) == 158
    assert frames[0].can_id == 0x100
    assert frames[0].data == bytes.fromhex("1020304050607080")


def test_replay_rejects_malformed_line():
    with pytest.raises(ReplayParseError):
        parse_line("not a valid line")


def test_replay_ignores_comments_and_blank_lines():
    assert parse_line("# a comment") is None
    assert parse_line("   ") is None
