"""Arduino UNO Q hardware tests.

STATUS: NOT RUN - HARDWARE REQUIRED for the real serial I/O path. No UNO Q
board is available in this environment. See firmware/uno_q_mcu/README.md
for the firmware and docs/UNO_Q_SETUP.md for the bring-up procedure.

The Bridge wire protocol itself (framing/CRC/encode/decode) is NOT
hardware-dependent and is fully tested in
tests/unit/test_unoq_protocol.py -- only the serial-port I/O exercised
here needs real hardware.
"""

from __future__ import annotations

import pytest

from edge.acquisition.unoq import UnoQBridgeSource, UnoQBridgeUnavailableError


@pytest.mark.skip(reason="NOT RUN - HARDWARE REQUIRED: no Arduino UNO Q board in this environment")
def test_unoq_bridge_receives_frames_from_mcu():
    """Manual procedure (docs/UNO_Q_SETUP.md):
    1. Flash firmware/uno_q_mcu/ onto the board's STM32U585 side.
    2. Connect an external CAN transceiver to an isolated bench, PCAN
       monitoring the same bus as an independent reference (see
       docs/PCAN_SETUP.md).
    3. Point UnoQBridgeConfig.serial_port at the board's actual Bridge
       serial device.
    4. Assert received CanFrame fields match the PCAN reference capture.
    """
    raise NotImplementedError


def test_unoq_source_raises_clear_error_without_hardware():
    """This part IS runnable here: confirms UnoQBridgeSource fails with a
    clear, documented error (not a raw traceback) when no board/serial
    device is present, which is exactly the condition in this sandbox."""
    source = UnoQBridgeSource()
    with pytest.raises(UnoQBridgeUnavailableError):
        next(source.frames())
