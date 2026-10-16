// VIGIL-TRUST UNO Q MCU firmware -- passive CAN capture + Bridge forwarding.
//
// STATUS: NOT_IMPLEMENTED / HARDWARE_PENDING overall. This sketch has NOT
// been compiled under the Arduino IDE/CLI or flashed to a real Arduino UNO
// Q board in this environment (no board or Arduino Core toolchain for this
// board was available). The hardware-independent pieces it wires together
// (bridge_protocol, capture_counter, health) WERE built and tested on a
// host machine -- see firmware/uno_q_mcu/tests/README.md for the actual
// captured output. can_rx.cpp's CAN peripheral access is an unverified
// assumption (Arduino_CAN API) -- see can_rx/can_rx.h.
//
// Safety: this sketch contains NO transmit path onto the CAN bus anywhere.
// It only ever calls can_rx_poll() (receive) and forwards frames over the
// Bridge serial link to the Linux side. Do not add a transmit function
// without updating docs/THREAT_MODEL.md and getting explicit sign-off --
// see CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 3.

#include "can_rx/can_rx.h"
#include "capture_counter/capture_counter.h"
#include "health/health.h"
#include "bridge_protocol/bridge_protocol.h"

// --- Configuration -----------------------------------------------------

static const uint32_t CAN_BITRATE = 500000;
static const uint32_t HEALTH_REPORT_INTERVAL_MS = 5000;
static const unsigned long BRIDGE_SERIAL_BAUD = 115200;

// --- State ---------------------------------------------------------------

static capture_counter_t g_capture_counter;
static health_state_t g_health_state;
static uint8_t g_wire_buffer[BRIDGE_MAX_FRAME_SIZE];

void setup() {
    // The Bridge link: per firmware/uno_q_mcu/README.md this is the
    // MCU<->Linux Bridge mechanism. Modeled here as a serial port because
    // that is the most common Arduino Core Bridge transport and matches
    // edge/acquisition/unoq.py's assumption (DEFAULT_SERIAL_PORT) --
    // THIS MUST BE CONFIRMED against the real UNO Q Bridge API before
    // trusting it; if the actual mechanism is shared memory or an RPC
    // call instead of a byte stream, only this Serial1.begin()/write()
    // usage needs to change, not the framing in bridge_protocol.c.
    Serial1.begin(BRIDGE_SERIAL_BAUD);

    can_rx_config_t can_config;
    can_config.bitrate = CAN_BITRATE;
    can_config.listen_only = true;  // passive by design, see file header

    if (!can_rx_init(&can_config)) {
        // HARDWARE_PENDING: can_rx_init's real body does not exist yet
        // (can_rx.cpp is an unverified sketch against Arduino_CAN). If/when
        // it is implemented and this fails on real hardware, report it
        // over the health channel rather than silently proceeding as if
        // CAN were working.
        bridge_health_t failure_report = {0, 0xFFFFFFFF};  // sentinel: init failed
        size_t n = bridge_encode_health(&failure_report, g_wire_buffer, sizeof(g_wire_buffer));
        if (n > 0) {
            Serial1.write(g_wire_buffer, n);
        }
    }

    capture_counter_init(&g_capture_counter);
    health_init(&g_health_state, millis(), HEALTH_REPORT_INTERVAL_MS);
}

void loop() {
    bridge_can_frame_t frame;
    if (can_rx_poll(&frame)) {
        frame.mcu_timestamp_us = micros();
        frame.mcu_frame_counter = capture_counter_next(&g_capture_counter);

        size_t n = bridge_encode_can_frame(&frame, g_wire_buffer, sizeof(g_wire_buffer));
        if (n > 0) {
            Serial1.write(g_wire_buffer, n);
        } else {
            // Encoding failed (dlc out of range) -- count as a drop rather
            // than forwarding a malformed frame.
            capture_counter_record_drop(&g_capture_counter);
        }
    }

    bridge_health_t health_report;
    if (health_tick(&g_health_state, millis(),
                     capture_counter_dropped_count(&g_capture_counter), &health_report)) {
        size_t n = bridge_encode_health(&health_report, g_wire_buffer, sizeof(g_wire_buffer));
        if (n > 0) {
            Serial1.write(g_wire_buffer, n);
        }
    }

    // TODO(HARDWARE_PENDING): kick the independent watchdog here once
    // health.c's watchdog TODO is implemented against real hardware.
}
