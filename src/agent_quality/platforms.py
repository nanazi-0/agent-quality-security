from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VALID_STATUSES = {"implemented", "configured", "adapter-ready", "catalog-only", "commercial-external"}


def load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    platforms = payload["platforms"]
    names: set[str] = set()
    for platform in platforms:
        if platform["name"] in names:
            raise ValueError(f"duplicate platform: {platform['name']}")
        if platform["status"] not in VALID_STATUSES:
            raise ValueError(f"invalid status for {platform['name']}: {platform['status']}")
        names.add(platform["name"])
    return platforms


def summarize(platforms: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {status: 0 for status in sorted(VALID_STATUSES)}
    by_capability: dict[str, int] = {}
    for platform in platforms:
        by_status[platform["status"]] += 1
        by_capability[platform["capability"]] = by_capability.get(platform["capability"], 0) + 1
    return {"total": len(platforms), "by_status": by_status, "by_capability": by_capability}

