from __future__ import annotations

import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_quality.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_utf8_tool_output_is_preserved_on_windows(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        root = project_root / ".runtime" / "tests" / f"pipeline-{uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        config = root / "gates.toml"
        config.write_text(
            '[[checks]]\nid="utf8"\nlayer="software"\ncommand=["python", "-c", "print(\'智能体通过\')"]\nrequired=true\n',
            encoding="utf-8",
        )
        report, passed, report_dir = run_pipeline(config, root, root / "reports")
        self.assertTrue(passed)
        self.assertTrue(report["checks"][0]["passed"])
        self.assertIn("智能体通过", (report_dir / "utf8.log").read_text(encoding="utf-8"))

    def test_required_missing_tool_fails_closed(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        root = project_root / ".runtime" / "tests" / f"pipeline-{uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        config = root / "gates.toml"
        config.write_text(
            '[[checks]]\nid="missing"\nlayer="security"\ncommand=["definitely-missing-tool"]\nrequired=true\n',
            encoding="utf-8",
        )
        report, passed, report_dir = run_pipeline(config, root, root / "reports")
        self.assertFalse(passed)
        self.assertTrue(report["checks"][0]["skipped"])
        self.assertTrue((report_dir / "gate-report.html").exists())
