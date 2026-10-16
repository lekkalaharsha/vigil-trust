// Host-buildable test for health.c (no hardware dependency).
// Build: gcc -I../health -I../bridge_protocol -o test_health_host \
//            test_health_host.c ../health/health.c ../bridge_protocol/bridge_protocol.c

#include <stdio.h>
#include "health.h"

static int failures = 0;
#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("[FAIL] %s\n", msg); failures++; } \
    else { printf("[PASS] %s\n", msg); } \
} while (0)

int main(void) {
    health_state_t state;
    bridge_health_t report;

    health_init(&state, /*now_ms=*/1000, /*report_interval_ms=*/5000);

    CHECK(health_tick(&state, 2000, 0, &report) == 0, "not_due_yet");
    CHECK(health_tick(&state, 5999, 0, &report) == 0, "still_not_due_just_before_interval");

    int due = health_tick(&state, 6000, 7, &report);
    CHECK(due == 1, "due_at_exactly_interval");
    CHECK(report.uptime_ms == 5000, "uptime_computed_correctly");
    CHECK(report.dropped_frame_count == 7, "dropped_count_passed_through");

    CHECK(health_tick(&state, 6001, 7, &report) == 0, "not_due_again_immediately_after");

    due = health_tick(&state, 11000, 9, &report);
    CHECK(due == 1, "due_again_after_second_interval");
    CHECK(report.uptime_ms == 10000, "uptime_accumulates");

    // millis() wraparound: last_report_ms near UINT32_MAX, now_ms wrapped
    // around to a small value. Unsigned subtraction should still compute a
    // sane elapsed time instead of a huge bogus one.
    health_state_t wrap_state;
    health_init(&wrap_state, 0xFFFFFFFFu - 1000, 2000);
    due = health_tick(&wrap_state, 2000, 0, &report);  // wrapped past 0
    CHECK(due == 1, "due_correctly_across_millis_wraparound");

    printf("\n%d check(s) failed.\n", failures);
    return failures == 0 ? 0 : 1;
}
