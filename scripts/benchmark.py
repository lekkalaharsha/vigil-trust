#!/usr/bin/env python
"""Reproducible performance benchmark, measured on THIS machine only.

Writes nothing by itself -- redirect stdout to BENCHMARK_RESULTS.md, or run
and paste the output, along with `python --version` and OS info, which this
script also prints. Never copy these numbers into a UNO Q claim; they are a
workstation/CI measurement only (see docs/LIMITATIONS.md).

Usage:
    .venv/Scripts/python.exe scripts/benchmark.py
"""

from __future__ import annotations

import platform
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from edge.queue.sqlite_queue import SqliteQueue
from edge.trust import cose_signer, merkle
from edge.trust.canonical import CanonicalEvent, canonical_bytes
from edge.trust.envelope import GatewayState
from edge.acquisition.simulator import SimulatorSource


def _timed(fn, n: int) -> float:
    start = time.perf_counter()
    for _ in range(n):
        fn()
    elapsed = time.perf_counter() - start
    return elapsed


def bench_signing(n: int = 2000) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    event = CanonicalEvent(
        gateway_id="gw-bench", vehicle_profile_id="demo-v1", boot_epoch=1, sequence=0,
        capture_time=0.0, can_channel="sim0", can_id=0x100, is_extended_id=False, is_fd=False,
        dlc=8, raw_payload=b"\x01\x02\x03\x04\x05\x06\x07\x08",
        previous_event_hash="0" * 64, batch_id="b", policy_version=1,
    )
    payload = canonical_bytes(event)

    elapsed = _timed(lambda: cose_signer.sign(payload, key), n)
    print(f"Signing:   {n} events in {elapsed:.4f}s -> {n / elapsed:,.0f} events/sec")

    signed = cose_signer.sign(payload, key)
    pub = key.public_key()
    elapsed = _timed(lambda: cose_signer.verify(signed, pub), n)
    print(f"Verify:    {n} events in {elapsed:.4f}s -> {n / elapsed:,.0f} verifications/sec")

    envelope_bytes = signed.to_cbor()
    unsigned_json_estimate = len(str(event.to_dict()).encode())
    print(f"Envelope size: {len(envelope_bytes)} bytes (COSE_Sign1 CBOR) "
          f"vs ~{unsigned_json_estimate} bytes (unsigned JSON-ish estimate of the same fields)")


def bench_merkle(sizes=(10, 100, 1000, 10000)) -> None:
    import hashlib
    for n in sizes:
        hashes = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(n)]
        start = time.perf_counter()
        merkle.build_merkle_root(hashes)
        elapsed = time.perf_counter() - start
        print(f"Merkle build: n={n:>6} -> {elapsed * 1000:.3f} ms")


def bench_queue(n: int = 2000) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="vigil_bench_"))
    try:
        key = ec.generate_private_key(ec.SECP256R1())
        state = GatewayState(gateway_id="gw-bench", vehicle_profile_id="demo-v1", private_key=key, batch_size=n + 1)
        queue = SqliteQueue(tmp_dir / "queue.db")
        frames = list(SimulatorSource(frame_count=n, realtime=False).frames())
        envelopes = [state.build_and_sign(f) for f in frames]

        start = time.perf_counter()
        for e in envelopes:
            queue.enqueue(e)
        insert_elapsed = time.perf_counter() - start
        print(f"Queue insert: {n} rows in {insert_elapsed:.4f}s -> {n / insert_elapsed:,.0f} rows/sec")

        start = time.perf_counter()
        items = queue.pending(limit=n)
        read_elapsed = time.perf_counter() - start
        print(f"Queue read:   {len(items)} rows in {read_elapsed:.4f}s -> {len(items) / read_elapsed:,.0f} rows/sec")
        queue.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def bench_reconnect_verification(sizes=(100, 1000, 10000)) -> None:
    """Measures how long it takes the BACKEND to re-verify a batch of the
    given size end to end (signature + chain + merkle), simulating a
    reconnect catch-up. Uses the same in-process harness as
    tests/integration, no network socket involved."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from cryptography.hazmat.primitives import serialization

    from backend.api.app import create_app
    from backend.checkpoints.store import CheckpointService
    from backend.device_registry.registry import TRUSTED, DeviceRegistry
    from backend.quarantine.store import QuarantineStore
    from backend.verifier.trusted_store import TrustedStore
    from edge.trust.identity import device_id_from_public_key, generate_keypair
    from fastapi.testclient import TestClient
    import base64
    from edge.trust.checkpoints import BatchCommitment

    for n in sizes:
        tmp_dir = Path(tempfile.mkdtemp(prefix="vigil_bench_reconnect_"))
        try:
            device_key = generate_keypair()
            device_id = device_id_from_public_key(device_key.public_key())
            public_key_pem = device_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii")
            registry = DeviceRegistry(tmp_dir / "registry.db")
            registry.register(device_id, "demo-v1", public_key_pem, status=TRUSTED)
            trusted_store = TrustedStore(tmp_dir / "trusted.db")
            quarantine = QuarantineStore(tmp_dir / "quarantine.db")
            checkpoints = CheckpointService(tmp_dir / "checkpoints.db", generate_keypair())
            app = create_app(registry, trusted_store, quarantine, checkpoints)
            client = TestClient(app, base_url="http://bench.test")

            state = GatewayState(gateway_id=device_id, vehicle_profile_id="demo-v1", private_key=device_key, batch_size=n + 1)
            frames = list(SimulatorSource(frame_count=n, realtime=False).frames())
            envelopes = [state.build_and_sign(f) for f in frames]

            commitment = BatchCommitment(
                gateway_id=device_id, boot_epoch=envelopes[0].boot_epoch,
                first_sequence=envelopes[0].sequence, last_sequence=envelopes[-1].sequence,
                previous_checkpoint_digest="0" * 64,
                batch_root=merkle.build_merkle_root([e.event_hash for e in envelopes]),
            )
            signed_commitment = cose_signer.sign(commitment.canonical_bytes(), device_key)

            start = time.perf_counter()
            response = client.post("/ingest/batch", json={
                "gateway_id": device_id,
                "batch_commitment": base64.b64encode(signed_commitment.to_cbor()).decode("ascii"),
                "events": [base64.b64encode(e.cose_cbor).decode("ascii") for e in envelopes],
            })
            elapsed = time.perf_counter() - start
            body = response.json()
            assert len(body["accepted"]) == n, f"expected {n} accepted, got {len(body['accepted'])}"
            print(f"Reconnect verification: n={n:>6} -> {elapsed:.4f}s total, "
                  f"{elapsed / n * 1000:.3f} ms/event, {n / elapsed:,.0f} events/sec")
            client.close()
            registry.close()
            trusted_store.close()
            quarantine.close()
            checkpoints.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Processor: {platform.processor() or 'unknown'}")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("=== Signing / verification / envelope size ===")
    bench_signing()
    print()
    print("=== Merkle batch build time ===")
    bench_merkle()
    print()
    print("=== Edge durable queue throughput ===")
    bench_queue()
    print()
    print("=== Backend reconnect-batch verification ===")
    bench_reconnect_verification()
    print()
    print("NOT MEASURED: Arduino UNO Q CPU/memory/latency, PCAN bus-load frame drop rate, "
          "MQTT transport latency over a real broker -- see docs/LIMITATIONS.md.")


if __name__ == "__main__":
    main()
