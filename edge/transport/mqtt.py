"""MQTT 5 transport over TLS with mutual authentication.

STATUS: IMPLEMENTED, INTEGRATION-TESTED ONLY WHEN A LOCAL MOSQUITTO BROKER
IS REACHABLE (tests/integration/test_mqtt_transport.py skips itself with a
clear reason otherwise -- see docker-compose.yml for a local broker, and
docs/LIMITATIONS.md). The HTTPS transport is what the automated test suite
and default demo exercise end-to-end.

Protocol: the gateway publishes one batch per MQTT PUBLISH to
`vigil/telemetry/<gateway_id>/batch` (QoS 1) and waits for a correlated
response on `vigil/ack/<gateway_id>` using the MQTT 5 Response-Topic /
Correlation-Data properties. The backend's MQTT bridge (backend/ingestion)
runs the same verifier used by the HTTPS path and publishes the ack.
"""

from __future__ import annotations

import base64
import json
import queue
import ssl
import uuid
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

from edge.transport.base import SubmitResult, Transport, TransportError

TELEMETRY_TOPIC_TEMPLATE = "vigil/telemetry/{gateway_id}/batch"
ACK_TOPIC_TEMPLATE = "vigil/ack/{gateway_id}"


class MqttTransport(Transport):
    def __init__(
        self,
        gateway_id: str,
        host: str,
        port: int = 8883,
        ca_cert: str | None = None,
        client_cert: str | None = None,
        client_key: str | None = None,
        ack_timeout_s: float = 10.0,
        use_tls: bool = True,
    ) -> None:
        self._gateway_id = gateway_id
        self._ack_timeout_s = ack_timeout_s
        self._ack_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()

        self._client = mqtt.Client(
            client_id=f"vigil-edge-{gateway_id}",
            protocol=mqtt.MQTTv5,
        )
        if use_tls:
            self._client.tls_set(
                ca_certs=ca_cert,
                certfile=client_cert,
                keyfile=client_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
        self._client.on_message = self._on_message
        self._client.connect(host, port, keepalive=30)
        self._client.subscribe(ACK_TOPIC_TEMPLATE.format(gateway_id=gateway_id), qos=1)
        self._client.loop_start()

    def _on_message(self, _client, _userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        self._ack_queue.put(payload)

    def submit_batch(self, gateway_id: str, cose_messages: list[bytes], batch_commitment_cbor: bytes) -> SubmitResult:
        correlation_id = uuid.uuid4().hex
        body = {
            "correlation_id": correlation_id,
            "gateway_id": gateway_id,
            "batch_commitment": base64.b64encode(batch_commitment_cbor).decode("ascii"),
            "events": [base64.b64encode(m).decode("ascii") for m in cose_messages],
        }
        properties = Properties(PacketTypes.PUBLISH)
        properties.ResponseTopic = ACK_TOPIC_TEMPLATE.format(gateway_id=gateway_id)
        properties.CorrelationData = correlation_id.encode("ascii")

        result = self._client.publish(
            TELEMETRY_TOPIC_TEMPLATE.format(gateway_id=gateway_id),
            payload=json.dumps(body),
            qos=1,
            properties=properties,
        )
        try:
            result.wait_for_publish(timeout=self._ack_timeout_s)
        except (RuntimeError, ValueError) as exc:
            raise TransportError(f"MQTT publish failed: {exc}") from exc
        if not result.is_published():
            raise TransportError("MQTT publish did not complete (broker unreachable?)")

        ack = self._wait_for_ack(correlation_id)
        if ack is None:
            raise TransportError("timed out waiting for backend MQTT ack")
        return SubmitResult(
            accepted_event_hashes=ack["accepted"],
            rejected=ack["rejected"],
            new_checkpoint_digest=ack.get("checkpoint"),
        )

    def _wait_for_ack(self, correlation_id: str) -> dict[str, Any] | None:
        import time

        deadline = time.monotonic() + self._ack_timeout_s
        while time.monotonic() < deadline:
            try:
                payload = self._ack_queue.get(timeout=max(0.1, deadline - time.monotonic()))
            except queue.Empty:
                return None
            if payload.get("correlation_id") == correlation_id:
                return payload
        return None

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
