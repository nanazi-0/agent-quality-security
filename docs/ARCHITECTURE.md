# Architecture

```text
test assets -> qualityctl -> agent endpoint -> authoritative state endpoint
                    |              |
                    |              +-> response/tool trajectory assertions
                    +-> software / security / performance commands
                                   |
                                   +-> JSON, logs and HTML evidence
```

The core runner has no third-party Python dependencies. External engines remain replaceable command adapters:

- Promptfoo: agent and RAG adversarial testing;
- Playwright: browser behavior and accessibility integration;
- k6: latency, reliability and capacity thresholds;
- Semgrep/CodeQL, Trivy and ZAP: traditional application security;
- Phoenix or MLflow: optional trace storage, experiments and online evaluation.

## Trust boundaries

1. Agent text is untrusted and never proves a business action completed.
2. Outcome checks read an authoritative API or database projection.
3. Red-team tests run outside production with scoped credentials.
4. Required tools missing from a production profile fail closed.
5. Reports contain evidence metadata but must not store secrets or raw personal data.

