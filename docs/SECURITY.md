# Security

## Reporting

This is a hackathon prototype with no production deployment; there is no
formal disclosure program. File an issue in the repository, or contact the
team directly, describing the issue and, if it's a vulnerability class
rather than a working exploit, keep exploit steps out of any public issue.

## Controls implemented

| Threat | Control | Code |
|---|---|---|
| Eavesdropping | TLS (demo: plain HTTP on localhost for the default transport; TLS 1.3/mTLS for the MQTT transport) | `edge/transport/mqtt.py`, `scripts/dev_pki.py` |
| Spoofed gateway | Per-device registry, no auto-trust | `backend/device_registry/registry.py` |
| Payload modification (in transit or at rest) | Application-layer ECDSA signature | `edge/trust/cose_signer.py` |
| Replay / duplicate | boot_epoch + sequence + event-hash replay cache | `backend/verifier/verifier.py` |
| Reordering | Hash chain + strict sequence check | `edge/trust/chain.py`, `backend/verifier/verifier.py` |
| Offline buffered tamper | Signed records + Merkle batch root + reconnect checkpoint | `edge/trust/merkle.py`, `edge/trust/checkpoints.py` |
| Stolen/revoked credential | Revocation state in device registry | `backend/device_registry/registry.py` (`REVOKED`) |
| Malicious CAN transmit | Acquisition sources are receive-only; no transmit method exists anywhere in `edge/acquisition/` | `edge/acquisition/base.py` |
| Unbounded resource use | Bounded batch sizes, durable queue with explicit limits, localhost-only metrics bind | `edge/pipeline.py`, `edge/api/metrics_server.py` |

## Input validation boundaries

Everything received from the network is treated as untrusted until it
clears `backend/verifier/verifier.py`:

- Base64 decode errors -> HTTP 400, never a crash
  (`backend/api/app.py::ingest_batch`).
- Malformed COSE structure -> `SCHEMA_INVALID`
  (`edge/trust/cose_signer.py::CoseSign1.from_cbor`).
- Unsupported/corrupt alg header -> signature verification returns `False`,
  never raises on attacker input (`edge/trust/cose_signer.py::verify`).
- Malformed canonical CBOR payload or missing required fields ->
  `SCHEMA_INVALID` (`backend/verifier/verifier.py::_verify_one_event`).

## Secrets handling

- Private keys are generated locally (`scripts/dev_pki.py`,
  `scripts/generate_backend_key.py`) and written only under `certs/`,
  which `.gitignore` excludes entirely.
- No credential or raw key is ever logged (`edge/main.py`,
  `backend/main.py` log structured, non-secret fields only).
- The dashboard and REST API never expose private key material; `/devices`
  only returns `device_id`, `vehicle_profile_id`, `status`, timestamps.

## Known gaps (see docs/LIMITATIONS.md for the full list)

- Software-only signing key (no HSM/TrustZone backing in this prototype).
- No X.509 client-certificate validation at the application layer (mTLS
  for MQTT uses TLS-layer client cert validation only); `CERTIFICATE_INVALID`
  is a reserved-but-unused reason code.
- No automated dependency/secret scanner was available in this
  environment; a manual secret-pattern review was performed instead (see
  TEST_RESULTS.md "Security review").
