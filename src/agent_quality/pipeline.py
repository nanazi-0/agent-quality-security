from __future__ import annotations

import os
import hashlib
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reporting import write_html, write_json


def _run_check(check: dict[str, Any], root: Path, report_dir: Path) -> dict[str, Any]:
    command = [str(item) for item in check["command"]]
    if command[0].lower() in {"python", "python3", "python.exe"}:
        command[0] = sys.executable
    executable = command[0]
    required = bool(check.get("required", True))
    if shutil.which(executable) is None and not (root / executable).exists():
        return {
            "id": check["id"], "layer": check["layer"], "required": required,
            "passed": not required, "skipped": True, "duration_seconds": 0,
            "detail": f"executable not found: {executable}", "command": command,
        }
    started = time.perf_counter()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.update({str(k): str(v) for k, v in check.get("env", {}).items()})
    try:
        result = subprocess.run(
            command,
            cwd=root / check.get("cwd", "."),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(check.get("timeout_seconds", 300)),
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        passed, skipped, detail = result.returncode == 0, False, f"exit_code={result.returncode}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = stdout + stderr
        passed, skipped, detail = False, False, "timeout"
    duration = round(time.perf_counter() - started, 3)
    log_path = report_dir / f"{check['id']}.log"
    log_path.write_text(output, encoding="utf-8")
    evidence_path = root / check["evidence"] if check.get("evidence") else None
    evidence_exists = evidence_path is not None and evidence_path.exists()
    if check.get("evidence_required") and not evidence_exists:
        passed = False
        detail = f"{detail}; required evidence missing"
    evidence = None
    if evidence_exists and evidence_path is not None:
        evidence = {
            "path": str(evidence_path.resolve()),
            "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        }
    return {
        "id": check["id"], "layer": check["layer"], "required": required,
        "passed": passed, "skipped": skipped, "duration_seconds": duration,
        "detail": detail, "command": command, "log_path": str(log_path.resolve()), "evidence": evidence,
    }


def run_pipeline(config_path: Path, root: Path, report_root: Path) -> tuple[dict[str, Any], bool, Path]:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = report_root / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    checks = [_run_check(check, root, report_dir) for check in config.get("checks", [])]
    required_checks = [check for check in checks if check["required"]]
    gate_passed = bool(required_checks) and all(check["passed"] and not check["skipped"] for check in required_checks)
    report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": str(config_path),
        "gate_passed": gate_passed,
        "checks": checks,
    }
    write_json(report, report_dir / "gate-report.json")
    write_html(report, report_dir / "gate-report.html")
    return report, gate_passed, report_dir
