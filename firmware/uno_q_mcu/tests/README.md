# Firmware host tests

`test_bridge_protocol_host.c` builds and runs on a normal host machine (no
Arduino toolchain, no UNO Q board) because `bridge_protocol.c` has no
hardware dependency. This is the only part of `firmware/uno_q_mcu/` that
has actually been compiled and run in this environment.

## Build & run

```bash
cd firmware/uno_q_mcu/tests
gcc -I../bridge_protocol -o test_bridge_protocol_host test_bridge_protocol_host.c ../bridge_protocol/bridge_protocol.c
./test_bridge_protocol_host
```

## Actual captured output (gcc.exe MinGW.org GCC-6.3.0-1, Windows, 2026-10-16)

```
CRC16/CCITT-FALSE("123456789") = 0x29B1 (expected 0x29B1)
[PASS] crc16_known_vector
encoded CAN frame (28 bytes): aa01160040e201002a0000000001000000080102030405060708eaa4
[PASS] can_frame_encoded_length
[PASS] can_frame_start_byte
[PASS] can_frame_type_byte
[PASS] zero_dlc_frame_length
[PASS] over_max_dlc_rejected
encoded health frame (14 bytes): aa0208009f86010003000000a0f3
[PASS] health_frame_type_byte

0 check(s) failed.
```

## Cross-check against the Python reference implementation

The C encoder's output above was compared against
`edge/acquisition/unoq_protocol.py` encoding the identical logical frames:

```bash
.venv/Scripts/python.exe -c "
from edge.acquisition import unoq_protocol as proto
frame = proto.BridgeCanFrame(mcu_timestamp_us=123456, mcu_frame_counter=42,
    can_id=0x100, is_extended_id=False, is_fd=False, data=bytes(range(1, 9)))
print(proto.encode_can_frame(frame).hex())
health = proto.BridgeHealth(uptime_ms=99999, dropped_frame_count=3)
print(proto.encode_health(health).hex())
"
```

Output:

```
aa01160040e201002a0000000001000000080102030405060708eaa4
aa0208009f86010003000000a0f3
```

**Byte-for-byte identical** to the C output above, for both the CAN frame
and the health frame. This confirms the wire format implemented in C
(`bridge_protocol.c`, meant to run on the STM32U585) and the wire format
implemented in Python (`edge/acquisition/unoq_protocol.py`, which runs on
the Linux/QRB2210 side and in the edge gateway process) agree exactly --
the one thing that was actually possible to verify about this firmware
without real UNO Q hardware.

## What this does NOT prove

- That `can_rx.c`/`can_rx.h` correctly drives real STM32U585 CAN hardware
  (no board available -- see docs/UNO_Q_SETUP.md).
- That bytes written to a real Bridge serial link arrive uncorrupted at
  the expected baud rate (the `FrameReassembler` on the Python side is
  designed to resync past corruption, per
  `tests/unit/test_unoq_protocol.py`, but that is a defense, not proof
  nothing will ever go wrong on a real link).
- Timing/latency of the Bridge mechanism itself, which is UNO Q
  board-specific and undocumented without hardware/SDK access.
