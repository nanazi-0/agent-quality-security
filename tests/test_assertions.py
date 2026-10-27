import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_quality.assertions import get_path, run_assertions


class AssertionTests(unittest.TestCase):
    def test_nested_path_with_array(self) -> None:
        value = {"json": {"tool_calls": [{"name": "cancel_order"}]}}
        self.assertEqual(get_path(value, "json.tool_calls[0].name"), "cancel_order")

    def test_assertion_result(self) -> None:
        results = run_assertions({"status": 200}, [{"path": "status", "op": "equals", "expected": 200}])
        self.assertEqual(
            results,
            [{"path": "status", "passed": True, "detail": "actual=200 equals expected=200"}],
        )
