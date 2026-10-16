"""PEAK PCAN acquisition backend via python-can.

STATUS: IMPLEMENTED, NOT HARDWARE-VALIDATED IN THIS ENVIRONMENT. This
sandbox has no PCAN-USB adapter or PEAK driver attached, so this module has
only been exercised against python-can's API surface, not real hardware.
See docs/PCAN_SETUP.md for the manual hardware test procedure
(PCAN_SETUP.md#validating-vigil-pcan-mode) that must be run on a workstation
with the PEAK driver and an adapter before this is claimed to work on
hardware.

Configuration (env vars or YAML, matching the architecture doc):

    CAN_INTERFACE=pcan
    CAN_CHANNEL=PCAN_USBBUS1
    CAN_BITRATE=500000
    CAN_FD=false
    CAN_LISTEN_ONLY=true
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from edge.acquisition.base import AcquisitionSource, CanFrame


class PcanUnavailableError(RuntimeError):
    """Raised when the PEAK PCAN driver/adapter is not available on this host."""


@dataclass(frozen=True)
class PcanConfig:
    channel: str = "PCAN_USBBUS1"
    bitrate: int = 500_000
    is_fd: bool = False
    listen_only: bool = True


class PcanSource(AcquisitionSource):
    mode = "pcan"

    def __init__(self, config: PcanConfig | None = None) -> None:
        self._config = config or PcanConfig()
        self._bus = None

    def _open_bus(self):
        try:
            import can  # python-can
        except ImportError as exc:  # pragma: no cover - dependency always installed per pyproject
            raise PcanUnavailableError("python-can is not installed") from exc
        try:
            return can.interface.Bus(
                interface="pcan",
                channel=self._config.channel,
                bitrate=self._config.bitrate,
                fd=self._config.is_fd,
                receive_own_messages=False,
            )
        except Exception as exc:
            # python-can raises can.CanInitializationError or OSError when the
            # PEAK driver/adapter is missing. Surface a clear, documented
            # error instead of a raw traceback -- see architecture doc section 8.
            raise PcanUnavailableError(
                "Could not open PCAN channel "
                f"{self._config.channel!r}. Is the PEAK driver installed and "
                "the adapter connected? See docs/PCAN_SETUP.md."
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
