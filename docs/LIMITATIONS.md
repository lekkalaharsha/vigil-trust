# Limitations

This is a hackathon prototype, not a certified product. Read this before
citing any capability or number from this repository.

## Explicit non-claims

This project does **not** claim:

- Production certification of any kind.
- V2X standards compliance (IEEE 1609.2/1609.2.1/1609.2.2, ETSI TS 102
  940/941). The COSE_Sign1-style container and ECDSA P-256 primitive are
  *inspired by* and *compatible in spirit with* these ecosystems, but no
  conformance testing has been performed.
- ISO/SAE 21434 or UNECE R155 compliance.
- Hardware-backed key isolation (STM32U585 TrustZone/HUK/PKA) -- the
  current signer is software-only (edge/trust/identity.py +
  edge/trust/cose_signer.py). Hardware-backed signing is a documented
  target, not implemented (firmware/uno_q_mcu/README.md).
- That appearance of "first", "novel cryptography", or "unhackable" --
  every cryptographic primitive used here is a standard, well-known one
  (ECDSA P-256/SHA-256, SHA-256 hash chaining, Merkle trees, TLS). See
  VIGIL_TRUST_Research_and_Architecture.md section 5 for the full novelty
  analysis and prior-art table.
- Any accuracy/performance number not actually measured in this repository
  (see BENCHMARK_RESULTS.md and TEST_RESULTS.md for what was measured,
  and NOT measured).

## Hardware not available in this environment

- **Arduino UNO Q board**: not available. The Bridge wire protocol
  (`edge/acquisition/unoq_protocol.py` and
  `firmware/uno_q_mcu/bridge_protocol/`) is implemented and cross-verified
  between the Python and C sides without needing hardware (see
  `firmware/uno_q_mcu/tests/README.md`). `edge/acquisition/unoq.py`'s
  serial I/O and `firmware/uno_q_mcu/can_rx/` + the top-level `.ino`
  sketch are written but **not hardware-validated**; they fail with a
  clear, explicit error (`UnoQBridgeUnavailableError`) rather than
  returning fake data when no board is present. See
  `firmware/uno_q_mcu/README.md` for the full per-module status table.
- **PEAK PCAN-USB adapter**: not available. `edge/acquisition/pcan.py` and
  `edge/acquisition/socketcan.py` are implemented against the python-can
  API and raise a clear `PcanUnavailableError` when no driver/adapter is
  present (verified by tests/hardware/test_pcan_hardware.py); the actual
  hardware receive path has not been exercised against a real adapter.
- **Docker / Mosquitto broker**: not available in this sandbox.
  `docker-compose.yml` and `Dockerfile.backend` are written but **not
  built or run**. `edge/transport/mqtt.py` is implemented but only
  integration-tested when a broker is reachable
  (tests/integration/test_mqtt_transport.py self-skips otherwise). The
  HTTPS transport (edge/transport/https.py) is what the full test suite
  and the real local demo (see DEMO_SCRIPT.md) actually exercise
  end-to-end.

## Architectural / cryptographic limitations (by design, documented)

- **Truncation attack**: the hash chain (edge/trust/chain.py) and Merkle
  batch root (edge/trust/merkle.py) give order-sensitive tamper evidence
  *within* a boot session, and the backend acceptance checkpoint
  (edge/trust/checkpoints.py, backend/checkpoints/store.py) anchors
  continuity from the first moment the backend observes a gateway/boot
  session. Data produced and buffered entirely offline, before any
  checkpoint has ever been issued for that boot_epoch, has no external
  anchor to compare against if an attacker with full control of the device
  discards a suffix of that pre-checkpoint data before the gateway ever
  reconnects. This is a known, inherent limitation of hash-chain-only
  schemes without a second, independently-rooted witness (e.g. a
  transparency log, a periodic external timestamp authority, or a
  hardware monotonic counter) and is not solved here.
- **COSE_Sign1 is not RFC-conformant in full generality**:
  edge/trust/cose_signer.py implements the RFC 9052 Sig_structure, ES256
  protected header, and raw r||s signature encoding, and is covered by
  test vectors in tests/unit/test_cose_signer.py, but it has not been run
  against an independent COSE conformance test suite or interop-tested
  against pycose/other COSE libraries.
- **Checkpoint/backend signing key is a single demo key file** (no HSM,
  no key rotation, no revocation procedure) -- see
  scripts/generate_backend_key.py.
- **Replay-cache scope**: duplicate/replay detection
  (backend/verifier/verifier.py) is scoped per (gateway_id, boot_epoch);
  it does not maintain a global cross-gateway, cross-epoch replay cache
  beyond what the chain/sequence state already captures.

## Not measured (do not estimate)

See BENCHMARK_RESULTS.md "Not measured" section: UNO Q CPU/memory/latency,
PCAN real-bus frame-drop behavior, MQTT-over-real-broker latency.

## What IS real in this repository

- Full canonical-serialization -> ECDSA sign -> hash-chain -> Merkle batch
  -> backend verify -> trusted/quarantine store pipeline, exercised
  end-to-end over real HTTP against a running `uvicorn` server (not just
  in-process tests) -- see DEMO_SCRIPT.md.
- All 10 required attack-lab scenarios, runnable both as pytest
  (tests/security/test_attack_lab.py) and as standalone CLI scripts
  (attack_lab/*.py) -- see TEST_RESULTS.md.
- A durable SQLite store-and-forward queue that survives process restart
  (tests/unit/test_queue_persistence.py) and a simulated
  network-outage/reconnect flow (attack_lab/outage_reconnect.py).
- Real, reproducible performance numbers for signing, verification, Merkle
  batching, queue throughput, and reconnect-batch re-verification on the
  development workstation (BENCHMARK_RESULTS.md).
