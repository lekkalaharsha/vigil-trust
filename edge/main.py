"""Edge gateway entrypoint.

    .venv/Scripts/python.exe -m edge.main --mode simulator
    .venv/Scripts/python.exe -m edge.main --mode replay --replay-log data/synthetic_can.log
    .venv/Scripts/python.exe -m edge.main --mode pcan
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from edge.acquisition.base import AcquisitionSource
from edge.acquisition.replay import ReplaySource
from edge.acquisition.simulator import SimulatorSource
from edge.api.metrics_server import EdgeMetricsServer
from edge.config import load_edge_config
from edge.pipeline import Drainer
from edge.queue.checkpoint_store import CheckpointStore
from edge.queue.sqlite_queue import SqliteQueue
from edge.transport.https import HttpsTransport
from edge.trust.envelope import GatewayState
from edge.trust.identity import load_identity_from_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vigil.edge")


def build_source(mode: str, replay_log: str) -> AcquisitionSource:
    if mode == "simulator":
        return SimulatorSource(frame_count=None, realtime=True)
    if mode == "replay":
        return ReplaySource(replay_log)
    if mode == "pcan":
        from edge.acquisition.pcan import PcanSource

        return PcanSource()
    if mode == "socketcan":
        from edge.acquisition.socketcan import SocketCanSource

        return SocketCanSource()
    if mode == "unoq":
        from edge.acquisition.unoq import UnoQBridgeSource

        return UnoQBridgeSource()
    raise ValueError(f"unknown acquisition mode: {mode!r}")


def run(mode: str | None = None, replay_log: str | None = None, max_frames: int | None = None) -> int:
    config = load_edge_config()
    mode = mode or config.acquisition_mode
    replay_log = replay_log or config.replay_log_path

    try:
        identity = load_identity_from_files(config.device_key_path)
    except FileNotFoundError:
        logger.error(
            "device key not found at %s. Run scripts/dev_pki.py --device %s first.",
            config.device_key_path,
            config.gateway_id,
        )
        return 1

    gateway_state = GatewayState(
        gateway_id=config.gateway_id,
        vehicle_profile_id=config.vehicle_profile_id,
        private_key=identity.private_key,
        batch_size=config.batch_size,
    )
    queue = SqliteQueue(config.queue_db_path)
    checkpoint_store = CheckpointStore(config.checkpoint_db_path)
    transport = HttpsTransport(base_url=config.backend_url)
    drainer = Drainer(config.gateway_id, queue, checkpoint_store, transport, identity.private_key)

    metrics_state = {"frames_signed": 0, "last_drain": None}

    def get_metrics() -> dict:
        return {
            "gateway_id": config.gateway_id,
            "boot_epoch": gateway_state.boot_epoch,
            "sequence": gateway_state.sequence,
            "queue_depth": queue.depth(),
            "frames_signed": metrics_state["frames_signed"],
            "last_drain": metrics_state["last_drain"],
        }

    metrics_server = EdgeMetricsServer(get_metrics)
    metrics_server.start()
    logger.info("edge metrics: http://127.0.0.1:9100/metrics")

    source = build_source(mode, replay_log)
    frame_count = 0
    last_drain_time = 0.0
    try:
        with source:
            for frame in source.frames():
                envelope = gateway_state.build_and_sign(frame)
                queue.enqueue(envelope)
                metrics_state["frames_signed"] += 1
                frame_count += 1

                now = time.monotonic()
                if now - last_drain_time >= config.drain_interval_s:
                    result = drainer.drain_once()
                    metrics_state["last_drain"] = {
                        "attempted": result.attempted,
                        "accepted": result.accepted,
                        "rejected": result.rejected,
                        "transport_error": result.transport_error,
                    }
                    if result.attempted:
                        logger.info(
                            "drain: attempted=%d accepted=%d rejected=%d error=%s",
                            result.attempted, result.accepted, result.rejected, result.transport_error,
                        )
                    last_drain_time = now

                if max_frames is not None and frame_count >= max_frames:
                    break
        # Final drain so a bounded demo run (replay/simulator with
        # max_frames) does not leave the queue non-empty.
        while queue.depth() > 0:
            result = drainer.drain_once()
            if result.transport_error or result.attempted == 0:
                break
        final_depth = queue.depth()
    finally:
        transport.close()
        queue.close()
        metrics_server.stop()

    logger.info("processed %d frames, final queue depth=%d", frame_count, final_depth)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["simulator", "replay", "pcan", "socketcan", "unoq"], default=None)
    parser.add_argument("--replay-log", default=None)
    parser.add_argument("--max-frames", type=int, default=None, help="stop after N frames (demo/testing)")
    args = parser.parse_args(argv)
    return run(mode=args.mode, replay_log=args.replay_log, max_frames=args.max_frames)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
