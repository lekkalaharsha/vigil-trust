"""Tiny localhost-only metrics endpoint for the edge gateway.

Uses the stdlib http.server instead of pulling in another ASGI server
thread just for one read-only JSON endpoint. Binds to 127.0.0.1 only.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable


def _make_handler(get_metrics: Callable[[], dict]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(get_metrics()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - silence default logging
            return

    return Handler


class EdgeMetricsServer:
    def __init__(self, get_metrics: Callable[[], dict], host: str = "127.0.0.1", port: int = 9100) -> None:
        self._server = HTTPServer((host, port), _make_handler(get_metrics))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
