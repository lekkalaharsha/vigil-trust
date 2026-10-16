#!/usr/bin/env python
"""Attack 4: duplicate event injected twice within one batch submission.
The backend must accept the first occurrence and reject the second as
DUPLICATE."""

from __future__ import annotations

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource
from edge.trust import merkle


def main() -> None:
    with temp_harness() as harness:
        frame = next(iter(SimulatorSource(frame_count=1, realtime=False).frames()))
        envelope = harness.gateway_state.build_and_sign(frame)

        body = harness.submit([envelope, envelope], batch_root=merkle.build_merkle_root([envelope.event_hash]))
        ok = report("duplicate", "DUPLICATE", set(body["rejected"].values()))
        print(f"[info] accepted={body['accepted']}")
        exit_with(ok)


if __name__ == "__main__":
    main()
