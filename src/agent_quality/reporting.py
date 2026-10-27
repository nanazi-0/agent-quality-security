from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_html(report: dict[str, Any], destination: Path) -> None:
    rows = []
    for check in report["checks"]:
        status = "PASS" if check["passed"] else ("SKIP" if check["skipped"] else "FAIL")
        rows.append(
            "<tr>"
            f"<td>{html.escape(check['id'])}</td>"
            f"<td>{html.escape(check['layer'])}</td>"
            f"<td class='{status.lower()}'>{status}</td>"
            f"<td>{check['duration_seconds']}</td>"
            f"<td><code>{html.escape(check.get('detail', ''))}</code></td>"
            "</tr>"
        )
    gate = "PASS" if report["gate_passed"] else "FAIL"
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Agent Quality Gate</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:1200px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:.55rem;text-align:left}}.pass{{color:#087a32;font-weight:700}}.fail{{color:#b42318;font-weight:700}}.skip{{color:#8a6100;font-weight:700}}code{{white-space:pre-wrap}}</style></head>
<body><h1>智能体质量与安全门禁：<span class="{gate.lower()}">{gate}</span></h1>
<p>运行时间：{html.escape(report['generated_at'])}</p>
<table><thead><tr><th>检查</th><th>层级</th><th>结果</th><th>秒</th><th>说明</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""
    destination.write_text(document, encoding="utf-8")


def write_json(report: dict[str, Any], destination: Path) -> None:
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

