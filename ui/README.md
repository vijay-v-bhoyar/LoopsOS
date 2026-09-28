# LoopOS Enterprise UI

Enterprise-oriented portal for exploring the LoopOS 108-loop system, mapping AI/GenAI/agentic AI use cases to loop bundles, validating readiness, exporting deterministic action plans, and running governed workflows through the LoopOS authority service.

## Commands

The supported UI build runtime is Node.js 24.x, matching the linked Vercel project and CI.

```powershell
npm install
node scripts/run-python.mjs -m pip install --requirement ../authority/requirements.txt
npm run test
# For the full evaluation browser suite, first set the fixture flags below.
npm run test:e2e
npm run lint:design
npm run build
npm run dev -- --host 127.0.0.1 --port 5173
```

The full evaluation suite includes signed synthetic LLM responses and a negative connector allowlist case. In PowerShell, set `$env:LOOPOS_E2E_LLM_ATTESTATION_FIXTURE='1'` and `$env:LOOPOS_E2E_EFFECT_BUDGET_FIXTURE='1'` before `npm run test:e2e`; the runner fixes the deployment mode to `evaluation`. CI sets these only for its browser step. Each run gets a new SQLite database, manifest, and Playwright artifact directory under `output/loopsos-e2e`; pre-existing API or Vite servers are never reused, and direct Playwright invocation without the runner manifest fails closed. The runner passes a strict child environment allowlist, disables Vite `.env` loading, and configures the local authority connector policy to deny external hosts. The effect fixture permits budget admission for deliberately unallowlisted `unknown.example.com` test routes; it does not add that host to the allowlist. The enterprise gate has its own fixed enterprise profile and never receives evaluation fixtures.

Run the local execution authority in a second terminal:

```powershell
npm run dev:authority
```

The local launcher keeps the authority on `127.0.0.1`, uses `deny_all` connector egress, enables development sessions, and stores its SQLite database under `output/loopsos-local/`. This is for local evaluation only; enterprise mode still requires the hosted identity, durable storage, broker, audit, retention, restore, and operational bindings described below.

The launcher selects Python 3.12+ portably (`py -3` on Windows, then `python3`/`python`, conventional Windows installs, and a workspace `.venv` fallback) and rejects an interpreter missing a requested `-m` module. Set `LOOPOS_PYTHON` to an exact interpreter path when the environment requires a pinned runtime.

`pretest` and `prebuild` regenerate `src/data/loopos-data.json` from the LoopOS corpus with:

```powershell
node scripts/run-python.mjs ../scripts/export_ui_data.py --out ui/src/data/loopos-data.json
```

## Product Boundaries

- Default `evaluation` mode may use the local governed execution authority, but development identity remains non-enterprise.
- Local role selection is explicitly a simulation and defaults to Operator.
- Browser-local persistence is bounded, validated, exportable, and deletable, but it is not authoritative.
- `enterprise` mode fails closed unless identity, persistence, audit, credential injection, transport, retention, support, and outbound bindings are declared and runtime-verified. Set `VITE_LOOPOS_CREDENTIAL_INJECTION_MODE=broker`; the authority must return positive broker verification before the UI can start an enterprise session.
- Optional LLM-assisted questioning through `VITE_LOOPOS_LLM_ENDPOINT`; deterministic fallback is always available.
- Optional structured-field enhancement through `VITE_LOOPOS_LLM_ENDPOINT`; it never selects loops or applies fields automatically.
- Optional enterprise voice fallback through `VITE_LOOPOS_TRANSCRIPTION_ENDPOINT`; audio is sent only after explicit consent.
- Workspace overlays for owners, evidence, approvals, and execution records do not mutate the source LoopOS corpus.
- Recommendations are deterministic and evidence-backed.
- Optional endpoint calls enforce HTTPS, exact host policy, timeout, redirect refusal, and bounded request/response sizes. JSON prompts default to a 256 KB request cap; enterprise multipart voice transcription is bounded at 10 MB. Production still requires a durable server-side tenant budget and rate limiter.
- Governed runs are durable in the authority database, enforce state transitions and payload-bound approvals, execute registered tool contracts, collect evidence, run validation/effectiveness probes, compensate failures, and stream audit events.

## Multimodal Intake

- Describe a use case in freeform text, attach PDF/DOCX/TXT/Markdown documents, or dictate it.
- PDF and DOCX extraction run in a terminable browser worker; TXT and Markdown use the browser text reader.
- Up to five documents are accepted, with a 10 MB per-file limit, 50,000 retained characters per source, and 200,000 per workspace.
- OCR and encrypted-PDF unlocking are not included.
- Raw files, audio, object URLs, interim transcripts, and rejected proposals are never persisted.
- Accepted text and provenance metadata are retained only after field-by-field review and explicit application.
- Browser speech recognition may use the browser vendor's configured speech service. The UI discloses this before recording.

## Deployment And Operations

- [Enterprise activation contract](ENTERPRISE-DEPLOYMENT.md)
- [Security model](SECURITY.md)
- [Operations runbook](OPERATIONS.md)
- [Trust UX register](TRUST-UX.md)

The supplied Compose package runs the UI and single-instance authority service as non-root containers. Enterprise rollout must replace development sessions, protect the database with encrypted persistent storage and backup, externally anchor the audit chain, and integrate the organization IdP/BFF, SIEM, retention, and connector credentials.

## Primary Screens

- Dashboard.
- Saved Workspace Console.
- Loop Explorer.
- Use Case Advisor.
- Use Case Library.
- Validation Studio.
- AI, GenAI, and Agentic Readiness Workbench.
- Implementation Plan export.
