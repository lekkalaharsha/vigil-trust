"""Hardware-in-the-loop PCAN tests.

STATUS: NOT RUN - HARDWARE REQUIRED. This sandbox has no PEAK PCAN-USB
adapter or driver attached. These tests are skipped unconditionally here;
run them manually on a workstation with the PEAK driver and an adapter
connected, per docs/PCAN_SETUP.md#validating-vigil-pcan-mode.
"""

from __future__ import annotations

import pytest

from edge.acquisition.pcan import PcanSource, PcanUnavailableError


@pytest.mark.skip(reason="NOT RUN - HARDWARE REQUIRED: no PEAK PCAN adapter/driver in this environment")
def test_pcan_source_receives_frames_from_hardware():
    """Manual procedure (docs/PCAN_SETUP.md):
    1. Connect a PCAN-USB adapter with PEAK driver installed.
    2. Set CAN_CHANNEL / CAN_BITRATE env vars to match the bench.
    3. Inject known frames onto the bus (simulator/authorized bench).
    4. Assert received CanFrame fields match the known injected frames.
    """
    raise NotImplementedError


def test_pcan_source_raises_clear_error_without_hardware():
    """This part IS runnable here: confirms PcanSource fails with a clear,
    documented error (not a raw traceback) when no adapter/driver is
    present, which is exactly the condition in this sandbox."""
    source = PcanSource()
    with pytest.raises(PcanUnavailableError):
        next(source.frames())
