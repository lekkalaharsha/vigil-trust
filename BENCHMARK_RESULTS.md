# Benchmark Results

Measured by running `scripts/benchmark.py` on the development workstation
used to build this prototype. These are **workstation numbers, not Arduino
UNO Q numbers** -- do not use them as a UNO Q performance claim (see
docs/LIMITATIONS.md). Reproduce with:

```bash
.venv/Scripts/python.exe scripts/benchmark.py
```

## Environment

- Python: 3.12.7 (MSC v.1941 64 bit, Windows)
- Platform: Windows-11-10.0.26300-SP0
- Processor: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD
- Date measured: 2026-10-16 17:27:09

## Results

### Signing / verification / envelope size

| Metric | Result |
|---|---|
| Signing throughput | 2000 events in 0.2125s -> **9,414 events/sec** |
| Verification throughput | 2000 events in 0.2777s -> **7,202 verifications/sec** |
| Envelope size | 359 bytes (COSE_Sign1 CBOR) vs ~396 bytes (unsigned JSON-ish estimate of the same fields) |

### Merkle batch build time

| Batch size (n) | Build time |
|---|---|
| 10 | 0.066 ms |
| 100 | 0.355 ms |
| 1,000 | 2.612 ms |
| 10,000 | 27.869 ms |

### Edge durable (SQLite) queue throughput

| Operation | Result |
|---|---|
| Insert (enqueue) | 2000 rows in 1.2865s -> **1,555 rows/sec** |
| Read (pending) | 2000 rows in 0.0110s -> **181,329 rows/sec** |

Insert throughput is bounded by one `COMMIT` (durability fsync) per
enqueued event in the current implementation -- this is a deliberate
durability choice (store-and-forward must survive a crash immediately
after enqueue), not an unoptimized accident, but a production version could
batch commits every N events or every M milliseconds to trade a small
durability window for much higher throughput.

### Backend reconnect-batch verification (signature + chain + Merkle, per batch)

| Batch size (n) | Total time | Per-event | Throughput |
|---|---|---|---|
| 100 | 0.6039s | 6.039 ms | 166 events/sec |
| 1,000 | 4.9010s | 4.901 ms | 204 events/sec |
| 10,000 | 40.8643s | 4.086 ms | 245 events/sec |

This is the single-process, single-threaded cost of fully re-verifying a
buffered batch after a simulated reconnect (ECDSA verify + canonical
decode + chain check + Merkle recomputation per event, via the in-process
FastAPI TestClient -- no real network round-trip). It is dominated by
ECDSA P-256 signature verification per event; a production backend would
parallelize verification across events/batches and/or scale horizontally
rather than process one event at a time on one core.

## Not measured (do not estimate)

- Arduino UNO Q (STM32U585 / QRB2210) CPU, memory, or signing latency --
  no UNO Q hardware was available in this environment.
- PCAN real-hardware frame rate / dropped-frame behavior at a given bus
  load -- no PCAN adapter was connected in this environment.
- MQTT transport latency/throughput over a real Mosquitto broker -- no
  Docker/broker was available in this environment (see docs/LIMITATIONS.md).
