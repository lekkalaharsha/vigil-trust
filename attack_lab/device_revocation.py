#!/usr/bin/env python
"""Attack scenario: a device the operator has explicitly revoked must be
rejected wholesale as DEVICE_REVOKED, regardless of otherwise-valid
signatures and chain state. See attack_lab/db_tamper_check.py for the
separate backend database copy tamper-verification utility."""

from __future__ import annotations

from backend.device_registry.registry import REVOKED

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource


def main() -> None:
    with temp_harness() as harness:
        harness.registry.set_status(harness.gateway_id, REVOKED)
        frame = next(iter(SimulatorSource(frame_count=1, realtime=False).frames()))
        envelope = harness.gateway_state.build_and_sign(frame)
        body = harness.submit([envelope])
        ok = report("device_revocation", "DEVICE_REVOKED", set(body["rejected"].values()))
        exit_with(ok)


if __name__ == "__main__":
    main()
