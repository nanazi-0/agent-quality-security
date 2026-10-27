from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from .case_runner import run_suite
from .demo_server import create_server
from .lifecycle import LifecycleStore
from .pipeline import run_pipeline
from .platforms import load_catalog, summarize


TOOLS = ["node", "npx", "docker", "k6", "semgrep", "trivy"]


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def doctor() -> int:
    print(f"python={sys.version.split()[0]}")
    print(f"project_root={_root()}")
    for tool in TOOLS:
        print(f"{tool}={shutil.which(tool) or 'not-installed (optional)'}")
    print(f"TARGET_BASE_URL={os.environ.get('TARGET_BASE_URL', 'not-set')}")
    return 0


def case_run(path: Path, output: Path) -> int:
    report, passed = run_suite(path, output)
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"CASE_GATE={'PASS' if passed else 'FAIL'}")
    print(f"report={output / 'case-results.json'}")
    return 0 if passed else 1


def demo() -> int:
    server = create_server()
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    previous = os.environ.get("TARGET_BASE_URL")
    os.environ["TARGET_BASE_URL"] = f"http://{host}:{port}"
    try:
        return case_run(_root() / "cases" / "demo-suite.json", _root() / "reports" / "demo")
    finally:
        server.shutdown()
        server.server_close()
        if previous is None:
            os.environ.pop("TARGET_BASE_URL", None)
        else:
            os.environ["TARGET_BASE_URL"] = previous


def pipeline_run(config: Path, output: Path) -> int:
    report, passed, report_dir = run_pipeline(config, _root(), output)
    store = LifecycleStore(_root())
    store.record_run(report, report_dir / "gate-report.json")
    feedback_path = report_dir / "feedback-queue.jsonl"
    failure_count = store.export_feedback(feedback_path)
    store.write_dashboard(_root() / "reports" / "dashboard.html")
    store.write_prometheus(_root() / "reports" / "quality.prom")
    for check in report["checks"]:
        status = "PASS" if check["passed"] else ("SKIP" if check["skipped"] else "FAIL")
        print(f"[{status}] {check['layer']}/{check['id']}: {check['detail']}")
    print(f"QUALITY_GATE={'PASS' if passed else 'FAIL'}")
    print(f"report={report_dir / 'gate-report.html'}")
    print(f"open_failures={failure_count}")
    print(f"dashboard={_root() / 'reports' / 'dashboard.html'}")
    return 0 if passed else 1


def platform_coverage() -> int:
    catalog = load_catalog(_root() / "integrations" / "platforms.json")
    summary = summarize(catalog)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for platform in catalog:
        print(f"[{platform['status']}] {platform['capability']}: {platform['name']} - {platform['role']}")
    output = _root() / "reports" / "platform-coverage.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "platforms": catalog}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={output}")
    return 0


def release_decision(run_id: str, actor: str, reason: str, approve: bool, rollback_plan: str) -> int:
    decision = LifecycleStore(_root()).decide_release(run_id, actor, reason, approve, rollback_plan)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 1 if decision["status"] == "blocked" else 0


def audit_verify() -> int:
    passed, count = LifecycleStore(_root()).verify_audit()
    print(f"AUDIT_CHAIN={'PASS' if passed else 'FAIL'} events={count}")
    return 0 if passed else 1


def failure_list(status: str) -> int:
    failures = LifecycleStore(_root()).list_failures(status)
    print(json.dumps(failures, ensure_ascii=False, indent=2))
    return 0


def failure_resolve(failure_id: str, actor: str, resolution: str, regression_case: Path) -> int:
    payload = LifecycleStore(_root()).resolve_failure(failure_id, actor, resolution, regression_case)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def external_ingest(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    catalog = load_catalog(_root() / "integrations" / "platforms.json")
    known = {item["name"] for item in catalog}
    if payload.get("platform") not in known:
        raise ValueError(f"platform is not registered: {payload.get('platform')}")
    for field in ("platform", "layer", "passed", "summary"):
        if field not in payload:
            raise ValueError(f"external result missing field: {field}")
    run_id = payload.get("run_id") or datetime.now(timezone.utc).strftime("external-%Y%m%dT%H%M%SZ")
    report_dir = _root() / "reports" / "external" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_copy = report_dir / "external-result.json"
    evidence_copy.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "schema_version": "1.0", "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": f"external:{payload['platform']}", "gate_passed": bool(payload["passed"]),
        "checks": [{
            "id": payload.get("check_id", payload["platform"]), "layer": payload["layer"],
            "required": bool(payload.get("required", True)), "passed": bool(payload["passed"]),
            "skipped": False, "duration_seconds": float(payload.get("duration_seconds", 0)),
            "detail": payload["summary"], "command": ["external-ingest"],
            "log_path": None,
            "evidence": {"path": str(evidence_copy.resolve()), "sha256": __import__("hashlib").sha256(evidence_copy.read_bytes()).hexdigest()},
        }],
    }
    report_path = report_dir / "gate-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    store = LifecycleStore(_root())
    store.record_run(report, report_path)
    store.write_dashboard(_root() / "reports" / "dashboard.html")
    store.write_prometheus(_root() / "reports" / "quality.prom")
    print(f"EXTERNAL_GATE={'PASS' if report['gate_passed'] else 'FAIL'} run_id={run_id}")
    return 0 if report["gate_passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent quality and security acceptance gates")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("demo")
    sub.add_parser("platform-coverage")
    sub.add_parser("audit-verify")
    failures = sub.add_parser("failure-list")
    failures.add_argument("--status", default="open")
    resolve = sub.add_parser("failure-resolve")
    resolve.add_argument("failure_id")
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--resolution", required=True)
    resolve.add_argument("--regression-case", type=Path, required=True)
    ingest = sub.add_parser("external-ingest")
    ingest.add_argument("result", type=Path)
    case = sub.add_parser("case-run")
    case.add_argument("suite", type=Path)
    case.add_argument("--output", type=Path, default=_root() / "reports" / "cases")
    pipeline = sub.add_parser("pipeline")
    pipeline.add_argument("--config", type=Path, default=_root() / "quality-gates.toml")
    pipeline.add_argument("--output", type=Path, default=_root() / "reports")
    release = sub.add_parser("release-decide")
    release.add_argument("--run-id", default="latest")
    release.add_argument("--actor", default="automation")
    release.add_argument("--reason", default="Automated gate result")
    release.add_argument("--approve", action="store_true")
    release.add_argument("--rollback-plan", default="Stop rollout and restore the last approved version")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "demo":
        return demo()
    if args.command == "platform-coverage":
        return platform_coverage()
    if args.command == "audit-verify":
        return audit_verify()
    if args.command == "failure-list":
        return failure_list(args.status)
    if args.command == "failure-resolve":
        return failure_resolve(args.failure_id, args.actor, args.resolution, args.regression_case)
    if args.command == "external-ingest":
        return external_ingest(args.result)
    if args.command == "case-run":
        return case_run(args.suite, args.output)
    if args.command == "pipeline":
        return pipeline_run(args.config, args.output)
    if args.command == "release-decide":
        return release_decision(args.run_id, args.actor, args.reason, args.approve, args.rollback_plan)
    return 2
