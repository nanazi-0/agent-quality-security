from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path


def get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    phoenix = os.environ.get("PHOENIX_HOST", "http://127.0.0.1:6006")
    status, _ = get(f"{phoenix}/healthz")
    if status != 200:
        return 1
    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"{phoenix}/v1/traces"

    from agent_quality.demo_server import create_server
    from agent_quality.telemetry import force_flush

    demo = create_server()
    thread = threading.Thread(target=demo.serve_forever, daemon=True)
    thread.start()
    host, port = demo.server_address
    try:
        request = urllib.request.Request(
            f"http://{host}:{port}/agent",
            data=json.dumps({"message": "退款政策是什么？"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            agent_status = response.status
        flushed = force_flush()
        time.sleep(1)
        projects_status, projects_body = get(f"{phoenix}/v1/projects")
        report = {
            "passed": status == 200 and agent_status == 200 and flushed and projects_status == 200,
            "phoenix_health_status": status,
            "agent_status": agent_status,
            "otel_flush": flushed,
            "projects_api_status": projects_status,
            "projects_response_preview": projects_body[:1000],
            "trace_endpoint": f"{phoenix}/v1/traces",
        }
        output = root / "reports" / "phoenix" / "results.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["passed"] else 1
    finally:
        demo.shutdown()
        demo.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
