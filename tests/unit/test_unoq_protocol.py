"""Pure-logic tests for the UNO Q Bridge wire protocol
(edge/acquisition/unoq_protocol.py). No hardware required -- this is the
one piece of the UNO Q path that can be fully tested in this environment;
see docs/LIMITATIONS.md for what still requires real hardware."""

from __future__ import annotations

import pytest

from edge.acquisition import unoq_protocol as proto


def test_crc16_known_vector():
    # CRC-16/CCITT-FALSE("123456789") == 0x29B1 is the standard check value
    # for this exact parameterization (poly 0x1021, init 0xFFFF).
    assert proto.crc16_ccitt_false(b"123456789") == 0x29B1


def test_can_frame_round_trip():
    frame = proto.BridgeCanFrame(
        mcu_timestamp_us=123456,
        mcu_frame_counter=42,
        can_id=0x100,
        is_extended_id=False,
        is_fd=False,
        data=b"\x01\x02\x03\x04\x05\x06\x07\x08",
    )
    wire = proto.encode_can_frame(frame)
    reassembler = proto.FrameReassembler()
    frames = reassembler.feed(wire)
    assert len(frames) == 1
    frame_type, payload = frames[0]
    assert frame_type == proto.FRAME_TYPE_CAN
    decoded = proto.decode_can_payload(payload)
    assert decoded == frame


def test_extended_id_and_fd_flags_round_trip():
    frame = proto.BridgeCanFrame(
        mcu_timestamp_us=1, mcu_frame_counter=1, can_id=0x1ABCDEF0,
        is_extended_id=True, is_fd=True, data=b"\xff" * 16,
    )
    wire = proto.encode_can_frame(frame)
    _, payload = proto.FrameReassembler().feed(wire)[0]
    decoded = proto.decode_can_payload(payload)
    assert decoded.is_extended_id is True
    assert decoded.is_fd is True
    assert decoded.can_id == 0x1ABCDEF0


def test_zero_length_data_round_trip():
    frame = proto.BridgeCanFrame(
        mcu_timestamp_us=0, mcu_frame_counter=0, can_id=0x200,
        is_extended_id=False, is_fd=False, data=b"",
    )
    wire = proto.encode_can_frame(frame)
    _, payload = proto.FrameReassembler().feed(wire)[0]
    assert proto.decode_can_payload(payload) == frame


def test_dlc_over_max_rejected():
    frame = proto.BridgeCanFrame(
        mcu_timestamp_us=0, mcu_frame_counter=0, can_id=0x1,
        is_extended_id=False, is_fd=False, data=b"\x00" * 65,
    )
    with pytest.raises(proto.ProtocolError):
        proto.encode_can_frame(frame)


def test_health_frame_round_trip():
    health = proto.BridgeHealth(uptime_ms=99999, dropped_frame_count=3)
    wire = proto.encode_health(health)
    frame_type, payload = proto.FrameReassembler().feed(wire)[0]
    assert frame_type == proto.FRAME_TYPE_HEALTH
    assert proto.decode_health_payload(payload) == health


def test_reassembler_handles_multiple_frames_in_one_chunk():
    frame1 = proto.BridgeCanFrame(0, 0, 0x1, False, False, b"\x01")
    frame2 = proto.BridgeCanFrame(1, 1, 0x2, False, False, b"\x02")
    wire = proto.encode_can_frame(frame1) + proto.encode_can_frame(frame2)
    frames = proto.FrameReassembler().feed(wire)
    assert len(frames) == 2
    assert proto.decode_can_payload(frames[0][1]) == frame1
    assert proto.decode_can_payload(frames[1][1]) == frame2


def test_reassembler_handles_byte_at_a_time_delivery():
    frame = proto.BridgeCanFrame(5, 5, 0x3, False, False, b"\xaa\xbb")
    wire = proto.encode_can_frame(frame)
    reassembler = proto.FrameReassembler()
    collected = []
    for byte in wire:
        collected.extend(reassembler.feed(bytes([byte])))
    assert len(collected) == 1
    assert proto.decode_can_payload(collected[0][1]) == frame


def test_reassembler_resyncs_past_corrupted_frame():
    good_frame = proto.BridgeCanFrame(0, 0, 0x4, False, False, b"\x01\x02")
    wire = proto.encode_can_frame(good_frame)
    corrupted = bytearray(wire)
    corrupted[-1] ^= 0xFF  # flip a CRC byte
    stream = bytes(corrupted) + proto.encode_can_frame(good_frame)

    reassembler = proto.FrameReassembler()
    frames = reassembler.feed(stream)
    # The corrupted frame is dropped; the second, valid frame still comes through.
    assert len(frames) == 1
    assert proto.decode_can_payload(frames[0][1]) == good_frame


def test_reassembler_resyncs_past_garbage_prefix():
    frame = proto.BridgeCanFrame(0, 0, 0x5, False, False, b"\x09")
    stream = b"\x00\x11\x22garbage" + proto.encode_can_frame(frame)
    frames = proto.FrameReassembler().feed(stream)
    assert len(frames) == 1
    assert proto.decode_can_payload(frames[0][1]) == frame


def test_decode_can_payload_rejects_dlc_mismatch():
    with pytest.raises(proto.ProtocolError):
        proto.decode_can_payload(b"\x00" * proto._CAN_PAYLOAD_PREFIX_SIZE + b"only-one-byte-but-dlc-says-more")
