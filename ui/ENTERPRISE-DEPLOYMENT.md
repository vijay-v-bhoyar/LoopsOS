# LoopOS Enterprise Deployment Gate

LoopOS has two explicit postures: `evaluation` and `enterprise`. Evaluation mode is browser-local and must not be used as an authority plane. Enterprise mode fails closed until every required binding is configured and runtime-verified.

## Required Bindings

| Binding | Required contract | Activation proof |
| --- | --- | --- |
| Identity | BFF-managed session; IdP groups mapped server-side to LoopOS roles | Session endpoint verifies issuer, audience, signature, expiry, tenant, subject, and one explicit role mapping |
| Persistence | LoopOS authority service and tenant-scoped durable Postgres database | Authority readiness reports Postgres and the authenticated workspace list succeeds; enterprise mode never uses browser workspace storage |
| Durable worker | Database-leased execution jobs and a protected worker/cron dispatch route | Authority readiness reports a fresh durable heartbeat from the configured internal or external dispatch mode |
| Audit | Authority hash chain delivered through the durable outbox to an external append-only sink | Authority readiness reports a configured sink, at least one accepted signed envelope, and zero undelivered anchors |
| Transport | HTTPS for every non-local origin | Certificate, reachability, redirect, and hostname checks pass |
| Retention | Approved retention and deletion policy URL | Legal/security owners approve the policy and deletion evidence path |
| Operations | Named support contact and on-call route | Alert routing and incident exercise pass |
| Outbound policy | Exact host allowlist for AI/transcription endpoints | Egress policy and endpoint data-processing terms are approved |
| Backup and restore | Credential-free HTTPS reference, SHA-256, and timestamp for a recent restore exercise | Authority binds readiness to the immutable digest; the handover verifier independently validates the exact evidence bytes |

The required `VITE_` values are documented in `.env.example`. They are public build configuration, never secrets. Tokens and service credentials belong only in the BFF or service runtime.

## Production Build

```bash
docker compose build
docker compose up -d
```

Terminate TLS at the enterprise ingress, keep the supplied security headers, and narrow `connect-src` in `nginx.conf` to approved origins. Set `VITE_LOOPOS_AUTHORITY_URL` to the exact HTTPS authority origin or to `/api` behind a same-origin ingress. Enterprise mode probes `/health/ready`, exchanges the managed identity session, and loads the tenant workspace register before it can transition to `enterprise_ready`.

## Release Gate

1. Pin the image by digest and attach SBOM, vulnerability scan, and provenance from the enterprise build service. CI retains attested OCI archives, a digest manifest, HIGH/CRITICAL vulnerability reports, and a hardened two-container runtime smoke report in the `loopos-release-evidence-<commit>` artifact for 30 days.
2. Run unit, design-token, build, Playwright, corpus-validation, and practicality-audit gates.
3. Test tenant isolation, session expiry, CSRF, audit append/retrieve, retention deletion, and restore in staging.
4. Confirm CSP and egress allowlists contain only approved service origins.
5. Record security, privacy, legal, product, and operations approval references.
6. Canary to an internal cohort; promote only when errors, latency, persistence, and audit delivery meet the runbook thresholds.

## Live Handover Proof

Run the verifier from a controlled release workstation after staging or production bindings are provisioned. The two assertions must resolve to different expected tenants, and the primary identity must have Executive authority so it can create and delete the marker and inspect audit proof. The verifier creates a uniquely named marker, proves the secondary tenant receives `404`, deletes the marker, proves the primary tenant also receives `404`, verifies the complete tenant audit chain and exact `WORKSPACE_DELETED` event, invokes protected worker dispatch, and then validates the complete readiness payload. Assertions, worker tokens, and application session tokens are never included in the JSON report.

```powershell
$env:LOOPOS_HANDOVER_BASE_URL="https://loopos.example.com/api"
$env:LOOPOS_HANDOVER_PRIMARY_IDENTITY_ASSERTION="<short-lived-primary-assertion>"
$env:LOOPOS_HANDOVER_SECONDARY_IDENTITY_ASSERTION="<short-lived-secondary-assertion>"
$env:LOOPOS_HANDOVER_WORKER_TOKEN="<server-side-worker-token>"
$env:LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE="<path-to-reviewed-postgres-restore.json>"
$env:LOOPOS_HANDOVER_EXPECTED_PRIMARY_TENANT="<primary-tenant-id>"
$env:LOOPOS_HANDOVER_EXPECTED_SECONDARY_TENANT="<secondary-tenant-id>"
python scripts/verify_production_handover.py --output output/production-handover-report.json
```

`GO` requires every check to pass. The restore evidence file must be the exact JSON whose SHA-256 and `generated_at` are configured as `LOOPOS_BACKUP_RESTORE_EVIDENCE_SHA256` and `LOOPOS_BACKUP_RESTORE_VERIFIED_AT`. Any missing credential, modified evidence byte, insecure target, failed cleanup, cross-tenant visibility, stale worker heartbeat, audit backlog, development authentication, non-Postgres storage, or incomplete operational binding produces `NO_GO` and a nonzero exit code. If the verifier is interrupted, search the primary tenant for the `handover-probe-` prefix and delete any residual marker before repeating the gate.

## Current Boundary

This repository supplies the portal, deterministic recommendation engine, governed execution authority, tenant-scoped SQLite/Postgres store contract, authoritative workspace revisions, database-leased execution jobs, protected worker/cron dispatch, tool/probe runtime, audit chain with a durable external-anchor outbox, and hardened containers. It does not supply the organization IdP/BFF, a provisioned managed Postgres instance, the independently administered WORM/SIEM sink, secrets manager, or organization-specific retention/backup implementation. Production activation remains blocked until those bindings are provisioned and verified.
