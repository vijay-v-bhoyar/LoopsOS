# LoopOS Production Handover Unblock Plan

Status: NO_GO until the external authority, identity, durability, evidence, pilot, and approval gates are proven.
Last refreshed: 2026-09-05

This plan follows the repository build loop: graph trace, smallest safe change, live or boundary test, fix, retest, and proof classification. Local tests and a Vercel preview are not substitutes for production identity, tenant isolation, durable storage, or human approval.

## Decision

The repository is structurally ready for controlled evaluation, but it is not ready for a real user handling a real production case. The current preview is a Vercel `READY` deployment, while its `/api/health/ready` and `/api/v1/workspaces` probes return `{"detail":"Authority configuration is invalid."}`. Anonymous access is protected by Vercel SSO. Do not promote this preview or enable production use.

## Current Proof Boundary

The following product paths are now unblocked and locally proven for controlled evaluation:

- Governed execution preserves the approval, exact-payload, evidence, probe, effectiveness, rollback, audit, and tenant-isolation contracts.
- The tenant kill switch is server-authoritative, durable, Executive-only, audited, visible in the UI, and enforced before dispatch, during engine phases, during effectiveness scheduling, and during restart reconciliation.
- Kill-switch interruption reports the real boundary: a remote request may already have completed, while this service does not claim remote cancellation or credential revocation.
- The shipped UI builds, passes unit and browser regressions on desktop/mobile, and refuses enterprise session bootstrap when readiness or bindings are not proven.
- The corpus, generated code graph, routing contract, security-header contract, and dependency audit are green.

The following release decisions remain blocked and cannot be inferred from the local proofs:

- Production identity, tenant assertions, durable Postgres, worker dispatch, external audit anchoring, retention/support controls, restore evidence, operational evidence, pilot ownership, and required human approvals.
- Platform/global break-glass orchestration and connector-side cancellation or credential revocation; the implemented control is intentionally tenant-scoped and fail-closed at this authority boundary.
- Real-user production handover until the deployed `/api` authority returns a proven ready state and the two-tenant authenticated verifier returns `GO`.

## Proven Baseline

- Graphify refresh: 3,176 nodes, 6,636 edges, and 245 communities; the final multigraph diagnostic is recorded in `output/graphify-final-diagnose.json`.
- UI unit tests: 23 files and 201 tests passed, including the persistence-readiness boundary regression.
- Live local smoke: evaluation entry, advisor navigation, bounded example loading, 24 deterministic recommendations, governance-review readiness, and corpus `PASS` were visible after the final UI source fix.
- Full authority suite: 257 tests passed and 1 intentional live-Postgres skip.
- Fresh authority-suite rerun passed with the repository package path configured: 260 tests passed and 1 intentional live-Postgres integration test was skipped because `LOOPOS_TEST_POSTGRES_DSN` was not provided.
- Tenant kill-switch slice: 5 direct authority regressions passed for Executive-only activation, queued-work blocking, fail-closed creation, audit integrity, non-resuming deactivation, honest in-flight uncertainty, and restart-safe blocking; production connector credential revocation remains external.
- Fresh governed/release browser regression: the full current matrix passed 94 desktop/mobile tests, including live kill-switch status reads, approval, rejection, audit, proof-pack, tenant-boundary, stalled-stream stop, reconnect, and stale-workspace isolation flows.
- Enterprise browser boundary: 10 desktop/mobile tests passed for fail-closed readiness, binding mismatch, queued-job blocking, and transient authoritative-save retry behavior.
- Browse-surface browser regression: 2 desktop/mobile tests passed for loop filtering, explicit empty states, loop detail selection, and use-case handoff navigation.
- Real browser document-worker regression: valid PDF and DOCX fixtures passed through the bundled PDF.js and Mammoth workers on desktop/mobile; focused tests passed in both Vite dev and built dist-preview modes.
- Enterprise transcription browser regression: multipart recording, response validation, microphone-track disposal, transcript review/apply, malformed-response fail-closed behavior, short-transcript draft fallback, reset cancellation, synchronous browser-start failure handling, synchronous recorder-start failure handling, and synchronous stop-failure handling passed on desktop/mobile.
- Dedicated enterprise readiness gate: 10 desktop/mobile cases passed with unavailable readiness, binding mismatch, extra endpoint-host mismatch, queued-job fail-closed, and transient authoritative-save retry scenarios; the E2E harness now accepts `LOOPOS_E2E_AUTHORITY_PORT` so an unrelated local service cannot invalidate the gate before assertions run.
- Cross-plane endpoint policy matching now requires the normalized authority and compiled UI host sets to be equal in both directions; authority-only or UI-only hosts fail closed before enterprise session bootstrap.
- Full local browser matrix: 94 tests passed across desktop/mobile, with 10 deliberate enterprise-gate skips that require an enterprise-configured Vite build; the clean rerun is recorded in `output/playwright-full-after-lifecycle-hardening-final.log`.
- Lifecycle hardening regressions now cover response-body deadlines for optional AI and authority JSON, authoritative-save retry, governed reconnect, local stop-following for stalled SSE, stale workspace switch isolation, and sign-out cancellation of pending enterprise bootstrap.
- Enterprise persistence evidence now separates infrastructure readiness from authenticated proof: the UI marks persistence verified only after a successful tenant-scoped workspace list, and preserves a fail-closed state for list failures and cross-tenant records.
- Tool invocation audit events now persist measured latency and retry count for success and failure paths; state-transition events include durable loop/version, execution, correlation, risk, authority, evidence, standard, policy/sandbox references, and explicit unverified proof state where external proof is unavailable.
- Authority request-rate protection now uses atomic durable fixed-window counters, explicit `LOOPOS_RATE_LIMIT_REQUESTS` and `LOOPOS_RATE_LIMIT_WINDOW_SECONDS` production configuration, `429` responses with `Retry-After`, and Postgres RLS/privilege parity; production startup/readiness remains fail-closed when the policy is absent or malformed.
- Rate-limit readiness is now part of the authority JSON contract and the UI deployment posture; the client rejects a ready response that omits the proof and renders request rate limiting as a separate enterprise activation binding.
- If the limiter store cannot be read or updated, the middleware rejects the request with a sanitized `503` and logs the infrastructure failure instead of admitting traffic without protection.
- The production handover verifier now requires `rate_limit_configured=true` in `/health/ready`, so a deployment cannot receive a handover `GO` without explicit request-protection proof.
- The production handover verifier now creates a bounded R1 run through the public API and requires the protected external worker drain to complete it with `EFFECTIVENESS_PROVEN` and `runner_status=completed`; a dispatch heartbeat alone is insufficient.
- Corpus validation: 160 checks passed.
- Local pilot probe runner: 5 registered adapters and 9 bounded fixture cases passed with zero external calls; this is local contract proof only, not live organizational evidence.
- Pilot activation candidate report: `NO_GO`; registry uniqueness, bounded scope, fixture binding, and executable adapter checks pass, while loop status, named owners, authoritative evidence, metric targets, and approved real golden-fixture checks remain fail-closed.
- Practicality audit: 279 files / 232,472 lines; 0 blockers, 1,603 action-required findings, and 715 warnings.
- Local and hosted Vite builds passed; the large JavaScript chunk warning remains a performance follow-up, not a handover approval.
- UI dependency audit: `npm audit --audit-level=high` reports 0 vulnerabilities after updating the transitive `@xmldom/xmldom` and `browserslist` advisories.
- Security-header contract passes. Vercel and Nginx use same-origin `connect-src` by default and reject scheme-wide browser egress.
- Vercel upload context explicitly excludes `.env*` files; the production preflight now enforces this boundary.
- Latest preview `dpl_59eWcMUx8HxdXdqFEtRLpr8PT3ys` is `READY` at [the Vercel preview](https://loopos-enterprise-30jkv18dl-vijayvbhoyar-8312s-projects.vercel.app). Protected Vercel CLI probes returned `{"status":"live"}` from `/api/health/live`; `/api/health/ready` and `/api/v1/workspaces` returned `{"detail":"Authority configuration is invalid."}`. The remote build reported 0 vulnerabilities. Direct browser access is protected by Vercel SSO. This is preview reachability and fail-closed behavior, not production authority proof.
- An enterprise-configured preview with only public test bindings was rejected by the build-time gate with structured `settings_loaded` `NO_GO`; the preflight no longer crashes on a missing runtime Python package.
- The linked Vercel project currently reports no configured environment variables, so production identity, durable storage, worker, audit, and operational bindings are not present.
- Local authority now exposes `GET /v1/controls/kill-switch`, Executive-only activation and deactivation, durable tenant control state, worker/engine/scheduler/restart enforcement, and an honest uncertainty record; this does not provision platform-global orchestration, remote connector cancellation, or credential revocation.

Evidence files:

- `output/production-configuration.json`
- `output/production-handover-report.json`
- `output/pilot-activation-report.json`
- `output/pilot-activation-candidate-trace.json`
- `output/playwright-full.log`
- `output/playwright-full-after-lifecycle-hardening-final.log`
- `output/playwright-full-after-pdf-worker.log`
- `output/playwright-full-after-voice-fallback.log`
- `output/voice-enterprise-live-final.log`
- `output/field-proposal-fallback-unit-retest.log`
- `output/voice-reset-live-retest.log`
- `output/voice-reset-unit-retest.log`
- `output/voice-start-failure-live-retest.log`
- `output/voice-start-failure-unit-retest.log`
- `output/ui-unit-after-voice-fallback.log`
- `output/ui-build-after-voice-fallback.log`
- `output/ui-unit-after-voice-reset.log`
- `output/ui-build-after-voice-reset.log`
- `output/playwright-full-after-voice-reset.log`
- `output/ui-unit-after-voice-start-guard.log`
- `output/ui-build-after-voice-start-guard.log`
- `output/playwright-full-after-voice-start-guard.log`
- `output/enterprise-gate-after-voice-start-guard-alt-port.log`
- `output/deployment-host-set-unit-retest.log`
- `output/enterprise-config-host-set-live-first.log`
- `output/enterprise-config-host-set-live-retest.log`
- `output/ui-unit-after-config-host-set.log`
- `output/ui-build-after-config-host-set.log`
- `output/playwright-full-after-config-host-set-alt-port.log`
- `output/voice-recorder-start-failure-live-first.log`
- `output/voice-recorder-start-failure-live-first2.log`
- `output/voice-recorder-start-failure-live-retest.log`
- `output/voice-recorder-start-failure-unit-retest.log`
- `output/ui-unit-after-recorder-start-guard.log`
- `output/ui-build-after-recorder-start-guard.log`
- `output/playwright-full-after-recorder-start-guard.log`
- `output/voice-stop-failure-live-first.log`
- `output/voice-stop-failure-live-retest.log`
- `output/voice-stop-failure-unit-retest.log`
- `output/ui-unit-after-stop-guard.log`
- `output/ui-build-after-stop-guard.log`
- `output/playwright-full-after-stop-guard.log`
- `output/vercel-preview-recorder-start-guard-final.log`
- `output/vercel-preview-recorder-start-guard-final-probes.log`
- `output/vercel-preview-stop-guard-final.log`
- `output/vercel-preview-stop-guard-final-probes.log`
- `output/vercel-preview-config-host-set-final.log`
- `output/vercel-preview-config-host-set-final-probes.log`
- `output/vercel-preview-voice-fallback.log`
- `output/vercel-preview-voice-fallback-probes.log`
- `output/vercel-preview-voice-start-guard.log`
- `output/vercel-preview-voice-start-guard-probes.log`
- `output/vercel-preview-final.log`
- `output/vercel-preview-final-probes.log`
- `output/vercel-env-current.log`
- `output/document-extraction-dist.log`
- `output/graphify-final-diagnose.json`
- `output/design-lint-final.log`
- `output/corpus-validation-final.log`
- `graphify-out/GRAPH_REPORT.md`

## Workstream 1: Select One Pilot

The highest-ranked bounded candidate is `pilot-sdlc-governance-os`: one product, one release train, and one evidence store across 11 loops. This is a recommendation, not an automatic selection. A product owner must choose the real pilot before `LOOPOS_ACTIVE_PLAYBOOK_ID` is set.

Candidate loop IDs:

- `loop-006-requirements-quality-loop`
- `loop-007-requirements-change-control-loop`
- `loop-008-requirements-traceability-loop`
- `loop-014-retrospective-improvement-loop`
- `loop-015-design-review-loop`
- `loop-016-architecture-fitness-and-future-compatibility-loop`
- `loop-022-code-quality-loop`
- `loop-023-pull-request-review-loop`
- `loop-025-ci-pipeline-loop`
- `loop-036-release-readiness-loop`
- `loop-038-deployment-validation-loop`

For every selected loop, the named owners must:

1. Set the descriptor status to `PILOT` only after the pilot boundary is approved.
2. Bind policy, gate, risk, executor, validator, and backup owners in `owners/OWNER_REGISTRY.yaml`.
3. Bind a credential-free HTTPS authoritative location, freshness policy, and retention policy in `evidence/EVIDENCE_LOCATION_REGISTRY.yaml`.
4. Set a finite metric target and observation window in `runtime/metric_packs.yaml`.
5. Keep the existing fixture and executable probe references intact.
6. Run `python scripts/verify_pilot_activation.py --playbook-id pilot-sdlc-governance-os --output output/pilot-activation-candidate-trace.json`.
7. Set `LOOPOS_ACTIVE_PLAYBOOK_ID` in the controlled runtime only after the candidate trace passes, then run `python scripts/verify_pilot_activation.py --output output/pilot-activation-report.json`.
8. Run `python scripts/run_pilot_probes.py --output output/pilot-probe-local-contract.json` and retain the result as local contract evidence; do not substitute it for external CI, observability, security, or model-evaluation proof.
9. Replace the bounded fixture only with an organization-approved JSON/YAML fixture declaring `fixture_kind: approved_golden_fixture` and a non-placeholder `approval_ref`; the verifier will reject bounded fixtures, missing metadata, unsafe paths, malformed adapter envelopes, and any nonzero external-call count.

Do not activate the complete 108-loop corpus as one change. Do not replace missing organization values with names, URLs, targets, or dates invented by automation.

## Workstream 2: Provision Authority Runtime

An infrastructure and security owner must provision these values through the approved secret/configuration manager. Secrets must not be committed or placed in `VITE_` variables.

- `LOOPOS_ALLOW_DEV_AUTH=false` and an explicit `LOOPOS_SESSION_HMAC_SECRET` of at least 32 bytes.
- `LOOPOS_STORAGE_BACKEND=postgres` and a TLS-protected `LOOPOS_POSTGRES_DSN` using `sslmode=require`, `verify-ca`, or `verify-full`.
- `LOOPOS_OIDC_ISSUER`, `LOOPOS_OIDC_AUDIENCE`, `LOOPOS_OIDC_JWKS_URL`, tenant and role claim names, and an explicit `LOOPOS_OIDC_ROLE_MAPPING_JSON`.
- Exact `LOOPOS_CORS_ORIGINS` for the approved UI origins, or empty only when the authority and UI are genuinely same-origin.
- `LOOPOS_OUTBOUND_POLICY_MODE=deny_all` or an exact `LOOPOS_ALLOWED_HTTP_HOSTS` allowlist.
- `LOOPOS_AUDIT_ANCHOR_URL` and `LOOPOS_AUDIT_ANCHOR_HMAC_SECRET` bound to an append-only WORM/SIEM sink.
- `LOOPOS_RETENTION_POLICY_URL`, `LOOPOS_SUPPORT_CONTACT`, and current operational evidence URL, digest, and timestamp.
- `LOOPOS_BACKUP_RESTORE_EVIDENCE_URL`, its lowercase SHA-256 digest, and verified timestamp.
- `LOOPOS_WORKER_TOKEN` or `CRON_SECRET` with at least 32 bytes, plus `LOOPOS_EXECUTION_WORKER_MODE=external` on Vercel.

The provisioned environment must also bind connector and webhook credentials to the allowed host and tenant scope. The checked-in Postgres migration contract already passes; managed connectivity, RLS behavior, tenant isolation, and restore proof do not.

## Workstream 3: Bind the UI

The UI build owner must provide the public, non-secret bindings in the controlled Vercel build environment and make them match the authority values exactly:

- `VITE_LOOPOS_DEPLOYMENT_MODE=enterprise`
- `VITE_LOOPOS_AUTHORITY_URL=/api` for same-origin routing, or an exact HTTPS `/api` URL plus `VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST`
- `VITE_LOOPOS_AUTH_MODE=bff-session`
- `VITE_LOOPOS_PERSISTENCE_MODE=api`
- `VITE_LOOPOS_AUDIT_MODE=server`
- Matching retention, support, outbound, allowed-host, and restore-evidence bindings

The default CSP permits only same-origin connections. If a deployment intentionally calls a direct optional service, add its exact HTTPS origin to both `vercel.json` and `ui/nginx.conf`, then rerun the production preflight and enterprise browser gate. Never change `connect-src` to `https:` or `*`.

## Workstream 4: Produce External Evidence

Operations and security owners must produce fresh, independently addressable evidence. Each URL must be credential-free, globally routable, HTTPS, and controlled by the organization.

- Postgres connectivity and tenant-isolation evidence with two distinct tenant assertions.
- Audit-anchor accepted-envelope evidence and zero undelivered backlog.
- Fresh worker heartbeat from the selected external dispatch mode.
- Exact restore evidence bytes, lowercase SHA-256 digest, and verification timestamp.
- Exact operational evidence bytes for retention, support, outbound policy, and backup/restore controls.
- OCI image digest, SBOM, provenance, vulnerability report, runtime smoke, rollback rehearsal, and retention evidence.

If Docker, the managed database, the identity provider, or the evidence sink is unavailable on the workstation, classify the check as `BLOCKED` or `DEGRADED`; do not convert it to a local pass.

## Workstream 5: Run the Gates in Order

1. Run `python scripts/validate_loop_corpus.py` and resolve any structural failure.
2. Run the UI dependency audit, tests, design-token lint, build, and `npm run test:e2e:enterprise-gate` from `ui`.
3. Run `python scripts/verify_production_environment.py --output output/production-configuration.json`; stop unless the verdict is `READY_FOR_LIVE_VERIFICATION`.
4. Deploy the exact reviewed build to the approved environment and verify HTTPS routing, response security headers, and no stale deployment cache.
5. Run the two-tenant authenticated handover verifier with real assertions supplied only through the controlled workstation environment:
   `python scripts/verify_production_handover.py --base-url <approved-https-authority> --output output/production-handover-report.json`
6. Require `GO` from the handover verifier, including marker isolation, deletion, audit-chain completeness, worker dispatch, readiness, restore bytes, and operational bytes.
7. Attach the release evidence bundle and obtain security, privacy, legal, product, and operations approvals.
8. Canary to the approved internal cohort, observe the defined window, and promote only through the governed release action with rollback evidence.

## Stop Conditions

Stop immediately if development authentication is enabled, Postgres is not durable and TLS-protected, OIDC assertions do not resolve to distinct tenants, audit delivery has backlog, worker heartbeat is stale, evidence bytes do not match their digests, pilot ownership is missing, preview access is not available to the approved test identities, or any required approval is absent.

## Current Unblock Owner Map

- Product owner: select one pilot and approve scope.
- Category owners: populate named owner records and metric targets for the selected loops.
- Security/identity owner: provision OIDC, role mapping, session secret, CORS, and secret manager.
- Platform/database owner: provision managed Postgres, migrations, backups, restore, and scheduler.
- Operations/audit owner: provision the external anchor, retention, support, outbound, and operational evidence.
- UI/deployment owner: bind Vercel variables, resolve preview access, deploy the reviewed build, and retain immutable evidence.
- Release authority: review the evidence packet and issue the governed canary/promotion approval.

The next safe action is to collect these owner-owned values and evidence outside the repository, then rerun the gates above. Until that happens, the fail-closed `NO_GO` result is the correct product behavior.
