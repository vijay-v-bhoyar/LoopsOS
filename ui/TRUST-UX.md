# LoopOS Enterprise UI Trust UX Register

Status: evaluation-safe client and enterprise activation gate registered, with dedicated live browser coverage for every trust surface listed below. Authoritative backend enforcement is required before production activation.

## 1. Surface Register

| Surface | Promise | Enforcing artifact | Probe |
|---|---|---|---|
| Dashboard validation summary | Shows corpus validation separately from activation readiness | `scripts/validate_loop_corpus.py`, `scripts/audit_loop_practicality.py`, `src/screens/Dashboard.tsx` | `e2e/dashboard-validation-summary.spec.ts`, `npm run test` dashboard count test |
| Deployment posture | Shows evaluation, blocked, verification-required, or ready state from explicit bindings; enterprise startup fails closed | `src/lib/deployment.ts`, `src/screens/ReadinessWorkbench.tsx` | `e2e/enterprise-readiness.spec.ts`, deployment posture tests |
| Use Case Advisor recommendations | Explains loop suggestions from recorded metadata, archetypes, playbooks, and risk factors | `src/lib/recommendation.ts`, `src/data/loopos-data.json`, `src/screens/UseCaseAdvisor.tsx` | `e2e/use-case-advisor-recommendations.spec.ts`, matcher tests in `src/lib/recommendation.test.ts` |
| Multimodal intake | Holds typed text, extracted text, and transcripts in review until the user explicitly applies selected fields | `src/features/useCaseIntake/UseCaseIntake.tsx`, `src/features/useCaseIntake/fieldProposal.ts` | `e2e/multimodal-intake.spec.ts`, intake component tests |
| Document extraction | Reads PDF/DOCX/TXT/Markdown locally within declared limits and records warnings or actionable failures | `src/features/useCaseIntake/documentExtraction.ts`, extraction worker | `e2e/document-extraction.spec.ts`, extractor and binary-parser tests |
| Voice capture | Shows browser capability, recording state, transcript, browser-service disclosure, and endpoint consent honestly | `src/features/useCaseIntake/useVoiceCapture.ts` | `e2e/voice-capture.spec.ts`, voice hook tests |
| Structured-field enhancement | Calls the configured enterprise endpoint only after an explicit action and never changes loop selection directly | `src/features/useCaseIntake/fieldProposal.ts`, `src/features/useCaseIntake/UseCaseIntake.tsx` | `e2e/structured-field-enhancement.spec.ts`, intake proposal tests and enhancement fallback tests |
| Saved Workspace Console | Persists bounded local records, reports save failures, exports portable JSON, and confirms deletion | `src/lib/workspaceStore.ts`, `src/lib/workspaceExport.ts`, `src/screens/WorkspaceConsole.tsx` | `e2e/workspace-console.spec.ts`, persistence and export tests |
| Local simulation gate | Enables role-aware evaluation workflow only, defaults to Operator, and is unavailable in blocked enterprise mode | `src/components/AuthGate.tsx`, `canApprove` in `src/lib/workspaceStore.ts` | `e2e/local-simulation-gate.spec.ts`, auth gate and approval tests |
| LLM-assisted questioning | Uses a configured endpoint when available and deterministic questions otherwise | `src/lib/questionAssistant.ts`, `src/screens/WorkspaceConsole.tsx` | `e2e/llm-assisted-questioning.spec.ts`, question assistant tests |
| Optional service boundary | Rejects insecure/unapproved origins, redirects, timeouts, and oversized responses | `src/lib/secureRequest.ts` | `e2e/optional-service-boundary.spec.ts`, secure request tests |
| Client failure boundary | Suppresses internal error detail, records an incident reference, and never records a false result | `src/components/AppErrorBoundary.tsx` | `e2e/client-failure-boundary.spec.ts`, error-boundary test |
| Governed execution authority | Creates durable runs, displays exact payload approval, verified output, recovery/compensation, an Executive-controlled tenant stop, and streamed append-only events without local fallback | `authority/loopos_authority/`, `src/features/governedExecution/` | authority unit/API tests and governed Playwright journeys |
| Release Assurance Workspace | Shows release gates, Jira/GitHub/manual evidence references, exceptions, connector posture, and ROI basis from deterministic records; it does not claim live connector authority | `src/lib/releaseAssurance.ts`, `authority/loopos_authority/store.py` connector event and release initiative records | `e2e/release-assurance.spec.ts`, release assurance unit tests, authority API tests |
| Validation Studio | Does not promote use-case readiness beyond available inputs | `src/lib/validation.ts` | `e2e/validation-studio.spec.ts`, validation tests |
| Action Plan export | Produces markdown and saves the latest plan into the active workspace | `src/lib/actionPlan.ts`, `savePlan` in `src/lib/workspaceStore.ts` | `e2e/action-plan.spec.ts`, advisor and workspace tests |
| Contextual help | Explains risk, readiness, evidence, why, and export concepts without hiding critical instructions | `src/components/Help.tsx` | `e2e/contextual-help.spec.ts`, keyboard/focus checks and app tests |

## 2. Why Display

The "Why this loop" area renders `MatchFactor` records produced by the deterministic matcher. Source-backed factors include the retained source identifier and excerpt. It does not invent confidence scores or create a post-hoc rationale.

## 3. Reversibility And Mutability

Evaluation mode adds local workspace overlays only. Owner/evidence edits, approvals, question suggestions, execution records, and accepted source text are saved in browser storage and do not modify the generated LoopOS corpus. Every workspace can be exported or permanently deleted through an explicit confirmation.

Raw files, microphone audio, object URLs, interim transcripts, and rejected proposals remain transient. Removing a retained source removes it from future matching but does not silently reverse fields the user previously approved.

## 4. Authority Boundaries

- The evaluation gate is not enterprise SSO and selected roles are simulations.
- Local approval drafts are planning notes and never authorize an authority run.
- Governed authority approvals and rejections bind an authorized actor to the exact executable payload hash; approvals expire, can be renewed without erasing history, and are consumed once.
- `record_action` creates a real durable authority artifact; `http_json_action` invokes an allowlisted enterprise endpoint with server-side credentials and a compensation contract.
- External HTTP actions cannot be relabeled as local by a client; the tool type enforces external-effect approval policy.
- Failed validation and compensation paths retain their partial outputs and evidence hashes for investigation.
- The tenant kill switch is server-authoritative, durable, Executive-only, and audited. It blocks new and queued work before dispatch and interrupts in-flight authority processing; an external request may already have completed, and this service does not falsely claim remote cancellation or credential revocation. Deactivation does not resume a blocked run; restart requires a new run and normal approval.
- Optional LLM questioning is assistive. Recommendation logic remains deterministic and evidence-backed.
- Release assurance records are durable initiative evidence, not deployment permission. Jira/GitHub write-back requires a governed external action with server-side connector credentials, payload-bound approval, and a compensation or correction path when applicable.
- Connector evidence events are source payload records with hashes, tenant isolation, and an explicit verification status. `verified_webhook` means the raw request body matched the configured HMAC secret at ingestion time and the delivery ID is bound to that payload so altered replays are refused. It is still not proof that the upstream Jira/GitHub object remains unchanged after observation; freshness and backfill policy must be configured before production reliance.
- Durable release initiative records render the authority-returned `freshness_summary`; the client does not calculate release freshness itself. The current authority policy marks linked connector evidence fresh only when all linked events have valid observation timestamps within 24 hours of record creation, otherwise the record shows missing or stale evidence. Freshness is not provider verification: session-authenticated snapshots remain review evidence.
- Durable release initiative records render the authority-returned `readiness_verdict`; the client does not decide release readiness. `GO`, `NO_GO`, and `REVIEW_REQUIRED` are deterministic over recorded freshness, provider verification, and release gate status, and do not execute a production deployment without a separate governed action.
- Authority proof packs are downloaded from `GET /v1/release-initiatives/{initiative_id}/proof-pack`; the client does not reconstruct the durable authority proof pack locally. The returned Markdown is an evidence packet with a server hash, not an approval or deployment command. Proof-pack generation appends a server-side `PROOF_PACK_GENERATED` audit event containing the Markdown hash and source event IDs. Retrieval time is response metadata, not part of the hashed Markdown, so repeated downloads of an unchanged durable release record preserve the same proof-pack hash.
- Optional AI field structuring is assistive, visibly labeled, schema-validated, and review-gated.
- Browser speech recognition may use a browser-managed speech service; the UI does not claim local-only recognition.
- Enterprise transcription requires an explicit consent action and configured endpoint. No endpoint means no fallback upload.
- Client-side limits and consent are product boundaries, not server-side enterprise enforcement.
- Missing owners, evidence, metrics, probes, and handoffs must remain visible as gaps.
- The label `Enterprise ready` is available only after declared bindings and runtime proofs pass; build configuration alone is insufficient.

## 5. Known Residual Gaps

- The authority enforces tenant-scoped access and a durable hash-chained audit trail. Auditor and Executive roles can verify that chain in the UI; external WORM/SIEM anchoring remains an enterprise deployment responsibility.
- Connector credential revocation during a kill-switch event is not implemented by this service and remains an organization-owned connector or secret-manager control.
- No write-back to enterprise GRC, ticketing, evidence, or identity systems.
- Jira/GitHub connector rows are shadow/export posture until enterprise connector credentials, webhook signature verification, backfill, rate-limit handling, freshness policy, and governed write scopes are configured server-side.
- Clipboard and download behavior depends on browser permissions.
- Full screen-reader manual pass is still recommended before enterprise rollout.
- Browser speech availability and recognition quality vary by managed browser policy and platform.
- Image-only PDFs require an external OCR workflow before LoopOS can analyze them.
- Enterprise activation still requires an IdP/BFF, encrypted managed persistence for horizontal scale, external audit anchoring, approved retention implementation, SIEM routing, and accountable operators.

## 6. Verification Evidence

- `python scripts\validate_loop_corpus.py`
- `python scripts\audit_loop_practicality.py`
- `npm run test`
- `npm run test:e2e`
  Includes dedicated trust-surface browser journeys for dashboard validation summary, deployment posture, advisor recommendations, multimodal intake, document extraction, structured-field enhancement, workspace console, local simulation gate, LLM-assisted questioning, optional service boundary, client failure boundary, governed execution, release assurance, validation studio, action plan export, contextual help, and voice capture.
- `npm run lint:design`
- `npm run build`
- `npm audit --audit-level=high`
- `$env:PYTHONPATH="authority"; python -m unittest discover -s authority\tests -v`
