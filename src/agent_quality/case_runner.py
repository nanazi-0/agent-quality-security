from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assertions import run_assertions
from .http_client import request


RISK_LEVELS = {"low", "medium", "high", "critical"}


def _validate_suite(suite: dict[str, Any]) -> None:
    if not isinstance(suite.get("cases"), list) or not suite["cases"]:
        raise ValueError("suite must contain a non-empty cases array")
    identifiers: set[str] = set()
    for case in suite["cases"]:
        for field in ("id", "title", "risk", "invoke"):
            if field not in case:
                raise ValueError(f"case is missing required field: {field}")
        if case["risk"] not in RISK_LEVELS:
            raise ValueError(f"case {case['id']} has invalid risk level")
        if case["id"] in identifiers:
            raise ValueError(f"duplicate case id: {case['id']}")
        identifiers.add(case["id"])


def _record_request(name: str, spec: dict[str, Any], assertions: list[dict[str, Any]]) -> dict[str, Any]:
    response = request(spec)
    checks = run_assertions(response, assertions)
    return {"name": name, "response": response, "assertions": checks, "passed": all(x["passed"] for x in checks)}


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    try:
        for index, setup in enumerate(case.get("setup", []), start=1):
            steps.append(_record_request(f"setup-{index}", setup["request"], setup.get("assertions", [])))
            if not steps[-1]["passed"]:
                break
        else:
            invoke = _record_request("invoke", case["invoke"], case.get("response_assertions", []))
            forbidden = []
            for pattern in case.get("forbidden_response_patterns", []):
                found = pattern.lower() in invoke["response"]["text"].lower()
                forbidden.append({"pattern": pattern, "passed": not found})
            invoke["forbidden_patterns"] = forbidden
            invoke["passed"] = invoke["passed"] and all(item["passed"] for item in forbidden)
            steps.append(invoke)
            for index, outcome in enumerate(case.get("outcome", []), start=1):
                steps.append(_record_request(f"outcome-{index}", outcome["request"], outcome["assertions"]))
        passed = all(step["passed"] for step in steps)
        error = None
    except Exception as exc:
        passed = False
        error = f"{type(exc).__name__}: {exc}"
    return {
        "id": case["id"],
        "title": case["title"],
        "risk": case["risk"],
        "passed": passed,
        "error": error,
        "steps": steps,
    }


def run_suite(path: Path, output_dir: Path) -> tuple[dict[str, Any], bool]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    _validate_suite(suite)
    results = [run_case(case) for case in suite["cases"]]
    total = len(results)
    passed_count = sum(1 for result in results if result["passed"])
    failed_by_risk = {
        risk: sum(1 for result in results if not result["passed"] and result["risk"] == risk)
        for risk in sorted(RISK_LEVELS)
    }
    policy = suite.get("policy", {})
    pass_rate = passed_count / total
    gate_checks = {
        "minimum_pass_rate": pass_rate >= float(policy.get("minimum_pass_rate", 1.0)),
        "critical_failures": failed_by_risk["critical"] <= int(policy.get("max_critical_failures", 0)),
        "high_failures": failed_by_risk["high"] <= int(policy.get("max_high_failures", 0)),
    }
    gate_passed = all(gate_checks.values())
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite": suite.get("name", path.stem),
        "summary": {
            "total": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "pass_rate": round(pass_rate, 4),
            "failed_by_risk": failed_by_risk,
        },
        "gate_checks": gate_checks,
        "gate_passed": gate_passed,
        "results": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "case-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, gate_passed

