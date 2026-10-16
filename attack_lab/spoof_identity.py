#!/usr/bin/env python
"""Attack 1: unauthorized/spoofed device. An unregistered gateway signs and
submits a perfectly well-formed event; the backend must reject it as
UNKNOWN_DEVICE because it has no entry for that device_id."""

from __future__ import annotations

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource
from edge.trust.envelope import GatewayState
from edge.trust.identity import device_id_from_public_key, generate_keypair


def main() -> None:
    with temp_harness() as harness:
        attacker_key = generate_keypair()
        attacker_id = device_id_from_public_key(attacker_key.public_key())
        attacker_state = GatewayState(gateway_id=attacker_id, vehicle_profile_id="demo-v1", private_key=attacker_key)
        frame = next(iter(SimulatorSource(frame_count=1, realtime=False).frames()))
        envelope = attacker_state.build_and_sign(frame)

        body = harness.submit([envelope], signing_key=attacker_key, gateway_id=attacker_id, previous_checkpoint_digest="0" * 64)
        ok = report("spoof_identity", "UNKNOWN_DEVICE", set(body["rejected"].values()))
        exit_with(ok)


if __name__ == "__main__":
    main()
