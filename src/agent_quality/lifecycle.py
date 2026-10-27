from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LifecycleStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data_dir = root / "data"
        self.database = self.data_dir / "quality.db"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, generated_at TEXT NOT NULL, gate_passed INTEGER NOT NULL,
                    config TEXT NOT NULL, report_path TEXT NOT NULL, report_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checks (
                    run_id TEXT NOT NULL, check_id TEXT NOT NULL, layer TEXT NOT NULL,
                    required INTEGER NOT NULL, passed INTEGER NOT NULL, skipped INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL, detail TEXT NOT NULL, evidence_path TEXT,
                    evidence_sha256 TEXT, PRIMARY KEY (run_id, check_id)
                );
                CREATE TABLE IF NOT EXISTS failures (
                    failure_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    layer TEXT NOT NULL, risk TEXT, fingerprint TEXT NOT NULL, status TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, status TEXT NOT NULL,
                    actor TEXT NOT NULL, reason TEXT NOT NULL, report_sha256 TEXT NOT NULL,
                    rollback_plan TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE
                );
                """
            )

    def _audit(self, db: sqlite3.Connection, event_type: str, subject_id: str, payload: dict[str, Any]) -> None:
        previous = db.execute("SELECT event_hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else "GENESIS"
        created_at = _now()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        material = f"{previous_hash}|{event_type}|{subject_id}|{created_at}|{payload_json}".encode()
        event_hash = hashlib.sha256(material).hexdigest()
        db.execute(
            "INSERT INTO audit(event_type, subject_id, payload_json, created_at, previous_hash, event_hash) VALUES(?,?,?,?,?,?)",
            (event_type, subject_id, payload_json, created_at, previous_hash, event_hash),
        )

    def record_run(self, report: dict[str, Any], report_path: Path) -> None:
        run_id = report["run_id"]
        report_hash = _sha256(report_path)
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?)",
                (run_id, report["generated_at"], int(report["gate_passed"]), report["config"], str(report_path), report_hash),
            )
            db.execute("DELETE FROM checks WHERE run_id=?", (run_id,))
            db.execute("DELETE FROM failures WHERE run_id=?", (run_id,))
            for check in report["checks"]:
                evidence = check.get("evidence") or {}
                db.execute(
                    "INSERT INTO checks VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id, check["id"], check["layer"], int(check["required"]), int(check["passed"]),
                        int(check["skipped"]), check["duration_seconds"], check["detail"],
                        evidence.get("path"), evidence.get("sha256"),
                    ),
                )
                if not check["passed"]:
                    self._insert_failure(db, run_id, check["id"], check["layer"], None, check)
                self._ingest_case_failures(db, run_id, check)
            self._audit(db, "run_recorded", run_id, {"gate_passed": report["gate_passed"], "report_sha256": report_hash})

    def _insert_failure(
        self, db: sqlite3.Connection, run_id: str, item_id: str, layer: str,
        risk: str | None, payload: dict[str, Any],
    ) -> None:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256(f"{item_id}|{layer}|{normalized}".encode()).hexdigest()
        failure_id = f"fail-{fingerprint[:16]}-{run_id}"
        db.execute(
            "INSERT OR IGNORE INTO failures VALUES(?,?,?,?,?,?,?,?,?)",
            (failure_id, run_id, item_id, layer, risk, fingerprint, "open", normalized, _now()),
        )

    def _ingest_case_failures(self, db: sqlite3.Connection, run_id: str, check: dict[str, Any]) -> None:
        evidence = check.get("evidence") or {}
        if not evidence.get("path"):
            return
        path = Path(evidence["path"])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        results = payload.get("results", [])
        if not isinstance(results, list):
            return
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get("passed"), bool) or not result.get("id"):
                continue
            if not result["passed"]:
                self._insert_failure(db, run_id, result["id"], "business-outcome", result.get("risk"), result)

    def decide_release(
        self, run_id: str, actor: str, reason: str, approve: bool,
        rollback_plan: str,
    ) -> dict[str, Any]:
        with self._connect() as db:
            if run_id == "latest":
                row = db.execute("SELECT * FROM runs ORDER BY generated_at DESC LIMIT 1").fetchone()
            else:
                row = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise ValueError(f"run not found: {run_id}")
            if not row["gate_passed"]:
                status = "blocked"
            elif approve:
                if not actor or actor == "automation":
                    raise ValueError("human approval requires a named actor")
                status = "approved"
            else:
                status = "eligible"
            decision = {
                "decision_id": f"decision-{uuid4().hex}",
                "run_id": row["run_id"],
                "status": status,
                "actor": actor,
                "reason": reason,
                "report_sha256": row["report_sha256"],
                "rollback_plan": rollback_plan,
                "created_at": _now(),
            }
            db.execute(
                "INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?)",
                tuple(decision[key] for key in ("decision_id", "run_id", "status", "actor", "reason", "report_sha256", "rollback_plan", "created_at")),
            )
            self._audit(db, "release_decision", decision["decision_id"], decision)
        release_dir = self.root / "reports" / "releases"
        release_dir.mkdir(parents=True, exist_ok=True)
        (release_dir / f"{decision['decision_id']}.json").write_text(
            json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return decision

    def export_feedback(self, destination: Path) -> int:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM failures WHERE status='open' ORDER BY created_at").fetchall()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
        return len(rows)

    def list_failures(self, status: str = "open") -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM failures WHERE status=? ORDER BY created_at", (status,)
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_failure(
        self, failure_id: str, actor: str, resolution: str, regression_case: Path,
    ) -> dict[str, Any]:
        if not actor or actor == "automation":
            raise ValueError("failure resolution requires a named actor")
        if not regression_case.exists():
            raise ValueError(f"regression case does not exist: {regression_case}")
        payload = {
            "failure_id": failure_id,
            "actor": actor,
            "resolution": resolution,
            "regression_case": str(regression_case.resolve()),
            "regression_sha256": _sha256(regression_case),
            "resolved_at": _now(),
        }
        with self._connect() as db:
            row = db.execute("SELECT status FROM failures WHERE failure_id=?", (failure_id,)).fetchone()
            if row is None:
                raise ValueError(f"failure not found: {failure_id}")
            if row["status"] != "open":
                raise ValueError(f"failure is not open: {failure_id}")
            db.execute("UPDATE failures SET status='resolved' WHERE failure_id=?", (failure_id,))
            self._audit(db, "failure_resolved", failure_id, payload)
        return payload

    def write_prometheus(self, destination: Path) -> None:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            passed = db.execute("SELECT COUNT(*) FROM runs WHERE gate_passed=1").fetchone()[0]
            failures = db.execute("SELECT COUNT(*) FROM failures WHERE status='open'").fetchone()[0]
            approved = db.execute("SELECT COUNT(*) FROM decisions WHERE status='approved'").fetchone()[0]
        content = (
            "# TYPE agent_quality_runs_total counter\n"
            f"agent_quality_runs_total {total}\n"
            "# TYPE agent_quality_runs_passed_total counter\n"
            f"agent_quality_runs_passed_total {passed}\n"
            "# TYPE agent_quality_open_failures gauge\n"
            f"agent_quality_open_failures {failures}\n"
            "# TYPE agent_quality_approved_releases_total counter\n"
            f"agent_quality_approved_releases_total {approved}\n"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def write_dashboard(self, destination: Path) -> None:
        with self._connect() as db:
            runs = db.execute("SELECT * FROM runs ORDER BY generated_at DESC LIMIT 50").fetchall()
            decisions = db.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 50").fetchall()
            open_failures = db.execute("SELECT COUNT(*) FROM failures WHERE status='open'").fetchone()[0]
        run_rows = "".join(
            f"<tr><td>{html.escape(row['run_id'])}</td><td>{html.escape(row['generated_at'])}</td>"
            f"<td>{'PASS' if row['gate_passed'] else 'FAIL'}</td><td><code>{html.escape(row['report_sha256'][:16])}</code></td></tr>"
            for row in runs
        )
        decision_rows = "".join(
            f"<tr><td>{html.escape(row['run_id'])}</td><td>{html.escape(row['status'])}</td>"
            f"<td>{html.escape(row['actor'])}</td><td>{html.escape(row['created_at'])}</td></tr>"
            for row in decisions
        )
        document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>Quality Governance</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:1200px}}table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}td,th{{border:1px solid #ddd;padding:.5rem;text-align:left}}</style></head>
<body><h1>智能体质量治理看板</h1><p>未关闭失败：<strong>{open_failures}</strong></p>
<h2>评测运行</h2><table><tr><th>Run</th><th>时间</th><th>门禁</th><th>证据哈希</th></tr>{run_rows}</table>
<h2>发布决策</h2><table><tr><th>Run</th><th>状态</th><th>操作者</th><th>时间</th></tr>{decision_rows}</table></body></html>"""
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")

    def verify_audit(self) -> tuple[bool, int]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM audit ORDER BY sequence").fetchall()
        previous_hash = "GENESIS"
        for row in rows:
            if row["previous_hash"] != previous_hash:
                return False, row["sequence"]
            material = (
                f"{row['previous_hash']}|{row['event_type']}|{row['subject_id']}|"
                f"{row['created_at']}|{row['payload_json']}"
            ).encode()
            if hashlib.sha256(material).hexdigest() != row["event_hash"]:
                return False, row["sequence"]
            previous_hash = row["event_hash"]
        return True, len(rows)
