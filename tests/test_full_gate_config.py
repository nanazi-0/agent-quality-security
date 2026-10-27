from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class FullGateConfigTests(unittest.TestCase):
    def test_all_selected_dimensions_are_required(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = tomllib.loads((root / "quality-gates.toml").read_text(encoding="utf-8"))
        checks = {check["id"]: check for check in config["checks"]}
        expected = {
            "unit-tests",
            "business-outcome-and-safety-demo",
            "telemetry-openinference",
            "phoenix-trace-ingestion",
            "agent-security-promptfoo",
            "web-ui-accessibility",
            "performance-smoke",
            "source-security",
            "dependency-secret-misconfig",
            "web-dynamic-security",
        }
        self.assertEqual(set(checks), expected)
        self.assertTrue(all(check["required"] for check in checks.values()))
        for check_id, check in checks.items():
            if check_id != "unit-tests":
                self.assertTrue(check.get("evidence_required"), check_id)
                self.assertIn("evidence", check, check_id)


if __name__ == "__main__":
    unittest.main()
