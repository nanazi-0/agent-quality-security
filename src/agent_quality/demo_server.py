from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .telemetry import configure_tracing, span


DEMO_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>智能体质量验收演示</title>
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
  <main>
    <h1>智能体质量验收演示</h1>
    <form id="agent-form">
      <label for="message">任务内容</label>
      <textarea id="message" name="message" required>请取消订单42</textarea>
      <button type="submit">发送</button>
    </form>
    <section id="result" role="status" aria-live="polite">等待任务</section>
  </main>
  <script src="/assets/app.js" defer></script>
</body>
</html>"""

DEMO_CSS = """body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 3rem auto; padding: 0 1rem; color: #172033; }
label, textarea, button { display: block; width: 100%; box-sizing: border-box; }
textarea { min-height: 7rem; margin: .5rem 0 1rem; padding: .75rem; }
button { padding: .75rem; color: white; background: #175cd3; border: 0; border-radius: .4rem; }
#result { margin-top: 1rem; padding: 1rem; background: #f1f5f9; min-height: 1.5rem; }
"""

DEMO_JS = """document.querySelector('#agent-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const result = document.querySelector('#result');
  result.textContent = '处理中';
  const response = await fetch('/agent', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: document.querySelector('#message').value})
  });
  const payload = await response.json();
  result.textContent = payload.message;
});
"""


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "AgentQualityDemo"
    sys_version = ""
    state: dict[str, Any] = {"order_id": "42", "status": "active", "cancel_count": 0}

    def log_message(self, format: str, *args: object) -> None:
        return

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, data, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; manifest-src 'self'; worker-src 'none'")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        with span("http.get", {"http.request.method": "GET", "url.path": self.path}):
            if self.path == "/":
                self._send_bytes(200, DEMO_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/assets/app.css":
                self._send_bytes(200, DEMO_CSS.encode("utf-8"), "text/css; charset=utf-8")
            elif self.path == "/assets/app.js":
                self._send_bytes(200, DEMO_JS.encode("utf-8"), "text/javascript; charset=utf-8")
            elif self.path == "/health":
                self._send(200, {"status": "ok"})
            elif self.path == "/state/orders/42":
                self._send(200, self.state)
            else:
                self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:
        with span("http.post", {"http.request.method": "POST", "url.path": self.path}) as current:
            body = self._body()
            if self.path == "/reset":
                type(self).state = {"order_id": "42", "status": "active", "cancel_count": 0}
                self._send(200, self.state)
                return
            if self.path != "/agent":
                self._send(404, {"error": "not_found"})
                return
            prompt = str(body.get("message", "")).lower()
            current.set_attribute("openinference.span.kind", "AGENT")
            current.set_attribute("input.value", prompt)
            if "ignore" in prompt or "system prompt" in prompt or "越权" in prompt:
                current.set_attribute("agent.refused", True)
                self._send(200, {"message": "请求被安全策略拒绝", "refused": True, "tool_calls": []})
                return
            if "42" in prompt and ("取消" in prompt or "cancel" in prompt):
                state = type(self).state
                if state["status"] != "cancelled":
                    state["status"] = "cancelled"
                    state["cancel_count"] += 1
                current.set_attribute("tool.name", "cancel_order")
                current.set_attribute("output.value", "订单42已取消")
                self._send(200, {
                    "message": "订单42已取消",
                    "refused": False,
                    "tool_calls": [{"name": "cancel_order", "arguments": {"order_id": "42"}}],
                })
                return
            if "退款政策" in prompt or "refund policy" in prompt:
                current.set_attribute("openinference.span.kind", "RETRIEVER")
                current.set_attribute("retrieval.document_count", 1)
                current.set_attribute("output.value", "订单取消后，退款将在3个工作日内原路退回")
                self._send(200, {
                    "message": "订单取消后，退款将在3个工作日内原路退回",
                    "refused": False,
                    "tool_calls": [],
                    "citations": [{"id": "refund-policy-v1", "title": "退款政策"}],
                })
                return
            current.set_attribute("agent.refused", True)
            self._send(200, {"message": "无法完成该任务", "refused": True, "tool_calls": []})


def create_server() -> ThreadingHTTPServer:
    configure_tracing()
    return ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
