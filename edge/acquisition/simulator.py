"""Deterministic synthetic CAN traffic generator.

Given a fixed seed and profile, produces an identical sequence of frames on
every run (tests/unit/test_simulator.py asserts this). Not a claim about any
real vehicle's CAN bus layout.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Iterator

from edge.acquisition.base import AcquisitionSource, CanFrame


@dataclass(frozen=True)
class SimulatedSignal:
    can_id: int
    period_s: float
    dlc: int = 8


DEFAULT_SIGNALS: tuple[SimulatedSignal, ...] = (
    SimulatedSignal(can_id=0x100, period_s=0.1, dlc=8),  # engine speed
    SimulatedSignal(can_id=0x101, period_s=0.2, dlc=8),  # wheel speed
    SimulatedSignal(can_id=0x200, period_s=0.5, dlc=8),  # body status
)


class SimulatorSource(AcquisitionSource):
    mode = "simulator"

    def __init__(
        self,
        channel: str = "sim0",
        signals: tuple[SimulatedSignal, ...] = DEFAULT_SIGNALS,
        seed: int = 1337,
        frame_count: int | None = 200,
        realtime: bool = False,
    ) -> None:
        self._channel = channel
        self._signals = signals
        self._seed = seed
        self._frame_count = frame_count
        self._realtime = realtime

    def frames(self) -> Iterator[CanFrame]:
        rng = random.Random(self._seed)
        counters = {s.can_id: 0 for s in self._signals}
        sim_time = 0.0
        produced = 0
        # Deterministic schedule: advance in fixed 0.1s ticks and emit any
        # signal whose period has elapsed.
        tick = 0.1
        next_due = {s.can_id: 0.0 for s in self._signals}
        while self._frame_count is None or produced < self._frame_count:
            due_now = [s for s in self._signals if next_due[s.can_id] <= sim_time + 1e-9]
            for signal in due_now:
                counters[signal.can_id] = (counters[signal.can_id] + 1) % 256
                payload = bytes(
                    [counters[signal.can_id]] + [rng.randrange(256) for _ in range(signal.dlc - 1)]
                )
                yield CanFrame(
                    timestamp=sim_time,
                    channel=self._channel,
                    can_id=signal.can_id,
                    is_extended_id=signal.can_id > 0x7FF,
                    is_fd=False,
                    data=payload,
                )
                produced += 1
                next_due[signal.can_id] = sim_time + signal.period_s
                if self._frame_count is not None and produced >= self._frame_count:
                    return
            if self._realtime:
                time.sleep(tick)
            sim_time = round(sim_time + tick, 6)
