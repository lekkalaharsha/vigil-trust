# Protocol: CAN Trust Envelope (CTE)

## Canonical event schema

Defined in `edge/trust/canonical.py` (`CanonicalEvent`), serialized with
`cbor2.dumps(data, canonical=True)` (RFC 8949 deterministic encoding --
same logical event always produces the same bytes, verified by
`tests/unit/test_canonical.py`):

```text
version                  int, schema version (currently 1)
vehicle_profile_id       str
gateway_id               str
boot_epoch               int, random per process start (edge/trust/envelope.py:new_boot_epoch)
sequence                 int, monotonic within one boot_epoch, starting at 0
capture_time             float, seconds (from the acquisition source's own clock)
can_channel              str
can_id                   int
is_extended_id           bool
is_fd                    bool
dlc                      int (0-64)
raw_payload               bytes   -- exactly one of these two is present
  OR raw_payload_digest   str (sha256 hex)
decoded_signals          dict, optional (reserved for DBC-decoded signals)
previous_event_hash      str, 64-hex-char sha256 (chain state before this event)
batch_id                 str
policy_version           int
```

## Signing container: COSE_Sign1-style

`edge/trust/cose_signer.py` implements RFC 9052's COSE_Sign1 structure on
top of pyca/cryptography (not pycose -- see docs/LIMITATIONS.md):

```text
Sig_structure = ["Signature1", protected_header_bytes, b"", payload_bytes]
protected_header = {1: -7}   # alg = ES256 (ECDSA P-256 / SHA-256)
signature = ECDSA-sign(SHA-256(canonical CBOR of Sig_structure))
            encoded as raw r||s (64 bytes), not DER
wire_message = [protected_header_bytes, {}, payload_bytes, signature]  # CBOR array
```

## Hash chain

`edge/trust/chain.py`:

```text
H_n = SHA-256(canonical_event_n_bytes || H_(n-1))
H_(-1) = GENESIS_HASH = "0" * 64   (per boot_epoch)
```

`H_n` becomes event `n`'s `event_hash`, used as the Merkle leaf and the
replay-cache key -- it is *not* a plain digest of the event alone, it
binds the event to everything chained before it.

## Batch commitment and Merkle root

`edge/trust/merkle.py` + `edge/trust/checkpoints.py::BatchCommitment`:

```text
batch_root = MerkleRoot(H_first ... H_last)   # domain-separated leaves/nodes
BatchCommitment = {
  gateway_id, boot_epoch, first_sequence, last_sequence,
  previous_checkpoint_digest, batch_root
}
```

The commitment itself is signed the same way as an event (COSE_Sign1-style,
same device key) before being transmitted alongside the batch.

## Backend acceptance checkpoint

`edge/trust/checkpoints.py::AcceptanceCheckpoint`, issued and signed by the
backend (`backend/checkpoints/store.py`) only after a batch fully passes
verification:

```text
AcceptanceCheckpoint = {
  gateway_id, boot_epoch, highest_accepted_sequence,
  accepted_batch_root, previous_checkpoint_digest, backend_time
}
```

The gateway persists the resulting digest (`edge/queue/checkpoint_store.py`)
and references it as `previous_checkpoint_digest` in its next batch
commitment. A mismatch is rejected as `CHECKPOINT_MISMATCH`.

## Wire transport envelope (HTTPS)

`POST /ingest/batch` (backend/api/app.py):

```json
{
  "gateway_id": "gw-demo-01",
  "batch_commitment": "<base64 COSE_Sign1 CBOR of BatchCommitment>",
  "events": ["<base64 COSE_Sign1 CBOR of one event>", "..."]
}
```

Response:

```json
{
  "accepted": ["<event_hash>", "..."],
  "rejected": {"<event_hash or unindexed-N>": "<REASON_CODE>"},
  "checkpoint": "<new checkpoint digest, or null if nothing was accepted>"
}
```

## Required rejection reason codes

`UNKNOWN_DEVICE`, `DEVICE_REVOKED`, `CERTIFICATE_INVALID`,
`SIGNATURE_INVALID`, `SCHEMA_INVALID`, `REPLAY`, `DUPLICATE`,
`OUT_OF_ORDER`, `CHAIN_MISMATCH`, `CHECKPOINT_MISMATCH`,
`BATCH_ROOT_INVALID`, `POLICY_REJECTED` -- enforced as the only valid
values in `backend/quarantine/store.py::VALID_REASON_CODES` and produced
by `backend/verifier/verifier.py`. See docs/THREAT_MODEL.md for which
attack produces which code.

Note: `CERTIFICATE_INVALID` and `POLICY_REJECTED` are reserved codes in
the valid set for future use (e.g. X.509 chain validation if mTLS client
certs are later checked at the application layer, or a policy engine
rejecting an otherwise-valid event) -- no current code path emits them,
and no attack-lab scenario exercises them; they are not silently dropped,
they are simply unused in this prototype.
