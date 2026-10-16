#!/usr/bin/env python
"""Generate the backend's demo checkpoint-signing key (ECDSA P-256).

This key signs AcceptanceCheckpoint records (edge/trust/checkpoints.py). It
is distinct from device identity keys. Never commit the private key.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from edge.trust.identity import generate_keypair, write_keypair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="certs/backend_signing")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    key = generate_keypair()
    write_keypair(key, out_dir / "checkpoint.key", out_dir / "checkpoint.pub.pem")
    print(f"[generate_backend_key] wrote {out_dir / 'checkpoint.key'} and {out_dir / 'checkpoint.pub.pem'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
