from __future__ import annotations

import os
import sys
import threading
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_quality.case_runner import run_suite
from agent_quality.demo_server import create_server


class EndToEndTests(unittest.TestCase):
    def test_demo_suite_checks_authoritative_outcomes(self) -> None:
        server = create_server()
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        old = os.environ.get("TARGET_BASE_URL")
        os.environ["TARGET_BASE_URL"] = f"http://{host}:{port}"
        try:
            root = Path(__file__).resolve().parents[1]
            output = root / ".runtime" / "tests" / f"e2e-{uuid4().hex}"
            report, passed = run_suite(root / "cases" / "demo-suite.json", output)
            self.assertTrue(passed)
            self.assertEqual(report["summary"]["passed"], 4)
            self.assertEqual(report["summary"]["failed"], 0)
        finally:
            server.shutdown()
            server.server_close()
            if old is None:
                os.environ.pop("TARGET_BASE_URL", None)
            else:
                os.environ["TARGET_BASE_URL"] = old
