"""HTTPS transport: POST signed batches to the backend ingestion API.

This is the transport exercised end-to-end in the automated test suite
(tests/integration/test_end_to_end.py) because it needs no external broker
process. See edge/transport/mqtt.py for the MQTT 5 + TLS transport, which is
implemented but only integration-tested when a broker is reachable.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from edge.transport.base import SubmitResult, Transport, TransportError


class HttpsTransport(Transport):
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        client_cert: tuple[str, str] | None = None,
        verify: bool | str = True,
        timeout: float = 10.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            cert=client_cert,
            verify=verify,
            timeout=timeout,
        )

    def submit_batch(self, gateway_id: str, cose_messages: list[bytes], batch_commitment_cbor: bytes) -> SubmitResult:
        body: dict[str, Any] = {
            "gateway_id": gateway_id,
            "batch_commitment": base64.b64encode(batch_commitment_cbor).decode("ascii"),
            "events": [base64.b64encode(m).decode("ascii") for m in cose_messages],
        }
        try:
            response = self._client.post("/ingest/batch", json=body)
        except httpx.TransportError as exc:
            raise TransportError(f"could not reach backend: {exc}") from exc
        if response.status_code >= 500:
            raise TransportError(f"backend error {response.status_code}: {response.text}")
        if response.status_code >= 400:
            # Backend reachable but refused the whole request (e.g. malformed
            # body or unknown gateway at the HTTP layer) -- treat every event
            # in the batch as rejected with the server-provided reason.
            detail = response.json().get("detail", "POLICY_REJECTED") if response.headers.get(
                "content-type", ""
            ).startswith("application/json") else "POLICY_REJECTED"
            return SubmitResult(
                accepted_event_hashes=[],
                rejected={"*": str(detail)},
                new_checkpoint_digest=None,
            )
        data = response.json()
        return SubmitResult(
            accepted_event_hashes=data["accepted"],
            rejected=data["rejected"],
            new_checkpoint_digest=data.get("checkpoint"),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
