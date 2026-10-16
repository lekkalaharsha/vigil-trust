#include "health.h"

void health_init(health_state_t *state, uint32_t now_ms, uint32_t report_interval_ms) {
    state->start_time_ms = now_ms;
    state->last_report_ms = now_ms;
    state->report_interval_ms = report_interval_ms;
}

int health_tick(health_state_t *state, uint32_t now_ms, uint32_t dropped_frame_count,
                 bridge_health_t *out_report) {
    // Unsigned subtraction handles millis() wraparound correctly as long as
    // the wrap period is much larger than report_interval_ms (true for a
    // uint32_t ms counter: ~49.7 days).
    if ((uint32_t)(now_ms - state->last_report_ms) < state->report_interval_ms) {
        return 0;
    }
    state->last_report_ms = now_ms;
    out_report->uptime_ms = (uint32_t)(now_ms - state->start_time_ms);
    out_report->dropped_frame_count = dropped_frame_count;
    return 1;
}

// TODO(HARDWARE_PENDING): kick the STM32U585 independent watchdog (IWDG)
// here once this is built against the real board's HAL/Zephyr watchdog
// API. Left undone rather than guessed, since getting this wrong (e.g.
// wrong timeout register) is worse than not having it -- see
// docs/UNO_Q_SETUP.md.
