PY := .venv/Scripts/python.exe

.PHONY: venv install test unit integration security pki backend-key register edge backend demo attack-lab clean

venv:
	python -m venv .venv

install:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest tests -v

unit:
	$(PY) -m pytest tests/unit -v

integration:
	$(PY) -m pytest tests/integration -v

security:
	$(PY) -m pytest tests/security -v

pki:
	$(PY) scripts/generate_backend_key.py
	$(PY) scripts/dev_pki.py --device gw-demo-01
	$(PY) scripts/register_device.py --device-id gw-demo-01 \
		--public-key-path certs/devices/gw-demo-01.pub.pem --vehicle-profile demo-v1 \
		--db-path data/backend/registry.db

backend:
	$(PY) -m backend.main

edge:
	$(PY) -m edge.main --mode simulator

edge-replay:
	$(PY) -m edge.main --mode replay --replay-log data/synthetic_can.log

attack-lab:
	$(PY) -m attack_lab.spoof_identity
	$(PY) -m attack_lab.tamper
	$(PY) -m attack_lab.replay
	$(PY) -m attack_lab.duplicate
	$(PY) -m attack_lab.reorder
	$(PY) -m attack_lab.batch_root_forgery
	$(PY) -m attack_lab.checkpoint_mismatch
	$(PY) -m attack_lab.device_revocation
	$(PY) -m attack_lab.outage_reconnect

benchmark:
	$(PY) scripts/benchmark.py

clean:
	rm -rf data/edge data/backend __pycache__ .pytest_cache
