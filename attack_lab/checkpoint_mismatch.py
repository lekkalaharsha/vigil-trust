#!/usr/bin/env python
"""Attack 9: reconnect using a wrong/stale checkpoint reference. After one
batch is accepted, a follow-on batch declares a previous_checkpoint_digest
that does not match what the backend actually issued; the backend must
reject it as CHECKPOINT_MISMATCH."""

from __future__ import annotations

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource


def main() -> None:
    with temp_harness() as harness:
        frames = list(SimulatorSource(frame_count=3, realtime=False).frames())
        first_batch = [harness.gateway_state.build_and_sign(f) for f in frames[:2]]
        harness.submit(first_batch)

        next_envelope = harness.gateway_state.build_and_sign(frames[2])
        body = harness.submit([next_envelope], previous_checkpoint_digest="deadbeef" * 8)
        ok = report("checkpoint_mismatch", "CHECKPOINT_MISMATCH", set(body["rejected"].values()))
        exit_with(ok)


if __name__ == "__main__":
    main()
