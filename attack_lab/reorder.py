#!/usr/bin/env python
"""Attack 5: reorder buffered records before upload. Two events are swapped
in transmission order; chain/sequence validation must reject at least one
of them (OUT_OF_ORDER or CHAIN_MISMATCH)."""

from __future__ import annotations

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource


def main() -> None:
    with temp_harness() as harness:
        envelopes = [harness.gateway_state.build_and_sign(f) for f in SimulatorSource(frame_count=3, realtime=False).frames()]
        reordered = [envelopes[0], envelopes[2], envelopes[1]]

        body = harness.submit(reordered)
        reasons = set(body["rejected"].values())
        ok = bool(reasons & {"OUT_OF_ORDER", "CHAIN_MISMATCH"})
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] reorder: expected one of {{'OUT_OF_ORDER', 'CHAIN_MISMATCH'}}, observed {sorted(reasons)}")
        print(f"[info] accepted={len(body['accepted'])} of 3")
        exit_with(ok)


if __name__ == "__main__":
    main()
