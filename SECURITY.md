# Security policy

- Run adversarial tests only against systems you are authorized to test.
- Use isolated test tenants, scoped credentials and synthetic data.
- Do not write API keys into suites, reports or tool configuration files.
- Treat model, web, email, retrieval and tool output as untrusted input.
- Critical and high-risk checks are release blockers by default.
- Preserve reports as evidence, but redact prompts and payloads that contain personal or confidential data.

