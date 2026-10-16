#!/usr/bin/env python
"""Register a device (gateway) in the backend device registry.

device_id is an operator-assigned label (e.g. "gw-demo-01", matching
scripts/dev_pki.py --device and VIGIL_GATEWAY_ID in .env.example) -- the
registry is the source of truth binding that label to a public key, the
same way scripts/dev_pki.py's demo CA binds a certificate CN to a key. It
does not need to equal edge.trust.identity.device_id_from_public_key(); the
edge gateway and backend just both need to agree on the same device_id
string for a given keypair.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.device_registry.registry import TRUSTED, DeviceRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--public-key-path", required=True)
    parser.add_argument("--vehicle-profile", default="demo-v1")
    parser.add_argument("--db-path", default="data/backend/registry.db")
    args = parser.parse_args(argv)

    public_key_pem = Path(args.public_key_path).read_text(encoding="ascii")
    registry = DeviceRegistry(args.db_path)
    registry.register(args.device_id, args.vehicle_profile, public_key_pem, status=TRUSTED)
    registry.close()
    print(f"[register_device] registered {args.device_id} (status=trusted) in {args.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
