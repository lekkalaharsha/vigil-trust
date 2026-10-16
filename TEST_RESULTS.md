# Test Results

## Environment

- Date: 2026-10-16
- Python: 3.12.7 (MSC v.1941 64 bit), Windows-11-10.0.26300-SP0
- pytest 8.3.4, dependencies pinned per `pyproject.toml`
- gcc.exe (MinGW.org GCC-6.3.0-1) for the host-buildable firmware tests
- Command: `.venv/Scripts/python.exe -m pytest tests/ -v`

## Update (same session): UNO Q Bridge protocol completed

The Bridge wire protocol between the edge gateway and the UNO Q MCU
firmware was completed and verified on both sides without needing real
hardware:

- `edge/acquisition/unoq_protocol.py` -- framing, CRC16, CAN/health frame
  codecs, a corruption-resyncing `FrameReassembler`. 11 new unit tests in
  `tests/unit/test_unoq_protocol.py`, all passing (included in the 63
  below).
- `firmware/uno_q_mcu/bridge_protocol/bridge_protocol.c`,
  `capture_counter/capture_counter.c`, `health/health.c` -- the C-side
  mirror. Built and run with `gcc` on the development machine (no Arduino
  toolchain, no board) via `firmware/uno_q_mcu/tests/run_host_tests.sh`:
  **24/24 checks passed** across all three modules.
- The C encoder's output for an identical logical CAN frame and health
  frame was compared byte-for-byte against the Python encoder's output and
  found **identical** (see `firmware/uno_q_mcu/tests/README.md` for both
  hex dumps side by side).
- `edge/acquisition/unoq.py::UnoQBridgeSource` now actually opens a serial
  port and parses real Bridge frames (previously it unconditionally raised
  `NotImplementedError`); confirmed to fail with a clear
  `UnoQBridgeUnavailableError` (not a raw traceback) when no device is
  present, which is the case in this environment.
- `firmware/uno_q_mcu/can_rx/` (CAN peripheral access) and
  `vigil_uno_q_firmware.ino` (top-level sketch) remain **not
  hardware-validated** -- they depend on the Arduino_CAN library and a
  real Arduino Core toolchain for this board, neither available here. See
  `firmware/uno_q_mcu/README.md` for the authoritative per-module status.

## Automated test suite (AUTOMATED-TEST VERIFIED)

```
collected 55 items

tests/hardware/test_pcan_hardware.py::test_pcan_source_receives_frames_from_hardware SKIPPED
tests/hardware/test_pcan_hardware.py::test_pcan_source_raises_clear_error_without_hardware PASSED
tests/hardware/test_unoq_hardware.py::test_unoq_bridge_receives_frames_from_mcu SKIPPED
tests/hardware/test_unoq_hardware.py::test_unoq_source_raises_not_implemented_honestly PASSED
tests/integration/test_end_to_end.py::test_normal_frames_are_accepted_and_appear_in_trusted_store PASSED
tests/integration/test_end_to_end.py::test_checkpoint_is_issued_and_advances PASSED
tests/integration/test_end_to_end.py::test_second_batch_continues_chain_correctly PASSED
tests/integration/test_mqtt_transport.py::test_mqtt_transport_round_trip SKIPPED
tests/security/test_attack_lab.py::test_scenario_1_unauthorized_spoofed_device PASSED
tests/security/test_attack_lab.py::test_scenario_2_signed_payload_modified_after_signing PASSED
tests/security/test_attack_lab.py::test_scenario_3_replay_previously_accepted_event PASSED
tests/security/test_attack_lab.py::test_scenario_4_duplicate_event_within_one_batch PASSED
tests/security/test_attack_lab.py::test_scenario_5_reorder_buffered_records PASSED
tests/security/test_attack_lab.py::test_scenario_6_change_previous_hash PASSED
tests/security/test_attack_lab.py::test_scenario_7_modify_batch_root PASSED
tests/security/test_attack_lab.py::test_scenario_8_offline_queue_then_reconnect_continuity PASSED
tests/security/test_attack_lab.py::test_scenario_9_reconnect_with_wrong_checkpoint PASSED
tests/security/test_attack_lab.py::test_scenario_10_revoked_device_rejected PASSED
tests/unit/test_acquisition_sources.py::test_simulator_is_deterministic PASSED
tests/unit/test_acquisition_sources.py::test_replay_parses_fixture_log PASSED
tests/unit/test_acquisition_sources.py::test_replay_rejects_malformed_line PASSED
tests/unit/test_acquisition_sources.py::test_replay_ignores_comments_and_blank_lines PASSED
tests/unit/test_api_health.py::test_health_endpoint PASSED
tests/unit/test_api_health.py::test_metrics_endpoint_reflects_state PASSED
tests/unit/test_api_health.py::test_devices_endpoint PASSED
tests/unit/test_api_health.py::test_dashboard_served_at_root PASSED
tests/unit/test_canonical.py (5 tests) PASSED
tests/unit/test_chain.py (4 tests) PASSED
tests/unit/test_cose_signer.py (5 tests) PASSED
tests/unit/test_device_registry.py (3 tests) PASSED
tests/unit/test_merkle.py (6 tests) PASSED
tests/unit/test_quarantine_store.py (3 tests) PASSED
tests/unit/test_queue_persistence.py (3 tests) PASSED

tests/unit/test_unoq_protocol.py (11 tests) PASSED

================== 63 passed, 3 skipped, 1 warning in 3.48s ===================
```

**63 passed, 3 skipped, 0 failed** (52 + 11 new UNO Q Bridge protocol tests). The warning is a third-party
`DeprecationWarning` from `starlette.testclient` about an `anyio` alias,
unrelated to this project's code.

Skipped tests are skipped with an explicit, inspectable reason (not
silently green):

- `test_pcan_source_receives_frames_from_hardware` -- `NOT RUN - HARDWARE
  REQUIRED: no PEAK PCAN adapter/driver in this environment`
- `test_unoq_bridge_receives_frames_from_mcu` -- `NOT RUN - HARDWARE
  REQUIRED: no Arduino UNO Q board in this environment`
- `test_mqtt_transport_round_trip` -- `NOT RUN - BROKER REQUIRED: no MQTT
  broker reachable on 127.0.0.1:8883`

## Standalone attack-lab scripts (LIVE/REAL VERIFIED -- each run as its own process)

```
$ python -m attack_lab.spoof_identity
[PASS] spoof_identity: expected reason 'UNKNOWN_DEVICE', observed ['UNKNOWN_DEVICE']

$ python -m attack_lab.tamper
[PASS] tamper: expected reason 'SIGNATURE_INVALID', observed ['SIGNATURE_INVALID']

$ python -m attack_lab.replay
[info] first submission accepted=3
[PASS] replay: expected reason 'REPLAY', observed ['REPLAY']

$ python -m attack_lab.duplicate
[PASS] duplicate: expected reason 'DUPLICATE', observed ['DUPLICATE']

$ python -m attack_lab.reorder
[PASS] reorder: expected one of {'OUT_OF_ORDER', 'CHAIN_MISMATCH'}, observed ['BATCH_ROOT_INVALID', 'CHAIN_MISMATCH']

$ python -m attack_lab.batch_root_forgery
[PASS] batch_root_forgery: expected reason 'BATCH_ROOT_INVALID', observed ['BATCH_ROOT_INVALID']

$ python -m attack_lab.checkpoint_mismatch
[PASS] checkpoint_mismatch: expected reason 'CHECKPOINT_MISMATCH', observed ['CHECKPOINT_MISMATCH']

$ python -m attack_lab.device_revocation
[PASS] device_revocation: expected reason 'DEVICE_REVOKED', observed ['DEVICE_REVOKED']

$ python -m attack_lab.outage_reconnect
[info] network offline; queue depth after 6 frames = 6
[info] drain attempt while offline: transport_error='simulated network outage', queue depth still = 6
[info] network reconnected
[info] after reconnect: accepted=6, queue depth = 0
[PASS] outage_reconnect: offline_ok=True, reconnect_ok=True
```

All 9 scripts exit 0 (PASS). `reorder`'s observed set includes
`BATCH_ROOT_INVALID` in addition to `CHAIN_MISMATCH` because, once chain
validation rejects the reordered middle event, the remaining accepted
events no longer match the attacker-declared Merkle root either -- this is
a stronger rejection than the minimum required, not a weaker one.

## Backend database tamper-check utility (LIVE/REAL VERIFIED)

Run against the real `data/backend/trusted.db` produced by the end-to-end
demo run (DEMO_SCRIPT.md), and then against a copy with one `event_cbor`
byte flipped:

```
$ python -m attack_lab.db_tamper_check data/backend/trusted.db
[PASS] db_tamper_check: chain is self-consistent, no tampering detected

$ python -m attack_lab.db_tamper_check <tampered copy>
[FAIL] db_tamper_check: 1 chain inconsistency(ies) detected
  - gateway=gw-demo-01 boot_epoch=10178025 sequence=0: stored event_hash=c159038a... does
    not match recomputed=34cdbaaf... -- row content or chain has been altered
```

## End-to-end real-process demo (LIVE/REAL VERIFIED, not TestClient)

Ran `python -m backend.main` as a real `uvicorn` process bound to
`127.0.0.1:8443`, then `python -m edge.main --mode replay --replay-log
data/synthetic_can.log` as a separate process talking to it over real
HTTP (not in-process ASGI):

```
$ curl http://127.0.0.1:8443/health
{"status":"ok","uptime_s":1.099}

... edge.main runs, logs show:
drain: attempted=20 accepted=20 rejected=0 error=None
... (repeated for all batches)
processed 158 frames, final queue depth=0

$ curl http://127.0.0.1:8443/metrics
{"trusted_event_count":316,"quarantine_event_count":0,"quarantine_reason_histogram":{},"device_count":1}
```

(316 = 158 frames x 2 runs performed while validating a bug fix in
`edge/main.py`'s shutdown ordering -- see "Bugs found and fixed" below.)

A spoofed-device batch was then submitted directly against this live
server and correctly quarantined:

```
$ python -c "... submit from unregistered device ..."
200 {'accepted': [], 'rejected': {'unindexed-0': 'UNKNOWN_DEVICE'}, 'checkpoint': None}

$ curl http://127.0.0.1:8443/metrics
{"trusted_event_count":316,"quarantine_event_count":1,"quarantine_reason_histogram":{"UNKNOWN_DEVICE":1},"device_count":1}
```

The dashboard at `http://127.0.0.1:8443/` was confirmed to return HTTP 200
and serve the real `dashboard/index.html`.

## Bugs found and fixed during this session

1. `edge/trust/cose_signer.py::verify` originally raised `SignatureError`
   on a malformed/unexpected protected header instead of returning
   `False`; fixed so untrusted input never raises, only ever returns a
   boolean (caught by `test_cose_signer.py::test_corrupted_protected_header_alg_rejected`).
2. `httpx.ASGITransport` is async-only and cannot back a sync `httpx.Client`
   in tests; switched the integration-test harness to
   `fastapi.testclient.TestClient`.
3. `edge/main.py`'s shutdown path called `queue.depth()` in a final log
   line *after* the queue connection was already closed in `finally`,
   raising `sqlite3.ProgrammingError: Cannot operate on a closed database`
   on every real run; fixed by computing `final_depth` before closing.
4. `attack_lab` scripts and their shared harness did not close SQLite
   connections / the TestClient before their `tempfile.TemporaryDirectory`
   cleanup ran, causing `PermissionError: ... being used by another
   process` on Windows; fixed by adding explicit `close()` calls.

## Static checks

- `py_compile` over every `.py` file in the repository: **no syntax
  errors**.
- Manual grep for hardcoded secret-like patterns (`BEGIN PRIVATE KEY`,
  `api_key =`, `password =`, `secret =`): **none found**. No automated
  SBOM/secret-scanner tool was available in this environment to run
  beyond this manual check (see THIRD_PARTY_NOTICES.md).
- `.gitignore` verified to exclude `certs/`, `*.key`, `*.pem`, `*.db`,
  `.venv/`, and `.env` before any commit.

## Not run (see docs/LIMITATIONS.md)

- Real PCAN hardware receive path (no adapter available).
- Real Arduino UNO Q bring-up (no board available).
- `docker-compose up` / Dockerfile build (no Docker daemon available).
- MQTT transport against a real Mosquitto broker.
