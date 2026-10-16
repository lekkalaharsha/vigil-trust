#!/usr/bin/env bash
# Builds and runs every host-buildable firmware test (no Arduino toolchain,
# no UNO Q hardware required). Mirrors what was actually run and captured
# in this repository -- see README.md in this directory for output.
set -euo pipefail
cd "$(dirname "$0")"

echo "=== bridge_protocol ==="
gcc -I../bridge_protocol -o /tmp/test_bridge_protocol_host \
    test_bridge_protocol_host.c ../bridge_protocol/bridge_protocol.c
/tmp/test_bridge_protocol_host

echo
echo "=== capture_counter ==="
gcc -I../capture_counter -o /tmp/test_capture_counter_host \
    test_capture_counter_host.c ../capture_counter/capture_counter.c
/tmp/test_capture_counter_host

echo
echo "=== health ==="
gcc -I../health -I../bridge_protocol -o /tmp/test_health_host \
    test_health_host.c ../health/health.c ../bridge_protocol/bridge_protocol.c
/tmp/test_health_host

rm -f /tmp/test_bridge_protocol_host /tmp/test_capture_counter_host /tmp/test_health_host
