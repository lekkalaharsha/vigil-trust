"""Arduino UNO Q MCU Bridge acquisition adapter.

STATUS: wire protocol and framing (edge/acquisition/unoq_protocol.py) are
IMPLEMENTED and unit-tested without hardware
(tests/unit/test_unoq_protocol.py). This module's actual serial I/O path
is IMPLEMENTED but NOT HARDWARE-VALIDATED: no Arduino UNO Q board was
available in this environment to confirm the MCU firmware
(firmware/uno_q_mcu/) actually produces bytes this class can read, or that
the serial device path/baud rate assumptions below match the real Bridge
link. Do not treat this as a tested hardware integration until run against
real hardware per docs/UNO_Q_SETUP.md.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator

from edge.acquisition.base import AcquisitionSource, CanFrame
from edge.acquisition.unoq_protocol import (
    FRAME_TYPE_CAN,
    FRAME_TYPE_HEALTH,
    FrameReassembler,
    ProtocolError,
    decode_can_payload,
    decode_health_payload,
)

logger = logging.getLogger("vigil.edge.acquisition.unoq")

DEFAULT_SERIAL_PORT = "/dev/ttyACM0"
DEFAULT_BAUD_RATE = 115200
READ_CHUNK_SIZE = 4096
READ_TIMEOUT_S = 1.0


class UnoQBridgeUnavailableError(RuntimeError):
    """Raised when the Bridge serial link cannot be opened (board not
    connected, wrong port, pyserial not installed, permission denied)."""


@dataclass(frozen=True)
class UnoQBridgeConfig:
    serial_port: str = DEFAULT_SERIAL_PORT
    baud_rate: int = DEFAULT_BAUD_RATE
    channel_name: str = "unoq0"


class UnoQBridgeSource(AcquisitionSource):
    mode = "unoq"

    def __init__(self, config: UnoQBridgeConfig | None = None) -> None:
        self._config = config or UnoQBridgeConfig()
        self._serial = None
        self._reassembler = FrameReassembler()

    def _open_serial(self):
        try:
            import serial  # pyserial
        except ImportError as exc:  # pragma: no cover - dependency pinned in pyproject
            raise UnoQBridgeUnavailableError("pyserial is not installed") from exc
        try:
            return serial.Serial(
                port=self._config.serial_port,
                baudrate=self._config.baud_rate,
                timeout=READ_TIMEOUT_S,
            )
        except Exception as exc:
            raise UnoQBridgeUnavailableError(
                f"Could not open UNO Q Bridge serial port {self._config.serial_port!r} "
                f"at {self._config.baud_rate} baud. Is the board connected and is this "
                "the correct device path? See docs/UNO_Q_SETUP.md. "
                f"(underlying error: {exc})"
            ) from exc

    def frames(self) -> Iterator[CanFrame]:
        if self._serial is None:
            self._serial = self._open_serial()
        try:
            while True:
                chunk = self._serial.read(READ_CHUNK_SIZE)
                if not chunk:
                    continue  # read timeout, no data available yet -- not an error
                for frame_type, payload in self._reassembler.feed(chunk):
                    parsed = self._handle_frame(frame_type, payload)
                    if parsed is not None:
                        yield parsed
        finally:
            self.close()

    def _handle_frame(self, frame_type: int, payload: bytes) -> CanFrame | None:
        if frame_type == FRAME_TYPE_CAN:
            try:
                bridge_frame = decode_can_payload(payload)
            except ProtocolError as exc:
                logger.warning("dropping malformed CAN bridge frame: %s", exc)
                return None
            return CanFrame(
                # mcu_timestamp_us is the MCU's own monotonic clock, not wall
                # time -- see docs/LIMITATIONS.md / README.md timestamp rules.
                # Converting to seconds here only for CanFrame's float
                # contract; callers must not assume this is wall-clock time.
                timestamp=bridge_frame.mcu_timestamp_us / 1_000_000.0,
                channel=self._config.channel_name,
                can_id=bridge_frame.can_id,
                is_extended_id=bridge_frame.is_extended_id,
                is_fd=bridge_frame.is_fd,
                data=bridge_frame.data,
            )
        if frame_type == FRAME_TYPE_HEALTH:
            try:
                health = decode_health_payload(payload)
            except ProtocolError as exc:
                logger.warning("dropping malformed health bridge frame: %s", exc)
                return None
            logger.info(
                "UNO Q MCU health: uptime_ms=%d dropped_frame_count=%d",
                health.uptime_ms, health.dropped_frame_count,
            )
            return None
        logger.warning("unknown bridge frame_type=0x%02x, ignoring", frame_type)
        return None

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
