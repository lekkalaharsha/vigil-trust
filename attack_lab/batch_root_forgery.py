#!/usr/bin/env python
"""Attack 7: modify the batch root. The signed batch commitment declares a
Merkle root that does not match the events actually sent; the backend must
reject the whole batch as BATCH_ROOT_INVALID even though every individual
event signature is valid."""

from __future__ import annotations

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource


def main() -> None:
    with temp_harness() as harness:
        envelopes = [harness.gateway_state.build_and_sign(f) for f in SimulatorSource(frame_count=3, realtime=False).frames()]
        body = harness.submit(envelopes, batch_root="0" * 64)
        ok = report("batch_root_forgery", "BATCH_ROOT_INVALID", set(body["rejected"].values()))
        print(f"[info] accepted={body['accepted']}")
        exit_with(ok)


if __name__ == "__main__":
    main()
