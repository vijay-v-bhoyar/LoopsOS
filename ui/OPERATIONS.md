# Operations Runbook

## Service Objectives

Proposed starting targets, subject to enterprise owner approval:

- Portal availability: 99.9% monthly for production tenants.
- Static asset p95 latency: below 500 ms at the enterprise ingress.
- Authority API p95 latency: below 1.5 seconds for interactive reads/writes.
- Authoritative persistence success: at least 99.99%.
- Audit delivery: 99.99% within 60 seconds; missing audit proof blocks approval/execution changes.

## Health And Alerts

- Liveness: `GET /healthz` returns `200 ok`.
- Authority liveness: `GET /api/health/live`; authority readiness: `GET /api/health/ready`.
- Release CI starts the UI and authority images together with read-only filesystems, dropped capabilities, no-new-privileges, and non-root users. The retained `container-runtime-smoke.json` proves both image healthchecks, NGINX-to-authority proxying, readiness semantics, and security headers.
- Production readiness must additionally prove IdP session, tenant-scoped persistence, audit append/retrieve/external anchor, retention configuration, and outbound policy.
- Page on sustained 5xx, session verification failure, persistence write failure, audit delivery failure, cross-tenant probe failure, or CSP violation increase.
- Ticket on elevated client error-boundary incidents, extraction failures, or optional endpoint timeouts.

## Incident Response

1. Stop promotion and preserve image digest, configuration revision, and UTC incident window.
2. If authorization, isolation, audit, or data integrity is uncertain, disable affected write operations and revoke sessions.
3. Roll back to the last verified image digest; do not rebuild an old tag.
4. Verify `/healthz`, CSP, session expiry, tenant isolation, persistence, audit delivery, and a deterministic recommendation smoke test.
5. Reconcile missing or ambiguous records from authoritative event IDs. Never reconstruct approvals from browser state.
6. Record root cause, affected controls, evidence, owner, corrective action, and effectiveness observation window.

Queued or running idempotent runs are re-queued after an authority restart. Runs waiting for approval or an effectiveness observation deadline remain durable and are not restarted as actions. A failed or terminal run is never rewritten; recovery creates a linked successor.

Effectiveness deadlines are enforced by both queue and claim operations. A caller cannot bypass the configured observation window by manually starting a pending run; the scheduler releases it only when the stored deadline is due.

## Backup, Restore, And Deletion

The authoritative service must define encrypted backup cadence, recovery point objective, recovery time objective, restore testing, legal hold, retention, and deletion evidence. Browser-local evaluation records are user-managed and are not backed up; users can export or permanently delete each workspace. Local Supabase/Postgres can be used for beta persistence testing, but production promotion requires managed storage, restore drills, retention enforcement, and externally anchored audit evidence.

## Rollback Gate

A rollback is complete only when the prior digest is serving, new writes are authoritative, audit events are retrievable by correlation ID, client errors return to baseline, and the incident commander records the decision evidence.

## Handover Evidence

The production handover packet must include the reviewed restore evidence JSON and the JSON output from `scripts/verify_production_handover.py`. The restore evidence bytes must match the SHA-256 and timestamp published by production readiness. Marker cleanup is valid only when the deleting tenant reads `404` afterward and the valid append-only chain contains the correlated `WORKSPACE_DELETED` event. A handover report is valid only for the exact target named in the report, must have verdict `GO`, and must be generated after the deployed image, database migration, IdP mapping, worker schedule, audit sink, retention policy, support route, egress policy, and restore evidence are finalized.
