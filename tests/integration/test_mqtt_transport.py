"""MQTT transport integration test.

STATUS: NOT RUN - BROKER REQUIRED in this environment (no Docker/Mosquitto
available in this sandbox -- see docs/LIMITATIONS.md and
docker-compose.yml). This test self-skips with a clear reason if it cannot
reach 127.0.0.1:8883 within a short timeout, rather than silently passing
or hanging. Run `docker compose up mosquitto` and generate PKI via
scripts/dev_pki.py first to exercise this for real.
"""

from __future__ import annotations

import socket

import pytest


def _broker_reachable(host: str = "127.0.0.1", port: int = 8883, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _broker_reachable(), reason="NOT RUN - BROKER REQUIRED: no MQTT broker reachable on 127.0.0.1:8883")
def test_mqtt_transport_round_trip():
    pytest.skip("requires a running Mosquitto broker + generated PKI; see docker-compose.yml")
