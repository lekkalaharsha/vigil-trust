"""Linux SocketCAN acquisition backend via python-can.

STATUS: IMPLEMENTED, NOT HARDWARE-VALIDATED IN THIS ENVIRONMENT. This
sandbox runs on Windows and has no `can0`/SocketCAN interface; this module
has not been exercised against a real Linux SocketCAN device. See
docs/PCAN_SETUP.md for the documented PEAK-over-SocketCAN setup on Linux.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from edge.acquisition.base import AcquisitionSource, CanFrame
from edge.acquisition.pcan import PcanUnavailableError


@dataclass(frozen=True)
class SocketCanConfig:
    channel: str = "can0"
    receive_own_messages: bool = False


class SocketCanSource(AcquisitionSource):
    mode = "socketcan"

    def __init__(self, config: SocketCanConfig | None = None) -> None:
        self._config = config or SocketCanConfig()
        self._bus = None

    def _open_bus(self):
        try:
            import can
        except ImportError as exc:  # pragma: no cover
            raise PcanUnavailableError("python-can is not installed") from exc
        try:
            return can.interface.Bus(
                interface="socketcan",
                channel=self._config.channel,
                receive_own_messages=self._config.receive_own_messages,
            )
        except Exception as exc:
            raise PcanUnavailableError(
                f"Could not open SocketCAN interface {self._config.channel!r}. "
                "Is the interface up (`ip link set can0 up type can bitrate 500000`)? "
                "See docs/PCAN_SETUP.md."
            ) from exc

    def frames(self) -> Iterator[CanFrame]:
        if self._bus is None:
            self._bus = self._open_bus()
        try:
            while True:
                msg = self._bus.recv(timeout=1.0)
                if msg is None:
                    continue
                yield CanFrame(
                    timestamp=msg.timestamp,
                    channel=self._config.channel,
                    can_id=msg.arbitration_id,
                    is_extended_id=msg.is_extended_id,
                    is_fd=msg.is_fd,
                    data=bytes(msg.data),
                )
        finally:
            self.close()

    def close(self) -> None:
        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None
