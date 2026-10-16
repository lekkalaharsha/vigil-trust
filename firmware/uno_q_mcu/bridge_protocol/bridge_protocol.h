// Bridge wire protocol -- MCU (STM32U585) side.
//
// STATUS: NOT_IMPLEMENTED / HARDWARE_PENDING overall (no UNO Q board was
// available to build or flash this against), but this specific file is a
// byte-for-byte mirror of the Python reference implementation in
// edge/acquisition/unoq_protocol.py, which IS unit-tested
// (tests/unit/test_unoq_protocol.py) and whose test vectors (see
// bridge_protocol_crc16_test_vector() below) this file must keep matching.
// If you change the wire format here, update unoq_protocol.py and its
// tests in the same change, and vice versa.
//
// Frame format (little-endian), one frame per logical message:
//   byte 0:        START (0xAA)
//   byte 1:        frame_type (FRAME_TYPE_CAN=0x01, FRAME_TYPE_HEALTH=0x02)
//   bytes 2-3:     payload_length (uint16_t, little-endian)
//   bytes 4..N:    payload (payload_length bytes)
//   bytes N+1,N+2: CRC16/CCITT-FALSE over [frame_type, length_lo, length_hi, payload...]
//
// CAN frame payload (14 + dlc bytes):
//   bytes 0-3:  mcu_timestamp_us    (uint32_t)
//   bytes 4-7:  mcu_frame_counter   (uint32_t)
//   bytes 8-11: can_id              (uint32_t, low 29 bits significant)
//   byte  12:   flags               (bit0: extended id, bit1: fd)
//   byte  13:   dlc                 (0-64)
//   bytes 14..: data                (exactly dlc bytes)
//
// Health frame payload (8 bytes):
//   bytes 0-3: uptime_ms            (uint32_t)
//   bytes 4-7: dropped_frame_count  (uint32_t)

#ifndef VIGIL_BRIDGE_PROTOCOL_H
#define VIGIL_BRIDGE_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define BRIDGE_START_BYTE     0xAA
#define BRIDGE_FRAME_TYPE_CAN    0x01
#define BRIDGE_FRAME_TYPE_HEALTH 0x02

#define BRIDGE_FLAG_EXTENDED_ID 0x01
#define BRIDGE_FLAG_FD          0x02

#define BRIDGE_MAX_DLC 64

// Header (after START) + CRC overhead, matching unoq_protocol.py's
// _HEADER_SIZE (3: frame_type + 2 length bytes) and _CRC_SIZE (2).
#define BRIDGE_HEADER_SIZE 3
#define BRIDGE_CRC_SIZE    2
#define BRIDGE_CAN_PAYLOAD_PREFIX_SIZE 14  // timestamp(4) + counter(4) + can_id(4) + flags(1) + dlc(1)
#define BRIDGE_HEALTH_PAYLOAD_SIZE 8

// Max total wire frame size this firmware will ever emit: 1 (start) +
// header + CAN prefix + max data + crc.
#define BRIDGE_MAX_FRAME_SIZE (1 + BRIDGE_HEADER_SIZE + BRIDGE_CAN_PAYLOAD_PREFIX_SIZE + BRIDGE_MAX_DLC + BRIDGE_CRC_SIZE)

typedef struct {
    uint32_t mcu_timestamp_us;
    uint32_t mcu_frame_counter;
    uint32_t can_id;
    uint8_t  flags;
    uint8_t  dlc;
    uint8_t  data[BRIDGE_MAX_DLC];
} bridge_can_frame_t;

typedef struct {
    uint32_t uptime_ms;
    uint32_t dropped_frame_count;
} bridge_health_t;

// CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect, no xorout).
// Pure function, no hardware dependency -- see
// firmware/uno_q_mcu/tests/test_bridge_protocol_host.c for a host-buildable
// (non-Arduino) test of this function and the encoders below, matching
// edge/acquisition/unoq_protocol.py::crc16_ccitt_false byte-for-byte.
uint16_t bridge_crc16_ccitt_false(const uint8_t *data, size_t len);

// Encodes a CAN frame into `out` (caller-provided buffer, at least
// BRIDGE_MAX_FRAME_SIZE bytes). Returns the number of bytes written, or 0
// if frame->dlc > BRIDGE_MAX_DLC.
size_t bridge_encode_can_frame(const bridge_can_frame_t *frame, uint8_t *out, size_t out_capacity);

// Encodes a health frame into `out` (caller-provided buffer, at least
// 1 + BRIDGE_HEADER_SIZE + BRIDGE_HEALTH_PAYLOAD_SIZE + BRIDGE_CRC_SIZE
// bytes). Returns the number of bytes written.
size_t bridge_encode_health(const bridge_health_t *health, uint8_t *out, size_t out_capacity);

#endif  // VIGIL_BRIDGE_PROTOCOL_H
