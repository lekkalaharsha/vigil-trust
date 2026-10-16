#!/usr/bin/env python
"""Attack 3: replay a previously accepted batch. The exact same signed
events and batch commitment are resubmitted after the first submission was
already accepted; the backend must reject the resend as REPLAY, since the
event hashes already exist in the trusted store."""

from __future__ import annotations

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource


def main() -> None:
    with temp_harness() as harness:
        envelopes = [harness.gateway_state.build_and_sign(f) for f in SimulatorSource(frame_count=3, realtime=False).frames()]

        first = harness.submit(envelopes)
        print(f"[info] first submission accepted={len(first['accepted'])}")

        second = harness.submit(envelopes, previous_checkpoint_digest=first["checkpoint"])
        ok = report("replay", "REPLAY", set(second["rejected"].values()))
        exit_with(ok)


if __name__ == "__main__":
    main()
