# Threat Model

Condensed from VIGIL_TRUST_Research_and_Architecture.md sections 3-4;
read that document for the full justification and citations.

## Trust boundaries

1. **CAN -> gateway**: what was captured, when, from which
   interface/profile (edge/acquisition/*, edge/trust/canonical.py).
2. **Gateway -> backend**: authenticate the gateway, encrypt the channel,
   protect message integrity end-to-end (edge/transport/*,
   edge/trust/cose_signer.py).
3. **Backend/storage -> operator**: evidence that backend-accepted data has
   not been silently altered or reordered after acceptance
   (backend/verifier/trusted_store.py chain, attack_lab/db_tamper_check.py).

## In scope (demonstrated by attack_lab/* and tests/security/*)

| # | Scenario | Script | Reason code |
|---|---|---|---|
| 1 | Unauthorized/spoofed gateway | `attack_lab/spoof_identity.py` | `UNKNOWN_DEVICE` |
| 2 | Signed payload modified after signing | `attack_lab/tamper.py` | `SIGNATURE_INVALID` |
| 3 | Replay of a previously-accepted record | `attack_lab/replay.py` | `REPLAY` |
| 4 | Duplicate record in one submission | `attack_lab/duplicate.py` | `DUPLICATE` |
| 5 | Reordered buffered records | `attack_lab/reorder.py` | `OUT_OF_ORDER` / `CHAIN_MISMATCH` |
| 6 | Forged previous_event_hash (re-signed by attacker) | `tests/security/test_attack_lab.py::test_scenario_6` | `SIGNATURE_INVALID` |
| 7 | Forged batch Merkle root | `attack_lab/batch_root_forgery.py` | `BATCH_ROOT_INVALID` |
| 8 | Network outage -> buffer -> reconnect continuity | `attack_lab/outage_reconnect.py` | n/a (resilience, not rejection) |
| 9 | Reconnect referencing a wrong checkpoint | `attack_lab/checkpoint_mismatch.py` | `CHECKPOINT_MISMATCH` |
| 10 | Revoked device / DB copy tamper check | `attack_lab/device_revocation.py`, `attack_lab/db_tamper_check.py` | `DEVICE_REVOKED` |

## Explicitly out of scope for this hackathon prototype

- Proving a CAN frame was transmitted by a specific physical ECU (we trust
  the acquisition boundary; a fully compromised source ECU can inject
  believable-looking frames that the gateway will faithfully sign).
- Defending against a compromised gateway device itself (if an attacker
  has the device's private key, they can sign anything -- device
  revocation after detection is the mitigation, not prevention).
- RF jamming / availability attacks against Wi-Fi.
- Any destructive or active attack against a real/operating vehicle.
- Full physical tamper resistance of the signing key (software-only signer
  in this prototype -- see docs/LIMITATIONS.md).
- Production HSM certification, IEEE 1609.2 conformance testing, 3GPP
  C-V2X modem/radio-stack implementation, ISO/SAE 21434 or UNECE R155
  certification.

## Assumptions

- The backend's device registry (backend/device_registry/) is the root of
  trust: a device is never auto-trusted, only explicitly registered by an
  operator (scripts/register_device.py).
- The backend's checkpoint-signing key and the device registry database
  are assumed uncompromised; this prototype does not defend against a
  compromised backend.
- Clock skew between edge and backend is not defended against beyond what
  `capture_time` vs `accepted_at`/`backend_time` naturally exposes for
  investigator review; there is no NTP/clock-sync enforcement.
