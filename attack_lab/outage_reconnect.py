#!/usr/bin/env python
"""Attack/resilience scenario 8: network disconnect -> local queue growth
-> reconnect -> verified catch-up with continuity intact.

Unlike the other scripts this one is not an "attack" but the required
resilience demonstration (VIGIL_TRUST_Implementation_SOP.md section 4 and
Research_and_Architecture.md section 17 step 8-11)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from attack_lab.common import temp_harness
from edge.acquisition.simulator import SimulatorSource
from edge.pipeline import Drainer
from edge.queue.checkpoint_store import CheckpointStore
from edge.queue.sqlite_queue import SqliteQueue
from edge.transport.base import TransportError
from edge.transport.https import HttpsTransport


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="vigil_outage_reconnect_")
    ok = False
    with temp_harness() as harness:
        tmp_path = Path(tmp)
        queue = SqliteQueue(tmp_path / "queue.db")
        checkpoint_store = CheckpointStore(tmp_path / "checkpoint.db")
        real_transport = HttpsTransport(base_url="http://backend.test", client=harness.client)

        class FlakyTransport:
            def __init__(self):
                self.online = False

            def submit_batch(self, *a, **kw):
                if not self.online:
                    raise TransportError("simulated network outage")
                return real_transport.submit_batch(*a, **kw)

            def close(self):
                real_transport.close()

        flaky = FlakyTransport()
        drainer = Drainer(harness.gateway_id, queue, checkpoint_store, flaky, harness.device_key)

        for frame in SimulatorSource(frame_count=6, realtime=False).frames():
            queue.enqueue(harness.gateway_state.build_and_sign(frame))

        print(f"[info] network offline; queue depth after 6 frames = {queue.depth()}")
        result = drainer.drain_once()
        print(f"[info] drain attempt while offline: transport_error={result.transport_error!r}, queue depth still = {queue.depth()}")
        offline_ok = result.transport_error is not None and queue.depth() == 6

        flaky.online = True
        print("[info] network reconnected")
        total_accepted = 0
        while queue.depth() > 0:
            result = drainer.drain_once()
            total_accepted += result.accepted
            if result.transport_error or result.attempted == 0:
                break
        print(f"[info] after reconnect: accepted={total_accepted}, queue depth = {queue.depth()}")
        reconnect_ok = total_accepted == 6 and queue.depth() == 0 and harness.trusted_store.count() == 6

        ok = offline_ok and reconnect_ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] outage_reconnect: offline_ok={offline_ok}, reconnect_ok={reconnect_ok}")
        queue.close()
        checkpoint_store.close()
        real_transport.close()

    shutil.rmtree(tmp, ignore_errors=True)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
