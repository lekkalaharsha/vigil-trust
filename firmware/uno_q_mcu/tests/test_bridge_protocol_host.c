// Host-buildable (no Arduino toolchain, no hardware) test of
// bridge_protocol.c. This is the one piece of the firmware that was
// actually compiled and run in this environment -- see
// firmware/uno_q_mcu/tests/README.md for the captured output. It exists
// specifically to prove the C wire format matches
// edge/acquisition/unoq_protocol.py byte-for-byte, since that is the only
// part of the MCU firmware checkable without real UNO Q hardware.
//
// Build & run:
//   gcc -I../bridge_protocol -o test_bridge_protocol_host \
//       test_bridge_protocol_host.c ../bridge_protocol/bridge_protocol.c
//   ./test_bridge_protocol_host

#include <stdio.h>
#include <string.h>
#include "bridge_protocol.h"

static int failures = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { \
        printf("[FAIL] %s\n", msg); \
        failures++; \
    } else { \
        printf("[PASS] %s\n", msg); \
    } \
} while (0)

static void print_hex(const char *label, const uint8_t *buf, size_t len) {
    printf("%s (%zu bytes): ", label, len);
    for (size_t i = 0; i < len; i++) {
        printf("%02x", buf[i]);
    }
    printf("\n");
}

int main(void) {
    // CRC-16/CCITT-FALSE("123456789") == 0x29B1 is the standard published
    // check value for this exact parameterization. This is the same
    // assertion made in tests/unit/test_unoq_protocol.py::test_crc16_known_vector.
    uint16_t crc = bridge_crc16_ccitt_false((const uint8_t *)"123456789", 9);
    printf("CRC16/CCITT-FALSE(\"123456789\") = 0x%04X (expected 0x29B1)\n", crc);
    CHECK(crc == 0x29B1, "crc16_known_vector");

    // Encode a CAN frame identical to the one used in
    // tests/unit/test_unoq_protocol.py::test_can_frame_round_trip and print
    // the wire bytes, so they can be diffed against the Python encoder's
    // output for the same logical frame (see
    // firmware/uno_q_mcu/tests/README.md for that cross-check).
    bridge_can_frame_t frame = {
        .mcu_timestamp_us = 123456,
        .mcu_frame_counter = 42,
        .can_id = 0x100,
        .flags = 0,
        .dlc = 8,
        .data = {1, 2, 3, 4, 5, 6, 7, 8},
    };
    uint8_t out[BRIDGE_MAX_FRAME_SIZE];
    size_t n = bridge_encode_can_frame(&frame, out, sizeof(out));
    print_hex("encoded CAN frame", out, n);
    CHECK(n == 1 + BRIDGE_HEADER_SIZE + BRIDGE_CAN_PAYLOAD_PREFIX_SIZE + frame.dlc + BRIDGE_CRC_SIZE,
          "can_frame_encoded_length");
    CHECK(out[0] == BRIDGE_START_BYTE, "can_frame_start_byte");
    CHECK(out[1] == BRIDGE_FRAME_TYPE_CAN, "can_frame_type_byte");

    // Zero-dlc frame.
    bridge_can_frame_t empty_frame = {
        .mcu_timestamp_us = 0, .mcu_frame_counter = 0, .can_id = 0x200,
        .flags = 0, .dlc = 0, .data = {0},
    };
    uint8_t out2[BRIDGE_MAX_FRAME_SIZE];
    size_t n2 = bridge_encode_can_frame(&empty_frame, out2, sizeof(out2));
    CHECK(n2 == 1 + BRIDGE_HEADER_SIZE + BRIDGE_CAN_PAYLOAD_PREFIX_SIZE + BRIDGE_CRC_SIZE,
          "zero_dlc_frame_length");

    // Over-max dlc must be rejected (returns 0), matching
    // edge/acquisition/unoq_protocol.py::ProtocolError on the Python side.
    bridge_can_frame_t bad_frame = {
        .mcu_timestamp_us = 0, .mcu_frame_counter = 0, .can_id = 1,
        .flags = 0, .dlc = BRIDGE_MAX_DLC + 1, .data = {0},
    };
    uint8_t out3[BRIDGE_MAX_FRAME_SIZE];
    size_t n3 = bridge_encode_can_frame(&bad_frame, out3, sizeof(out3));
    CHECK(n3 == 0, "over_max_dlc_rejected");

    // Health frame.
    bridge_health_t health = { .uptime_ms = 99999, .dropped_frame_count = 3 };
    uint8_t out4[64];
    size_t n4 = bridge_encode_health(&health, out4, sizeof(out4));
    print_hex("encoded health frame", out4, n4);
    CHECK(out4[1] == BRIDGE_FRAME_TYPE_HEALTH, "health_frame_type_byte");

    printf("\n%d check(s) failed.\n", failures);
    return failures == 0 ? 0 : 1;
}
