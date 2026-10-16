"""Wire protocol for the Arduino UNO Q MCU<->Linux Bridge link.

This module is the Linux/Python-side counterpart of the C firmware in
firmware/uno_q_mcu/bridge_protocol/. It is pure parsing/framing logic with
no hardware dependency, so -- unlike the rest of the UNO Q path -- it CAN
be, and is, unit-tested in this environment
(tests/unit/test_unoq_protocol.py) without a real board. What is NOT
tested here is a real MCU actually producing these bytes over a real
serial link; see docs/UNO_Q_SETUP.md.

Frame format (little-endian), one frame per logical message:

    byte 0:      START (0xAA)
    byte 1:      frame_type (FRAME_TYPE_CAN=0x01, FRAME_TYPE_HEALTH=0x02)
    bytes 2-3:   payload_length (uint16, little-endian)
    bytes 4..N:  payload (payload_length bytes)
    bytes N+1,N+2: CRC16/CCITT-FALSE over [frame_type, length_lo, length_hi, payload...]

CAN frame payload (variable length = 14 + dlc bytes, NOT the fixed 64-byte
struct sketched in firmware/uno_q_mcu/README.md -- that struct is the
in-memory MCU representation; this wire encoding only sends the `dlc`
bytes actually present, to keep the serial link efficient):

    bytes 0-3:   mcu_timestamp_us   (uint32)
    bytes 4-7:   mcu_frame_counter  (uint32)
    bytes 8-11:  can_id             (uint32, low 29 bits significant)
    byte  12:    flags              (bit0: extended id, bit1: fd)
    byte  13:    dlc                (0-64)
    bytes 14..:  data               (exactly `dlc` bytes)

Health frame payload (8 bytes):

    bytes 0-3:   uptime_ms          (uint32)
    bytes 4-7:   dropped_frame_count (uint32)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

START_BYTE = 0xAA
FRAME_TYPE_CAN = 0x01
FRAME_TYPE_HEALTH = 0x02

_HEADER_FORMAT = "<BBH"  # start, frame_type, payload_length
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)
_CRC_SIZE = 2
_CAN_PAYLOAD_PREFIX_FORMAT = "<IIIBB"  # timestamp, counter, can_id, flags, dlc
_CAN_PAYLOAD_PREFIX_SIZE = struct.calcsize(_CAN_PAYLOAD_PREFIX_FORMAT)
_HEALTH_PAYLOAD_FORMAT = "<II"
_HEALTH_PAYLOAD_SIZE = struct.calcsize(_HEALTH_PAYLOAD_FORMAT)

FLAG_EXTENDED_ID = 0x01
FLAG_FD = 0x02

MAX_DLC = 64


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class BridgeCanFrame:
    mcu_timestamp_us: int
    mcu_frame_counter: int
    can_id: int
    is_extended_id: bool
    is_fd: bool
    data: bytes

    @property
    def dlc(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class BridgeHealth:
    uptime_ms: int
    dropped_frame_count: int


def crc16_ccitt_false(data: bytes, initial: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect, no xorout).
    Matches the reference implementation used in the C firmware
    (firmware/uno_q_mcu/bridge_protocol/crc16.c) -- see
    tests/unit/test_unoq_protocol.py for cross-checked known test vectors."""
    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode_can_frame(frame: BridgeCanFrame) -> bytes:
    if frame.dlc > MAX_DLC:
        raise ProtocolError(f"dlc {frame.dlc} exceeds MAX_DLC {MAX_DLC}")
    flags = (FLAG_EXTENDED_ID if frame.is_extended_id else 0) | (FLAG_FD if frame.is_fd else 0)
    payload = struct.pack(
        _CAN_PAYLOAD_PREFIX_FORMAT,
        frame.mcu_timestamp_us & 0xFFFFFFFF,
        frame.mcu_frame_counter & 0xFFFFFFFF,
        frame.can_id & 0xFFFFFFFF,
        flags,
        frame.dlc,
    ) + frame.data
    return _encode_frame(FRAME_TYPE_CAN, payload)


def encode_health(health: BridgeHealth) -> bytes:
    payload = struct.pack(_HEALTH_PAYLOAD_FORMAT, health.uptime_ms & 0xFFFFFFFF, health.dropped_frame_count & 0xFFFFFFFF)
    return _encode_frame(FRAME_TYPE_HEALTH, payload)


def _encode_frame(frame_type: int, payload: bytes) -> bytes:
    header_and_payload = struct.pack("<BH", frame_type, len(payload)) + payload
    crc = crc16_ccitt_false(header_and_payload)
    return bytes([START_BYTE]) + header_and_payload + struct.pack("<H", crc)


def decode_can_payload(payload: bytes) -> BridgeCanFrame:
    if len(payload) < _CAN_PAYLOAD_PREFIX_SIZE:
        raise ProtocolError(f"CAN payload too short: {len(payload)} bytes")
    timestamp, counter, can_id, flags, dlc = struct.unpack(
        _CAN_PAYLOAD_PREFIX_FORMAT, payload[:_CAN_PAYLOAD_PREFIX_SIZE]
    )
    data = payload[_CAN_PAYLOAD_PREFIX_SIZE:]
    if len(data) != dlc:
        raise ProtocolError(f"declared dlc={dlc} does not match actual data length={len(data)}")
    if dlc > MAX_DLC:
        raise ProtocolError(f"dlc {dlc} exceeds MAX_DLC {MAX_DLC}")
    return BridgeCanFrame(
        mcu_timestamp_us=timestamp,
        mcu_frame_counter=counter,
        can_id=can_id,
        is_extended_id=bool(flags & FLAG_EXTENDED_ID),
        is_fd=bool(flags & FLAG_FD),
        data=data,
    )


def decode_health_payload(payload: bytes) -> BridgeHealth:
    if len(payload) != _HEALTH_PAYLOAD_SIZE:
        raise ProtocolError(f"health payload must be {_HEALTH_PAYLOAD_SIZE} bytes, got {len(payload)}")
    uptime_ms, dropped = struct.unpack(_HEALTH_PAYLOAD_FORMAT, payload)
    return BridgeHealth(uptime_ms=uptime_ms, dropped_frame_count=dropped)


class FrameReassembler:
    """Feed it raw bytes as they arrive from the serial link; it yields
    (frame_type, payload) tuples for each frame with a valid CRC, and
    silently resynchronizes (scans forward for the next START byte) past
    any corrupted frame instead of getting stuck -- a serial link can lose
    or corrupt bytes, and this must never crash the edge process."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        self._buffer.extend(data)
        frames: list[tuple[int, bytes]] = []
        while True:
            length_before = len(self._buffer)
            frame = self._try_extract_one()
            if frame is not None:
                frames.append(frame)
                continue
            # No frame produced: keep retrying as long as we made progress
            # (e.g. resyncing past a corrupted frame or a garbage prefix);
            # stop only once the buffer is genuinely unchanged, meaning we
            # are waiting on more bytes to arrive.
            if len(self._buffer) == length_before:
                break
        return frames

    def _try_extract_one(self) -> tuple[int, bytes] | None:
        buf = self._buffer
        start = buf.find(START_BYTE)
        if start == -1:
            buf.clear()
            return None
        if start > 0:
            del buf[:start]

        if len(buf) < _HEADER_SIZE:
            return None
        _start, frame_type, length = struct.unpack(_HEADER_FORMAT, bytes(buf[:_HEADER_SIZE]))
        total_len = _HEADER_SIZE + length + _CRC_SIZE
        if len(buf) < total_len:
            return None

        header_and_payload = bytes(buf[1:_HEADER_SIZE + length])
        payload = bytes(buf[_HEADER_SIZE:_HEADER_SIZE + length])
        (received_crc,) = struct.unpack("<H", bytes(buf[_HEADER_SIZE + length:total_len]))
        expected_crc = crc16_ccitt_false(header_and_payload)

        if received_crc != expected_crc:
            # Corrupted frame: drop just the START byte and resync by
            # searching again on the next call, rather than trusting the
            # (possibly corrupted) declared length to skip past it.
            del buf[:1]
            return None

        del buf[:total_len]
        return frame_type, payload
