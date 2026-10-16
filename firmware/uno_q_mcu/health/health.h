// Health/watchdog reporting state. Pure logic, no hardware dependency --
// host-buildable and tested (firmware/uno_q_mcu/tests/test_health_host.c).
// The actual watchdog *hardware* kick (IWDG/WWDG on STM32U585) is a thin,
// untestable-without-hardware wrapper left as a TODO in health.c.

#ifndef VIGIL_HEALTH_H
#define VIGIL_HEALTH_H

#include <stdint.h>
#include "../bridge_protocol/bridge_protocol.h"

typedef struct {
    uint32_t start_time_ms;
    uint32_t last_report_ms;
    uint32_t report_interval_ms;
} health_state_t;

void health_init(health_state_t *state, uint32_t now_ms, uint32_t report_interval_ms);

// Returns true if a health report is due (now_ms - last_report_ms >=
// report_interval_ms), and if so, updates last_report_ms and fills
// `out_report` with the current bridge_health_t to encode and send.
int health_tick(health_state_t *state, uint32_t now_ms, uint32_t dropped_frame_count,
                 bridge_health_t *out_report);

#endif  // VIGIL_HEALTH_H
