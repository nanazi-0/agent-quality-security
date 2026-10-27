from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class CaptureHandler(BaseHTTPRequestHandler):
    payloads: list[dict[str, object]] = []

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).payloads.append({
            "path": self.path,
            "content_type": self.headers.get("Content-Type"),
            "bytes": len(body),
        })
        self.send_response(200)
        self.end_headers()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    capture = ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
    capture_thread = threading.Thread(target=capture.serve_forever, daemon=True)
    capture_thread.start()
    host, port = capture.server_address
    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"http://{host}:{port}/v1/traces"

    from agent_quality.demo_server import create_server
    from agent_quality.telemetry import force_flush

    demo = create_server()
    demo_thread = threading.Thread(target=demo.serve_forever, daemon=True)
    demo_thread.start()
    demo_host, demo_port = demo.server_address
    try:
        request = urllib.request.Request(
            f"http://{demo_host}:{demo_port}/agent",
            data=json.dumps({"message": "请取消订单42"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                return 1
        force_flush()
        deadline = time.time() + 5
        while not CaptureHandler.payloads and time.time() < deadline:
            time.sleep(0.05)
        report = {
            "passed": bool(CaptureHandler.payloads),
            "exporter": "otlp-http/protobuf",
            "openinference_attributes": ["openinference.span.kind", "input.value", "output.value", "tool.name"],
            "requests": CaptureHandler.payloads,
        }
        output = root / "reports" / "telemetry" / "results.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["passed"] else 1
    finally:
        demo.shutdown()
        demo.server_close()
        capture.shutdown()
        capture.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
