from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_quality.platforms import load_catalog, summarize


class PlatformCatalogTests(unittest.TestCase):
    def test_document_platforms_are_registered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        platforms = load_catalog(root / "integrations" / "platforms.json")
        names = {item["name"] for item in platforms}
        required = {
            "OpenTelemetry", "OpenInference", "Phoenix", "MLflow", "Langfuse", "DeepEval", "Ragas",
            "Promptfoo", "PyRIT", "Garak", "Playwright", "Cypress", "Selenium", "Postman/Newman",
            "Bruno", "k6", "JMeter", "Locust", "axe-core", "Lighthouse", "Accessibility Insights",
            "Semgrep CE", "CodeQL", "Trivy", "OWASP ZAP", "Prometheus", "Grafana",
            "GitHub Actions", "GitLab CI", "Jenkins", "TestMu AI", "Datadog", "Dynatrace",
            "Microsoft Foundry/Azure", "AWS Bedrock AgentCore", "Tencent Agent Platform/WeTest",
            "Huawei AgentArts/CodeArts",
        }
        self.assertFalse(required - names)
        self.assertGreaterEqual(summarize(platforms)["total"], len(required))

