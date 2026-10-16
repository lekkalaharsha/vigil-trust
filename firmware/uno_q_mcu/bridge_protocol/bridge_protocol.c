// Bridge wire protocol implementation -- MCU side. Plain C, no Arduino
// dependency, so it builds and is testable on a host machine (see
// firmware/uno_q_mcu/tests/test_bridge_protocol_host.c) as well as under
// the Arduino Core build. Mirrors edge/acquisition/unoq_protocol.py.

#include "bridge_protocol.h"

uint16_t bridge_crc16_ccitt_false(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (uint16_t)((crc << 1) ^ 0x1021);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

static size_t encode_frame(uint8_t frame_type, const uint8_t *payload, size_t payload_len,
                            uint8_t *out, size_t out_capacity) {
    const size_t total_len = 1 + BRIDGE_HEADER_SIZE + payload_len + BRIDGE_CRC_SIZE;
    if (out_capacity < total_len) {
        return 0;
    }

    size_t pos = 0;
    out[pos++] = BRIDGE_START_BYTE;
    out[pos++] = frame_type;
    out[pos++] = (uint8_t)(payload_len & 0xFF);
    out[pos++] = (uint8_t)((payload_len >> 8) & 0xFF);
    for (size_t i = 0; i < payload_len; i++) {
        out[pos++] = payload[i];
    }

    // CRC covers [frame_type, length_lo, length_hi, payload...] -- i.e.
    // everything written after the START byte so far.
    const uint16_t crc = bridge_crc16_ccitt_false(out + 1, BRIDGE_HEADER_SIZE + payload_len);
    out[pos++] = (uint8_t)(crc & 0xFF);
    out[pos++] = (uint8_t)((crc >> 8) & 0xFF);

    return pos;
}

size_t bridge_encode_can_frame(const bridge_can_frame_t *frame, uint8_t *out, size_t out_capacity) {
    if (frame->dlc > BRIDGE_MAX_DLC) {
        return 0;
    }

    uint8_t payload[BRIDGE_CAN_PAYLOAD_PREFIX_SIZE + BRIDGE_MAX_DLC];
    size_t pos = 0;

    payload[pos++] = (uint8_t)(frame->mcu_timestamp_us & 0xFF);
    payload[pos++] = (uint8_t)((frame->mcu_timestamp_us >> 8) & 0xFF);
    payload[pos++] = (uint8_t)((frame->mcu_timestamp_us >> 16) & 0xFF);
    payload[pos++] = (uint8_t)((frame->mcu_timestamp_us >> 24) & 0xFF);

    payload[pos++] = (uint8_t)(frame->mcu_frame_counter & 0xFF);
    payload[pos++] = (uint8_t)((frame->mcu_frame_counter >> 8) & 0xFF);
    payload[pos++] = (uint8_t)((frame->mcu_frame_counter >> 16) & 0xFF);
    payload[pos++] = (uint8_t)((frame->mcu_frame_counter >> 24) & 0xFF);

    payload[pos++] = (uint8_t)(frame->can_id & 0xFF);
    payload[pos++] = (uint8_t)((frame->can_id >> 8) & 0xFF);
    payload[pos++] = (uint8_t)((frame->can_id >> 16) & 0xFF);
    payload[pos++] = (uint8_t)((frame->can_id >> 24) & 0xFF);

    payload[pos++] = frame->flags;
    payload[pos++] = frame->dlc;

    for (uint8_t i = 0; i < frame->dlc; i++) {
        payload[pos++] = frame->data[i];
    }

    return encode_frame(BRIDGE_FRAME_TYPE_CAN, payload, pos, out, out_capacity);
}

size_t bridge_encode_health(const bridge_health_t *health, uint8_t *out, size_t out_capacity) {
    uint8_t payload[BRIDGE_HEALTH_PAYLOAD_SIZE];
    size_t pos = 0;

    payload[pos++] = (uint8_t)(health->uptime_ms & 0xFF);
    payload[pos++] = (uint8_t)((health->uptime_ms >> 8) & 0xFF);
    payload[pos++] = (uint8_t)((health->uptime_ms >> 16) & 0xFF);
    payload[pos++] = (uint8_t)((health->uptime_ms >> 24) & 0xFF);

    payload[pos++] = (uint8_t)(health->dropped_frame_count & 0xFF);
    payload[pos++] = (uint8_t)((health->dropped_frame_count >> 8) & 0xFF);
    payload[pos++] = (uint8_t)((health->dropped_frame_count >> 16) & 0xFF);
    payload[pos++] = (uint8_t)((health->dropped_frame_count >> 24) & 0xFF);

    return encode_frame(BRIDGE_FRAME_TYPE_HEALTH, payload, pos, out, out_capacity);
}
