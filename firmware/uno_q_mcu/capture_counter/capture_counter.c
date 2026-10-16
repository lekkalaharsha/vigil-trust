#include "capture_counter.h"

void capture_counter_init(capture_counter_t *counter) {
    counter->next_value = 0;
    counter->dropped_frame_count = 0;
    counter->has_previous = false;
    counter->previous_value = 0;
}

uint32_t capture_counter_next(capture_counter_t *counter) {
    const uint32_t value = counter->next_value;
    counter->previous_value = value;
    counter->has_previous = true;
    counter->next_value = value + 1;  // uint32_t wraps to 0 after UINT32_MAX, defined behavior
    return value;
}

void capture_counter_record_drop(capture_counter_t *counter) {
    counter->dropped_frame_count++;
}

uint32_t capture_counter_dropped_count(const capture_counter_t *counter) {
    return counter->dropped_frame_count;
}
