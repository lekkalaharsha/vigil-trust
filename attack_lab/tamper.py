#!/usr/bin/env python
"""Attack 2: signed payload modified after signing. One field of a valid
COSE_Sign1 event is edited in place (the signature is left untouched,
since the attacker does not have the device's private key). The backend
must reject it as SIGNATURE_INVALID."""

from __future__ import annotations

import cbor2

from attack_lab.common import exit_with, report, temp_harness
from edge.acquisition.simulator import SimulatorSource
from edge.trust.cose_signer import CoseSign1


def main() -> None:
    with temp_harness() as harness:
        frame = next(iter(SimulatorSource(frame_count=1, realtime=False).frames()))
        envelope = harness.gateway_state.build_and_sign(frame)

        cose = CoseSign1.from_cbor(envelope.cose_cbor)
        decoded = cbor2.loads(cose.payload)
        decoded["can_id"] = decoded["can_id"] + 1
        tampered_payload = cbor2.dumps(decoded, canonical=True)
        tampered_cose = CoseSign1(protected=cose.protected, payload=tampered_payload, signature=cose.signature)
        tampered_envelope = envelope.__class__(
            gateway_id=envelope.gateway_id, boot_epoch=envelope.boot_epoch, sequence=envelope.sequence,
            batch_id=envelope.batch_id, event_hash=envelope.event_hash, cose_cbor=tampered_cose.to_cbor(),
        )

        body = harness.submit([tampered_envelope])
        ok = report("tamper", "SIGNATURE_INVALID", set(body["rejected"].values()))
        exit_with(ok)


if __name__ == "__main__":
    main()
