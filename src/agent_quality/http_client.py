from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ValueError(f"required environment variable is missing: {name}")
            return os.environ[name]
        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    return value


def request(spec: dict[str, Any]) -> dict[str, Any]:
    resolved = expand_env(spec)
    method = resolved.get("method", "GET").upper()
    payload = resolved.get("json")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", **resolved.get("headers", {})}
    if data is not None:
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(resolved["url"], data=data, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=float(resolved.get("timeout_seconds", 15))) as response:
            status = response.status
            body_bytes = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        body_bytes = exc.read()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    text = body_bytes.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = None
    return {"status": status, "text": text, "json": parsed, "latency_ms": latency_ms}

