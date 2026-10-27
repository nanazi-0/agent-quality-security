# Project collaboration rules

- Treat `reports/` and `.runtime/` as generated runtime data.
- Never commit credentials, production payloads, personal data, or raw secrets.
- Business outcome assertions must read an authoritative state source; an agent's final text is not proof of completion.
- High and critical risk cases fail closed.
- Keep tool integrations optional and preserve the standard-library core.
- Run `./scripts/test.ps1` after changing schemas, gates, assertions, or runners.

