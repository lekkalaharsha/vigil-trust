"""Replay CAN frames from a recorded log file.

Log format (one frame per line, matches scripts/dev data fixtures):

    <timestamp_seconds> <hex_can_id> <hex_payload>
    0.000 0x100 1020304050607080

Lines starting with '#' are comments and are ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from edge.acquisition.base import AcquisitionSource, CanFrame


class ReplayParseError(ValueError):
    pass


def parse_line(line: str) -> tuple[float, int, bytes] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    parts = stripped.split()
    if len(parts) != 3:
        raise ReplayParseError(f"expected 3 fields, got {len(parts)}: {line!r}")
    ts_str, id_str, data_str = parts
    try:
        timestamp = float(ts_str)
        can_id = int(id_str, 16)
        data = bytes.fromhex(data_str)
    except ValueError as exc:
        raise ReplayParseError(f"malformed replay line {line!r}: {exc}") from exc
    return timestamp, can_id, data


class ReplaySource(AcquisitionSource):
    mode = "replay"

    def __init__(self, log_path: Path | str, channel: str = "replay0") -> None:
        self._log_path = Path(log_path)
        self._channel = channel

    def frames(self) -> Iterator[CanFrame]:
        with self._log_path.open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                try:
                    parsed = parse_line(line)
                except ReplayParseError as exc:
                    raise ReplayParseError(f"{self._log_path}:{lineno}: {exc}") from exc
                if parsed is None:
                    continue
                timestamp, can_id, data = parsed
                yield CanFrame(
                    timestamp=timestamp,
                    channel=self._channel,
                    can_id=can_id,
                    is_extended_id=can_id > 0x7FF,
                    is_fd=False,
                    data=data,
                )
