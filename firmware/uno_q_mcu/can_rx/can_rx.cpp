// HARDWARE_PENDING implementation sketch against the Arduino_CAN library
// API surface (CanMsg / ArduinoCAN::begin / ArduinoCAN::read, per
// https://github.com/arduino-libraries/Arduino_CAN). NOT compiled or
// tested against real Arduino Core / UNO Q hardware in this environment --
// see can_rx.h's header comment for why, and docs/UNO_Q_SETUP.md for what
// must be verified before this is trusted.
//
// If the UNO Q board support package turns out to expose CAN differently
// (e.g. a Zephyr-native `struct can_frame` / `can_add_rx_filter` API
// instead of Arduino_CAN), this file's *body* needs to change, but
// can_rx.h's `can_rx_init`/`can_rx_poll` contract should not have to --
// that boundary is deliberately kept narrow for exactly this reason.

#include "can_rx.h"

#if defined(ARDUINO) && __has_include(<Arduino_CAN.h>)
#define VIGIL_HAVE_ARDUINO_CAN 1
#include <Arduino_CAN.h>
#else
#define VIGIL_HAVE_ARDUINO_CAN 0
#endif

#if VIGIL_HAVE_ARDUINO_CAN

bool can_rx_init(const can_rx_config_t *config) {
    // Arduino_CAN's CanBitRate enum only offers discrete standard rates;
    // map the requested numeric bitrate onto the closest supported one.
    // TODO(HARDWARE_PENDING): confirm Arduino_CAN exposes a listen-only
    // mode flag on this board -- CAN.begin() may not take one on every
    // Arduino_CAN target. If it doesn't, listen-only must be enforced by
    // never calling any transmit API (which this file already does, by
    // simply not providing one) rather than by a peripheral register.
    CanBitRate rate;
    switch (config->bitrate) {
        case 125000:  rate = CanBitRate::BR_125k;  break;
        case 250000:  rate = CanBitRate::BR_250k;  break;
        case 500000:  rate = CanBitRate::BR_500k;  break;
        case 1000000: rate = CanBitRate::BR_1000k; break;
        default:      rate = CanBitRate::BR_500k;  break;
    }
    return CAN.begin(rate);
}

bool can_rx_poll(bridge_can_frame_t *out_frame) {
    if (!CAN.available()) {
        return false;
    }
    CanMsg const msg = CAN.read();

    out_frame->can_id = msg.id;
    out_frame->flags = 0;
    if (msg.isExtendedId()) {
        out_frame->flags |= BRIDGE_FLAG_EXTENDED_ID;
    }
    // Arduino_CAN's CanMsg does not currently model CAN FD; if/when this
    // board's library adds FD support, set BRIDGE_FLAG_FD here too.
    out_frame->dlc = msg.data_length > BRIDGE_MAX_DLC ? BRIDGE_MAX_DLC : msg.data_length;
    for (uint8_t i = 0; i < out_frame->dlc; i++) {
        out_frame->data[i] = msg.data[i];
    }
    // mcu_timestamp_us and mcu_frame_counter are intentionally NOT set
    // here -- the caller (vigil_uno_q_firmware.ino) stamps those
    // immediately after this call returns, using its own monotonic clock
    // and capture_counter_t, so there is exactly one place in the firmware
    // that assigns them.
    return true;
}

#else  // !VIGIL_HAVE_ARDUINO_CAN

// Host/non-Arduino build (e.g. accidentally compiled outside the Arduino
// IDE/CLI): fail loudly at compile time rather than silently producing a
// no-op stub that looks like it works.
#error "can_rx.cpp requires building under the Arduino Core for a board " \
       "that provides Arduino_CAN.h. This file is HARDWARE_PENDING and " \
       "has not been built against real Arduino Core/UNO Q toolchain in " \
       "this environment -- see docs/UNO_Q_SETUP.md."

#endif  // VIGIL_HAVE_ARDUINO_CAN
