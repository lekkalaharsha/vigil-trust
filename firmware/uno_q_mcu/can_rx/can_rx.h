// Passive CAN receive -- MCU side.
//
// STATUS: NOT_IMPLEMENTED / HARDWARE_PENDING. Written against the public
// Arduino_CAN library API (the same library Arduino ships for the
// Portenta H7 / GIGA R1's CAN peripherals,
// https://github.com/arduino-libraries/Arduino_CAN), as the most honest
// available assumption for what CAN support on an Arduino Core board
// looks like. Arduino's own UNO Q documentation does not (as of writing)
// confirm whether Arduino_CAN itself, a different wrapper, or direct
// Zephyr CAN driver access is the supported path on the STM32U585 side --
// THIS MUST BE VERIFIED against the actual UNO Q board support package
// before this file is trusted, not assumed from this comment. No UNO Q
// board or SDK was available in this environment to check.
//
// This header/implementation have NOT been compiled against a real
// Arduino Core toolchain in this environment (only the hardware-independent
// files -- bridge_protocol, capture_counter, health -- were actually built
// and run, see firmware/uno_q_mcu/tests/).
//
// Receive-only by design: no transmit function is declared or provided
// anywhere in this file, matching CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md
// rule 3 and VIGIL_TRUST_Research_and_Architecture.md section 14.3.

#ifndef VIGIL_CAN_RX_H
#define VIGIL_CAN_RX_H

#include <stdint.h>
#include <stdbool.h>
#include "../bridge_protocol/bridge_protocol.h"

typedef struct {
    uint32_t bitrate;        // e.g. 500000
    bool     listen_only;    // true: never ACK/arbitrate onto the bus
} can_rx_config_t;

// Initializes the CAN peripheral in listen-only/passive mode. Returns true
// on success. HARDWARE_PENDING: body is a TODO against Arduino_CAN /
// Zephyr CAN APIs, not implemented.
bool can_rx_init(const can_rx_config_t *config);

// Non-blocking poll: if a frame is available, fills `out_frame`'s
// can_id/flags/dlc/data (NOT timestamp/counter -- the caller stamps those,
// see vigil_uno_q_firmware.ino) and returns true. Returns false if nothing
// is available right now. HARDWARE_PENDING: not implemented.
bool can_rx_poll(bridge_can_frame_t *out_frame);

#endif  // VIGIL_CAN_RX_H
