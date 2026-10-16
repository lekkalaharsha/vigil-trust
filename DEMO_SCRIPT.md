# Demo Script (5-7 minutes)

Matches VIGIL_TRUST_Research_and_Architecture.md section 17 and
VIGIL_TRUST_Implementation_SOP.md section 11. Everything below was
actually run during development of this repository -- see TEST_RESULTS.md
for the captured output.

## 0. One-time setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"   # or .venv/bin/python on Linux/macOS

.venv/Scripts/python.exe scripts/generate_backend_key.py
.venv/Scripts/python.exe scripts/dev_pki.py --device gw-demo-01
.venv/Scripts/python.exe scripts/register_device.py --device-id gw-demo-01 \
    --public-key-path certs/devices/gw-demo-01.pub.pem --vehicle-profile demo-v1 \
    --db-path data/backend/registry.db
```

## 1. Start the backend + dashboard

```bash
.venv/Scripts/python.exe -m backend.main
```

Open http://127.0.0.1:8443/ -- the dashboard shows 0 trusted events, 1
registered (trusted) device, 0 quarantined events.

## 2. Show verified telemetry (simulator or replay source)

In a second terminal:

```bash
VIGIL_GATEWAY_ID=gw-demo-01 VIGIL_DEVICE_KEY_PATH=certs/devices/gw-demo-01.key \
VIGIL_BACKEND_URL=http://127.0.0.1:8443 \
.venv/Scripts/python.exe -m edge.main --mode replay --replay-log data/synthetic_can.log
```

The dashboard's "Latest verified telemetry" table fills in live (polls
every 2s); "Trusted events" counter increases. This is real signed-&-
verified telemetry flowing edge -> HTTPS -> backend verifier -> dashboard,
not a mock.

## 3. Show device/security identity (not secret keys)

Point at the dashboard's "Devices / certificate status" table: `gw-demo-01`,
`status: trusted`. Explain: the backend only trusts devices explicitly
registered via `scripts/register_device.py` -- nothing is auto-trusted.

## 4. Tamper -> reject

```bash
.venv/Scripts/python.exe -m attack_lab.tamper
```

Explain the output: a payload field was edited after signing; the backend
independently recomputes and checks the ECDSA signature and rejects it as
`SIGNATURE_INVALID`. (This script uses its own disposable in-memory
backend so it doesn't need the one started in step 1 running -- point out
that the exact same `Verifier` code path is what the live backend runs.)

## 5. Replay -> reject

```bash
.venv/Scripts/python.exe -m attack_lab.replay
```

A previously-accepted batch is resent verbatim; rejected as `REPLAY`.

## 6. Disconnect -> local queue -> reconnect -> verified catch-up

```bash
.venv/Scripts/python.exe -m attack_lab.outage_reconnect
```

Shows: queue depth growing to 6 while "offline", a failed drain attempt
with `transport_error`, then a successful drain after "reconnecting" with
all 6 events verified and the queue returning to depth 0.

## 7. Show the rest of the attack lab (optional, time permitting)

```bash
make attack-lab
# or individually:
.venv/Scripts/python.exe -m attack_lab.spoof_identity
.venv/Scripts/python.exe -m attack_lab.duplicate
.venv/Scripts/python.exe -m attack_lab.reorder
.venv/Scripts/python.exe -m attack_lab.batch_root_forgery
.venv/Scripts/python.exe -m attack_lab.checkpoint_mismatch
.venv/Scripts/python.exe -m attack_lab.device_revocation
```

## 8. Architecture and production path

Show docs/ARCHITECTURE.md's diagram and
VIGIL_TRUST_Research_and_Architecture.md section 14.2 (production target):
automotive-qualified hardware, HSM-backed identity, cellular/5G, ISO/SAE
21434 work products. Close with the one-line pitch: transport encryption
protects the pipe; VIGIL-TRUST also protects the telemetry object's
provenance and continuity after the pipe ends.

## Known gaps to state plainly if asked

- No real UNO Q or PCAN hardware was available to validate against in
  this environment (docs/UNO_Q_SETUP.md, docs/PCAN_SETUP.md,
  docs/LIMITATIONS.md).
- MQTT transport is implemented but only integration-tested when a broker
  is reachable; the HTTPS transport is what this demo and the automated
  test suite exercise end-to-end.
