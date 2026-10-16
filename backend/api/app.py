"""Backend REST API: ingestion, health, metrics, and read-only data for the
dashboard. Binds to all interfaces only when explicitly configured; the
default demo config binds to localhost (see backend/main.py / .env.example).
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.checkpoints.store import CheckpointService
from backend.device_registry.registry import DeviceRegistry
from backend.quarantine.store import QuarantineStore
from backend.verifier.trusted_store import TrustedStore
from backend.verifier.verifier import Verifier

START_TIME = time.time()
DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"


class IngestBatchRequest(BaseModel):
    gateway_id: str
    batch_commitment: str = Field(..., description="base64-encoded COSE_Sign1 CBOR")
    events: list[str] = Field(..., description="list of base64-encoded COSE_Sign1 CBOR events")


class IngestBatchResponse(BaseModel):
    accepted: list[str]
    rejected: dict[str, str]
    checkpoint: str | None = None


def create_app(
    registry: DeviceRegistry,
    trusted_store: TrustedStore,
    quarantine: QuarantineStore,
    checkpoints: CheckpointService,
) -> FastAPI:
    app = FastAPI(title="VIGIL-TRUST Backend", version="0.1.0")
    verifier = Verifier(registry, trusted_store, quarantine, checkpoints)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "uptime_s": round(time.time() - START_TIME, 3)}

    @app.get("/metrics")
    def metrics() -> dict[str, Any]:
        return {
            "trusted_event_count": trusted_store.count(),
            "quarantine_event_count": quarantine.count(),
            "quarantine_reason_histogram": quarantine.reason_histogram(),
            "device_count": len(registry.list_all()),
        }

    @app.post("/ingest/batch", response_model=IngestBatchResponse)
    def ingest_batch(request: IngestBatchRequest) -> IngestBatchResponse:
        try:
            cose_messages = [base64.b64decode(e) for e in request.events]
            batch_commitment_cbor = base64.b64decode(request.batch_commitment)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid base64 in request: {exc}") from exc
        if not cose_messages:
            raise HTTPException(status_code=400, detail="events must not be empty")

        result = verifier.verify_batch(request.gateway_id, cose_messages, batch_commitment_cbor)
        return IngestBatchResponse(
            accepted=result.accepted_event_hashes,
            rejected=result.rejected,
            checkpoint=result.new_checkpoint_digest,
        )

    @app.get("/devices")
    def list_devices() -> list[dict[str, Any]]:
        return [
            {
                "device_id": d.device_id,
                "vehicle_profile_id": d.vehicle_profile_id,
                "status": d.status,
                "registered_at": d.registered_at,
                "updated_at": d.updated_at,
            }
            for d in registry.list_all()
        ]

    @app.get("/events/recent")
    def recent_events(limit: int = 100, gateway_id: str | None = None) -> list[dict[str, Any]]:
        return trusted_store.recent_events(limit=limit, gateway_id=gateway_id)

    @app.get("/quarantine/recent")
    def recent_quarantine(limit: int = 100) -> list[dict[str, Any]]:
        return quarantine.recent(limit=limit)

    @app.get("/quarantine/histogram")
    def quarantine_histogram() -> dict[str, int]:
        return quarantine.reason_histogram()

    if DASHBOARD_DIR.exists():
        @app.get("/")
        def dashboard_index() -> FileResponse:
            return FileResponse(DASHBOARD_DIR / "index.html")

        app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

    return app
