// Host-buildable test for capture_counter.c (no hardware dependency).
// Build: gcc -I../capture_counter -o test_capture_counter_host \
//            test_capture_counter_host.c ../capture_counter/capture_counter.c

#include <stdio.h>
#include "capture_counter.h"

static int failures = 0;
#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("[FAIL] %s\n", msg); failures++; } \
    else { printf("[PASS] %s\n", msg); } \
} while (0)

int main(void) {
    capture_counter_t counter;
    capture_counter_init(&counter);

    CHECK(capture_counter_next(&counter) == 0, "first_value_is_zero");
    CHECK(capture_counter_next(&counter) == 1, "second_value_is_one");
    CHECK(capture_counter_next(&counter) == 2, "third_value_is_two");
    CHECK(capture_counter_dropped_count(&counter) == 0, "no_drops_recorded_yet");

    capture_counter_record_drop(&counter);
    capture_counter_record_drop(&counter);
    CHECK(capture_counter_dropped_count(&counter) == 2, "drops_recorded");
    // Recording a drop must not perturb the sequence counter itself.
    CHECK(capture_counter_next(&counter) == 3, "sequence_unaffected_by_drop_recording");

    // Wraparound: force next_value right up to UINT32_MAX and confirm it
    // wraps to 0 rather than undefined behavior or a crash.
    capture_counter_t wrap_counter;
    capture_counter_init(&wrap_counter);
    wrap_counter.next_value = 0xFFFFFFFFu;
    CHECK(capture_counter_next(&wrap_counter) == 0xFFFFFFFFu, "pre_wrap_value");
    CHECK(capture_counter_next(&wrap_counter) == 0, "wraps_to_zero");

    printf("\n%d check(s) failed.\n", failures);
    return failures == 0 ? 0 : 1;
}
