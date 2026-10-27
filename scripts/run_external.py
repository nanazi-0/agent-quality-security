from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = {
    "promptfoo": "ghcr.io/promptfoo/promptfoo@sha256:3001a2cdc6a1cf42b814dd24d59e543cae602ddf01b4ee073db6ce76c6469a72",
    "k6": "grafana/k6@sha256:e66db15b860113878fa74670e31f5e274830b7b6e42c8bff28b2f2d86a257603",
    "semgrep": "semgrep/semgrep@sha256:93963d9295a366f59e4850127b1550400ee7b388f04fe144e4a1f6325d96e01b",
    "trivy": "ghcr.io/aquasecurity/trivy@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa",
    "zap": "ghcr.io/zaproxy/zaproxy@sha256:7aaa659b0d43078febd82e29bad112285c370727e86ab8340444220e17d9f0d2",
}


def command_name(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"required executable is not installed: {name}")
    return resolved


def run(command: list[str], env: dict[str, str] | None = None) -> int:
    print("RUN", " ".join(command))
    return subprocess.run(command, cwd=ROOT, env=env or os.environ.copy(), check=False).returncode


def docker_base(image: str) -> list[str]:
    return [command_name("docker"), "run", "--rm", "--pull=missing", "-v", f"{ROOT}:/work", "-w", "/work", image]


def with_demo(tool: str) -> int:
    from agent_quality.demo_server import create_server

    server = create_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _, port = server.server_address
    local_url = f"http://127.0.0.1:{port}"
    container_url = f"http://host.docker.internal:{port}"
    env = os.environ.copy()
    env["TARGET_BASE_URL"] = local_url
    env["WEB_BASE_URL"] = local_url
    try:
        if tool == "promptfoo":
            output = ROOT / "reports" / "promptfoo" / "results.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            command = docker_base(IMAGES["promptfoo"])
            command[2:2] = [
                "--add-host", "host.docker.internal:host-gateway",
                "-e", f"TARGET_BASE_URL={container_url}",
                "-e", "PROMPTFOO_DISABLE_TELEMETRY=true",
                "-e", "PROMPTFOO_SELF_HOSTED=false",
            ]
            return run(command + [
                "promptfoo", "eval", "-c", "security/promptfooconfig.yaml",
                "--no-cache", "--output", "/work/reports/promptfoo/results.json",
            ])
        if tool == "playwright":
            (ROOT / "reports" / "playwright").mkdir(parents=True, exist_ok=True)
            return run([command_name("npx"), "playwright", "test", "--config", "ui/playwright.config.ts"], env)
        if tool == "k6":
            output = ROOT / "reports" / "k6"
            output.mkdir(parents=True, exist_ok=True)
            command = docker_base(IMAGES["k6"])
            command[2:2] = ["--add-host", "host.docker.internal:host-gateway", "-e", f"TARGET_BASE_URL={container_url}"]
            return run(command + ["run", "--summary-export", "/work/reports/k6/summary.json", "performance/smoke.js"])
        if tool == "zap":
            output = ROOT / "reports" / "zap"
            output.mkdir(parents=True, exist_ok=True)
            command = [
                command_name("docker"), "run", "--rm", "--pull=missing",
                "--add-host", "host.docker.internal:host-gateway",
                "-v", f"{output}:/zap/wrk:rw", IMAGES["zap"],
            ]
            code = run(command + [
                "zap-baseline.py", "-t", container_url, "-m", "1", "-I",
                "-J", "results.json",
            ])
            report_path = output / "results.json"
            if code != 0 or not report_path.exists():
                return code or 1
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            high_alerts = [
                alert for site in payload.get("site", []) for alert in site.get("alerts", [])
                if int(alert.get("riskcode", 0)) >= 3
            ]
            print(f"ZAP_HIGH_ALERTS={len(high_alerts)}")
            return 1 if high_alerts else 0
        raise ValueError(f"unknown demo tool: {tool}")
    finally:
        server.shutdown()
        server.server_close()


def without_demo(tool: str) -> int:
    if tool == "semgrep":
        output = ROOT / "reports" / "semgrep"
        output.mkdir(parents=True, exist_ok=True)
        return run(docker_base(IMAGES["semgrep"]) + [
            "semgrep", "scan", "--config", "security/semgrep.yml", "--error",
            "--json-output", "/work/reports/semgrep/results.json", "src", "scripts",
        ])
    if tool == "trivy":
        output = ROOT / "reports" / "trivy"
        output.mkdir(parents=True, exist_ok=True)
        cache = ROOT / ".runtime" / "trivy-cache"
        cache.mkdir(parents=True, exist_ok=True)
        command = docker_base(IMAGES["trivy"])
        command[-1:-1] = ["-v", f"{cache}:/root/.cache/trivy"]
        return run(command + [
            "fs", "--timeout", "15m", "--db-repository", "ghcr.io/aquasecurity/trivy-db:2",
            "--scanners", "vuln,secret,misconfig", "--exit-code", "1",
            "--severity", "HIGH,CRITICAL",
            "--skip-dirs", "node_modules", "--skip-dirs", ".venv",
            "--skip-dirs", ".runtime", "--skip-dirs", "reports",
            "--format", "json", "--output", "/work/reports/trivy/results.json", "/work",
        ])
    raise ValueError(f"unknown standalone tool: {tool}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=["promptfoo", "playwright", "k6", "semgrep", "trivy", "zap"])
    args = parser.parse_args()
    try:
        if args.tool in {"promptfoo", "playwright", "k6", "zap"}:
            return with_demo(args.tool)
        return without_demo(args.tool)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
