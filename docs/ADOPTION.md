# Connect a real agent

1. Copy `cases/demo-suite.json` to `cases/your-suite.json`.
2. Set `TARGET_BASE_URL` to the test deployment.
3. Replace `/agent`, `/reset` and `/state/...` with real test-environment endpoints.
4. Express deterministic response and authoritative business-state assertions.
5. Copy `configs/full-gates.example.toml` to `quality-gates.toml`.
6. Enable each external check only after its tool and configuration work locally.
7. Run `python qualityctl.py pipeline` and keep the generated report as release evidence.

## Existing Portfolio projects

- `agent-memory-governance`: add `memoryctl doctor`, memory evaluation and secret checks as required command gates.
- `cobra-flow-rgzn-dev`: call the business middleware or Gateway test endpoint, then verify DM/IoTDB or business database state through an authoritative read API.

Do not point destructive cases at production. Create resettable fixtures, test tenants and reversible test data first.

