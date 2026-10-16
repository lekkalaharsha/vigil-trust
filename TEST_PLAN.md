# Test Plan

## Levels

| Level | Location | Purpose |
|---|---|---|
| Unit | `tests/unit/` | Pure-logic correctness: canonical serialization determinism, COSE sign/verify, chain math, Merkle tree, queue persistence, device registry, quarantine store, acquisition source parsing/determinism, API health |
| Integration | `tests/integration/` | Real wiring across module boundaries: edge sign -> queue -> HTTPS transport -> backend verify -> trusted store, over a real FastAPI app (via `fastapi.testclient.TestClient`, which drives the actual ASGI app, not a mock) |
| Security | `tests/security/` | All 10 required attack-lab scenarios as pytest assertions, against the same harness as integration tests |
| Hardware | `tests/hardware/` | Explicitly marked `NOT RUN - HARDWARE REQUIRED` where no board/adapter exists; still verifies the *absence* produces a clear error, not fake success |

Standalone equivalents of the security scenarios also exist as runnable
scripts in `attack_lab/*.py` (see DEMO_SCRIPT.md) for live demonstration
without reading test code.

## Pass conditions (mirrors VIGIL_TRUST_Implementation_SOP.md section 7 / 16.2)

| Test | Pass condition | Covered by |
|---|---|---|
| Normal replay | All frames accepted, 0 quarantined | `test_end_to_end.py::test_normal_frames_are_accepted_and_appear_in_trusted_store` |
| Canonical determinism | Same logical event -> identical bytes/digest | `test_canonical.py` |
| Unauthorized identity | `UNKNOWN_DEVICE` | `test_attack_lab.py::test_scenario_1`, `attack_lab/spoof_identity.py` |
| Payload tamper | `SIGNATURE_INVALID` | `test_attack_lab.py::test_scenario_2`, `attack_lab/tamper.py` |
| Replay | `REPLAY` | `test_attack_lab.py::test_scenario_3`, `attack_lab/replay.py` |
| Duplicate | `DUPLICATE` | `test_attack_lab.py::test_scenario_4`, `attack_lab/duplicate.py` |
| Reorder | `OUT_OF_ORDER` / `CHAIN_MISMATCH` | `test_attack_lab.py::test_scenario_5`, `attack_lab/reorder.py` |
| Forged chain hash | `SIGNATURE_INVALID` (attacker cannot re-sign as the device) | `test_attack_lab.py::test_scenario_6` |
| Forged batch root | `BATCH_ROOT_INVALID` | `test_attack_lab.py::test_scenario_7`, `attack_lab/batch_root_forgery.py` |
| Offline/reconnect | Queue grows while offline, drains fully + verifies on reconnect | `test_attack_lab.py::test_scenario_8`, `attack_lab/outage_reconnect.py` |
| Wrong checkpoint | `CHECKPOINT_MISMATCH` | `test_attack_lab.py::test_scenario_9`, `attack_lab/checkpoint_mismatch.py` |
| Revoked device | `DEVICE_REVOKED` | `test_attack_lab.py::test_scenario_10`, `attack_lab/device_revocation.py` |
| DB copy tamper | Chain inconsistency detected | `attack_lab/db_tamper_check.py` (run manually against a corrupted copy, see TEST_RESULTS.md) |
| Queue persistence | Survives process restart | `test_queue_persistence.py::test_queue_survives_restart` |
| Device revocation | Status flips, rejected afterward | `test_device_registry.py::test_revocation` |
| API health | `/health`, `/metrics`, `/devices`, dashboard root all respond | `test_api_health.py` |
| Replay log parsing | Malformed lines raise, comments/blanks ignored | `test_acquisition_sources.py` |
| PCAN without hardware | Clear `PcanUnavailableError`, not a raw traceback | `test_pcan_hardware.py::test_pcan_source_raises_clear_error_without_hardware` |
| UNO Q without hardware | Clear `UnoQBridgeUnavailableError`, not a raw traceback | `test_unoq_hardware.py::test_unoq_source_raises_clear_error_without_hardware` |
| UNO Q Bridge wire protocol (framing, CRC, resync) | Round-trips, corruption detected/resynced, no hardware needed | `test_unoq_protocol.py` (11 tests) |
| UNO Q Bridge protocol C/Python parity | Identical wire bytes for identical logical frames | `firmware/uno_q_mcu/tests/run_host_tests.sh` + manual Python cross-check, see `firmware/uno_q_mcu/tests/README.md` |

## What is intentionally NOT covered by automated tests here

- Real PCAN/UNO Q hardware behavior (no hardware available -- see
  docs/LIMITATIONS.md).
- MQTT transport over a real broker (no Docker/Mosquitto available --
  self-skipping test documents this: `test_mqtt_transport.py`).
- Load/soak testing at a specific target frame rate (only point-in-time
  throughput numbers exist, see BENCHMARK_RESULTS.md).
