"""API health/metrics endpoints -- uses the same harness as everything else."""


def test_health_endpoint(harness):
    response = harness.http_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_endpoint_reflects_state(harness):
    response = harness.http_client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["trusted_event_count"] == 0
    assert body["device_count"] == 1


def test_devices_endpoint(harness):
    response = harness.http_client.get("/devices")
    assert response.status_code == 200
    devices = response.json()
    assert len(devices) == 1
    assert devices[0]["device_id"] == harness.gateway_id
    assert devices[0]["status"] == "trusted"


def test_dashboard_served_at_root(harness):
    response = harness.http_client.get("/")
    assert response.status_code == 200
    assert "VIGIL-TRUST" in response.text
