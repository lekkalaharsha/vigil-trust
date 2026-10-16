"""Common CAN acquisition contract. All acquisition backends (simulator,
replay, pcan, socketcan, unoq) produce the same CanFrame shape so the rest
of the edge pipeline (trust envelope construction) never has to know which
backend produced a frame.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class CanFrame:
    timestamp: float
    channel: str
    can_id: int
    is_extended_id: bool
    is_fd: bool
    data: bytes

    @property
    def dlc(self) -> int:
        return len(self.data)


class AcquisitionSource(ABC):
    """Passive-only CAN acquisition source.

    No implementation of this interface may expose a transmit/send method.
    Per CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 3, the default CAN behavior
    is receive-only.
    """

    mode: str = "unknown"

    @abstractmethod
    def frames(self) -> Iterator[CanFrame]:
        """Yield frames in capture order. Implementations should be generators."""

    def close(self) -> None:  # pragma: no cover - optional override
        return None

    def __enter__(self) -> "AcquisitionSource":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
