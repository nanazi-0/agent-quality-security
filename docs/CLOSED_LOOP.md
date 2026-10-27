# Complete closed loop

```text
requirements and risk model
          ↓
versioned golden cases
          ↓
software + agent/RAG + security + performance + outcome checks
          ↓
immutable logs, evidence paths and SHA-256 hashes
          ↓
automated gate: PASS / FAIL
          ↓
release decision: blocked / eligible / human-approved
          ↓
rollout, monitoring and rollback plan
          ↓
failed checks and cases enter feedback-queue.jsonl
          ↓
human triage -> corrected regression case -> next run
```

## Commands

```powershell
.\.venv\Scripts\python.exe qualityctl.py platform-coverage
.\.venv\Scripts\python.exe qualityctl.py pipeline
.\.venv\Scripts\python.exe qualityctl.py release-decide --run-id latest
.\.venv\Scripts\python.exe qualityctl.py release-decide --run-id latest --approve --actor "reviewer-name" --reason "reviewed evidence"
.\.venv\Scripts\python.exe qualityctl.py audit-verify
.\.venv\Scripts\python.exe qualityctl.py failure-list
.\.venv\Scripts\python.exe qualityctl.py failure-resolve <failure-id> --actor "reviewer" --resolution "fixed" --regression-case cases/regression.json
.\.venv\Scripts\python.exe qualityctl.py external-ingest examples/external-platform-result.json
```

`eligible` means automated checks passed. It is deliberately different from `approved`: high-impact releases require an identified human to review the evidence and accept a rollback plan.

## What “all platforms covered” means

All platforms named in the knowledge document are registered in `integrations/platforms.json`. They are classified as:

- `implemented`: native project capability;
- `configured`: executable configuration is present, but the external tool may still need installation;
- `adapter-ready`: its CLI/API results can enter the command gate and evidence model;
- `catalog-only`: an alternative, not part of the selected stack;
- `commercial-external`: requires an external account, contract and credentials.

Alternative products are not simultaneously required. A valid production profile selects at least one real executor for every mandatory capability and marks it `required=true`.

External SaaS and cloud platforms export their result into the envelope defined by `schemas/external-result.schema.json`; `external-ingest` binds that evidence to the same run ledger and audit chain. This does not claim an account or connector exists before credentials are provided.
