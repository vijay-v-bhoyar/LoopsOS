# LoopOS Enterprise UI

Enterprise-oriented portal for exploring the LoopOS 108-loop system, mapping AI/GenAI/agentic AI use cases to loop bundles, validating readiness, exporting deterministic action plans, and running governed workflows through the LoopOS authority service.

## Commands

```powershell
npm install
npm run test
npm run test:e2e
npm run lint:design
npm run build
npm run dev -- --host 127.0.0.1 --port 5173
```

Run the execution authority in a second terminal:

```powershell
$env:PYTHONPATH="../authority"
python -m uvicorn loopos_authority.api:app --app-dir ../authority --host 127.0.0.1 --port 8787
```

`pretest` and `prebuild` regenerate `src/data/loopos-data.json` from the LoopOS corpus with:

```powershell
python ../scripts/export_ui_data.py --out ui/src/data/loopos-data.json
```

## Product Boundaries

- Default `evaluation` mode may use the local governed execution authority, but development identity remains non-enterprise.
- Local role selection is explicitly a simulation and defaults to Operator.
- Browser-local persistence is bounded, validated, exportable, and deletable, but it is not authoritative.
- `enterprise` mode fails closed unless identity, persistence, audit, transport, retention, support, and outbound bindings are declared and runtime-verified.
- Optional LLM-assisted questioning through `VITE_LOOPOS_LLM_ENDPOINT`; deterministic fallback is always available.
- Optional structured-field enhancement through `VITE_LOOPOS_LLM_ENDPOINT`; it never selects loops or applies fields automatically.
- Optional enterprise voice fallback through `VITE_LOOPOS_TRANSCRIPTION_ENDPOINT`; audio is sent only after explicit consent.
- Workspace overlays for owners, evidence, approvals, and execution records do not mutate the source LoopOS corpus.
- Recommendations are deterministic and evidence-backed.
- Optional endpoint calls enforce HTTPS, host policy, timeout, redirect refusal, and response-size limits.
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
