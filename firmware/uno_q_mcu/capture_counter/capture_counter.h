// Monotonic per-frame capture counter, independent of CAN ID.
//
// Pure logic, no hardware dependency -- host-buildable and tested, see
// firmware/uno_q_mcu/tests/test_capture_counter_host.c. Purpose: give the
// Linux-side edge pipeline (edge/acquisition/unoq.py) a way to detect
// dropped frames on the Bridge link, independent of and in addition to
// the application-layer `sequence` number edge/trust/envelope.py assigns
// after a frame crosses the Bridge.

#ifndef VIGIL_CAPTURE_COUNTER_H
#define VIGIL_CAPTURE_COUNTER_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t next_value;
    uint32_t dropped_frame_count;
    bool     has_previous;
    uint32_t previous_value;
} capture_counter_t;

void capture_counter_init(capture_counter_t *counter);

// Returns the next counter value to stamp onto an outgoing CAN frame, and
// advances internal state. Wraps at UINT32_MAX back to 0 (the Linux side
// must treat a single large negative jump as a wrap, not a reordering --
// see edge/acquisition/unoq_protocol.py's BridgeCanFrame.mcu_frame_counter
// docstring).
uint32_t capture_counter_next(capture_counter_t *counter);

// Call this when the firmware knows it dropped a frame locally (e.g. an
// internal queue was full) so bridge_health_t.dropped_frame_count
// (bridge_protocol.h) reflects reality instead of silently under-reporting.
void capture_counter_record_drop(capture_counter_t *counter);

uint32_t capture_counter_dropped_count(const capture_counter_t *counter);

#endif  // VIGIL_CAPTURE_COUNTER_H
