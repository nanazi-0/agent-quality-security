from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_quality.lifecycle import LifecycleStore


class LifecycleTests(unittest.TestCase):
    def test_non_case_results_do_not_break_run_ingestion(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        root = project_root / ".runtime" / "tests" / f"lifecycle-{uuid4().hex}"
        evidence = root / "scanner.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_text(json.dumps({"results": {"scanner": "summary"}}), encoding="utf-8")
        report_dir = root / "reports" / "run-scanner"
        report_dir.mkdir(parents=True)
        report = {
            "run_id": "run-scanner", "generated_at": "2026-10-10T00:00:00+00:00",
            "gate_passed": True, "config": "test",
            "checks": [{
                "id": "scanner", "layer": "software-security", "required": True,
                "passed": True, "skipped": False, "duration_seconds": 1.0,
                "detail": "ok", "evidence": {"path": str(evidence), "sha256": "test"},
            }],
        }
        report_path = report_dir / "gate-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        store = LifecycleStore(root)
        store.record_run(report, report_path)
        self.assertEqual(store.list_failures("open"), [])

    def test_run_decision_feedback_and_audit(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        root = project_root / ".runtime" / "tests" / f"lifecycle-{uuid4().hex}"
        report_dir = root / "reports" / "run-1"
        report_dir.mkdir(parents=True)
        report = {
            "run_id": "run-1", "generated_at": "2026-10-10T00:00:00+00:00",
            "gate_passed": False, "config": "test",
            "checks": [{
                "id": "security", "layer": "agent-security", "required": True,
                "passed": False, "skipped": False, "duration_seconds": 1.0,
                "detail": "attack succeeded", "evidence": None,
            }],
        }
        report_path = report_dir / "gate-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        store = LifecycleStore(root)
        store.record_run(report, report_path)
        destination = root / "feedback.jsonl"
        self.assertEqual(store.export_feedback(destination), 1)
        decision = store.decide_release("latest", "automation", "gate failed", False, "rollback")
        self.assertEqual(decision["status"], "blocked")
        passed, count = store.verify_audit()
        self.assertTrue(passed)
        self.assertEqual(count, 2)

        regression = root / "regression.json"
        regression.write_text('{"case":"security"}', encoding="utf-8")
        failure_id = store.list_failures("open")[0]["failure_id"]
        resolved = store.resolve_failure(failure_id, "security-reviewer", "fixed policy", regression)
        self.assertEqual(resolved["failure_id"], failure_id)
        self.assertEqual(store.list_failures("open"), [])
        passed, count = store.verify_audit()
        self.assertTrue(passed)
        self.assertEqual(count, 3)
