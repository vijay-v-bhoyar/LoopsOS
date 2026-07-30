# LoopOS Governed Execution Authority

The authority service turns a LoopOS descriptor into a durable, observable run. It uses the repository state machine and vendored standard hash as executable inputs rather than maintaining a second lifecycle definition.

## What Executes

Every run follows the corpus transition graph from `TRIGGERED` through evidence collection, diagnosis, planning, authorization, action, validation, proof, and effectiveness. The service provides:

- SQLite durability with WAL, foreign keys, tenant-scoped queries, and idempotent create commands.
- Optional Supabase/local Postgres storage using the same authority store contract and append-only audit triggers.
- Payload-bound, 15-minute, single-use approvals for R3/R4 and external-effect actions; expired approvals can be renewed without replacing their history.
- Exact-payload rejection decisions that atomically block the run and remain in the audit trail.
- Write-ahead tool intent, bounded retries for retryable actions and connected reads, and idempotency replay.
- `record_action` and allowlisted `http_json_action` contracts.
- Workspace and HTTP JSON evidence collection.
- Immediate validation probes plus immediate or durably scheduled effectiveness probes.
- Durable successful and failed outputs, including validation findings and compensation results.
- Compensating actions and immutable linked recovery runs with fresh dispatch keys.
- SHA-256 chained append-only events protected against update/delete by database triggers.
- Authenticated SSE event delivery and evidence/output APIs.
- Durable connector evidence events for Jira/GitHub/manual sources, stored with payload hashes and tenant isolation.
- Durable release assurance initiative records that bind connector event IDs, release gates, exceptions, loop bundles, and proof-pack scope to the tenant audit chain.

## Local Run

```powershell
python -m pip install -r authority\requirements.txt
$env:PYTHONPATH="authority"
python -m uvicorn loopos_authority.api:app --host 127.0.0.1 --port 8787
```

The Vite server proxies `/api` to port `8787`. Open the Workspace Console, wait for `Authority connected`, choose a loop, and select `Run loop`. Authorized users can approve or reject exact payloads, request compensation, create recovery successors, and verify the tenant audit chain from the same panel.

## Release Assurance Records

Connector events are durable evidence records for the SDLC productivity moat. Authenticated users can create session-scoped snapshots through `POST /v1/connector-events` and list them through `GET /v1/connector-events?workspace_id=...`. GitHub and Jira webhooks can create `verified_webhook` snapshots through `POST /v1/webhooks/{tenant_id}/{system}?workspace_id=...` only when a per-tenant secret is configured and the raw request body HMAC matches. The authority stores the bounded source payload, records a stable payload hash, deduplicates identical system/external-id/payload combinations, rejects a reused webhook delivery ID with a different payload, isolates records by tenant, records verification status, and appends `CONNECTOR_EVENT_RECORDED` to the audit chain.

Release initiatives are durable planning records created through `POST /v1/release-initiatives` with an `Idempotency-Key` and listed through `GET /v1/release-initiatives?workspace_id=...`. The authority validates loop IDs and connector event IDs, stores the bounded release assurance payload, isolates records by tenant, and appends `RELEASE_INITIATIVE_RECORDED` to the audit chain.

When a release initiative binds connector event IDs, the authority also records a deterministic freshness summary. V1 policy treats release connector evidence as fresh only when every linked event has a valid `observed_at` timestamp within 24 hours of the authority release record. Missing evidence is `missing`; old or malformed timestamps are `stale`. The summary records source counts, webhook-verified counts, session-snapshot counts, oldest/newest observation time, and stale event IDs.

The authority also records a deterministic readiness verdict for each release initiative. `GO` requires fresh connector evidence and all release assurance gates passed. Stale or missing evidence, missing gates, blocked gates, and evidence gaps produce `NO_GO`. Review-required gates and active exceptions produce `REVIEW_REQUIRED` only when no fail-closed condition is present. This verdict is a readiness decision for the recorded release packet; production deployment still requires a separate governed action with its own payload-bound approval and rollback contract.

Authority proof packs are generated through `GET /v1/release-initiatives/{initiative_id}/proof-pack`. The endpoint rebuilds Markdown from the tenant-scoped durable release record, linked connector evidence, freshness summary, and readiness verdict, then returns a SHA-256 hash of that Markdown. Each generation appends `PROOF_PACK_GENERATED` with the Markdown hash, release verdict, freshness status, and source event IDs to the tenant audit chain. The retrieval timestamp is response metadata, not part of the hashed Markdown, so the hash is stable while the durable release record is unchanged. Proof packs are read-only evidence packets with audited generation; they do not create, approve, or execute production changes.

These records do not claim live Jira or GitHub authority by themselves. Connector reads and write-back remain separate governed actions: shadow-read evidence can support a proof pack, while comments, status checks, issue updates, or release decisions must go through payload-bound approval and the existing tool/action contract.

## Local Supabase Storage

SQLite remains the zero-dependency default. To run the authority service against local Supabase Postgres, install the Supabase CLI and start the local stack from the repository root:

```powershell
supabase start
$env:LOOPOS_STORAGE_BACKEND="postgres"
$env:LOOPOS_POSTGRES_DSN="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
$env:PYTHONPATH="authority"
python -m uvicorn loopos_authority.api:app --host 127.0.0.1 --port 8787
```

The schema lives in `supabase/migrations/20260720010000_loopos_authority.sql`. It creates the authority tables, leased execution-job queue, and audit-anchor outbox; enables RLS; revokes `anon` and `authenticated` access to the exposed `public` tables; and adds triggers that reject audit-event updates and deletes.

Local Supabase requires Docker or a compatible container runtime and is for development or beta evaluation only. Do not expose the local Supabase stack to external traffic.

## Configuration

| Variable | Purpose |
| --- | --- |
| `LOOPOS_DATABASE_PATH` | Durable SQLite path; use persistent encrypted storage |
| `LOOPOS_STORAGE_BACKEND` | `sqlite` by default; set to `postgres` for Supabase/local Postgres |
| `LOOPOS_POSTGRES_DSN` | Postgres DSN required when `LOOPOS_STORAGE_BACKEND=postgres` |
| `LOOPOS_SESSION_HMAC_SECRET` | Session signing secret, minimum 32 bytes outside development |
| `LOOPOS_ALLOW_DEV_AUTH` | Enables self-service local sessions; must be `false` in enterprise environments |
| `LOOPOS_OIDC_ISSUER` | Exact HTTPS issuer accepted for production identity assertions |
| `LOOPOS_OIDC_AUDIENCE` | Exact audience required in production identity assertions |
| `LOOPOS_OIDC_JWKS_URL` | HTTPS JWKS endpoint used to verify RS256 identity assertions |
| `LOOPOS_OIDC_TENANT_CLAIM` | Claim containing the authoritative tenant ID; defaults to `tenant_id` |
| `LOOPOS_OIDC_ROLE_CLAIM` | Claim containing external groups or roles; defaults to `groups` |
| `LOOPOS_OIDC_ROLE_MAPPING_JSON` | Explicit map from external groups to LoopOS roles; ambiguous mappings are rejected |
| `LOOPOS_ALLOWED_HTTP_HOSTS` | Comma-separated exact connector hostname allowlist |
| `LOOPOS_CONNECTOR_BEARER_TOKENS_JSON` | Server-only JSON map of host to bearer token; never expose through Vite variables |
| `LOOPOS_WEBHOOK_SECRETS_JSON` | Server-only JSON map of `tenant:system` or `system` to HMAC secret for verified webhook evidence |
| `LOOPOS_CORS_ORIGINS` | Exact allowed UI origins |
| `LOOPOS_AUDIT_ANCHOR_URL` | HTTPS endpoint for the approved append-only WORM/SIEM sink |
| `LOOPOS_AUDIT_ANCHOR_HMAC_SECRET` | Server-only HMAC secret, minimum 32 bytes, shared with the audit sink |
| `LOOPOS_AUDIT_ANCHOR_POLL_SECONDS` | Retry worker polling interval; defaults to 5 seconds |
| `LOOPOS_RETENTION_POLICY_URL` | HTTPS reference to the approved retention and deletion policy |
| `LOOPOS_SUPPORT_CONTACT` | Accountable operational owner or escalation route |
| `LOOPOS_OUTBOUND_POLICY_MODE` | Explicit `deny_all` or `allowlist`; allowlist mode requires allowed HTTP hosts |
| `LOOPOS_BACKUP_RESTORE_EVIDENCE_URL` | HTTPS reference to the latest approved restore exercise evidence |
| `LOOPOS_BACKUP_RESTORE_EVIDENCE_SHA256` | Lowercase SHA-256 of the exact restore evidence JSON |
| `LOOPOS_BACKUP_RESTORE_VERIFIED_AT` | Timestamp of the reviewed restore exercise |
| `LOOPOS_BACKUP_RESTORE_MAX_AGE_DAYS` | Maximum accepted age of restore evidence; defaults to 90 days |
| `LOOPOS_OPERATIONAL_EVIDENCE_URL` | Credential-free HTTPS reference to the reviewed retention, support, and outbound-control packet |
| `LOOPOS_OPERATIONAL_EVIDENCE_SHA256` | Lowercase SHA-256 of the exact operational evidence JSON |
| `LOOPOS_OPERATIONAL_EVIDENCE_VERIFIED_AT` | Timestamp matching the operational evidence packet `generated_at` |
| `LOOPOS_OPERATIONAL_EVIDENCE_MAX_AGE_DAYS` | Maximum accepted age of operational evidence; defaults to 90 days |
| `LOOPOS_WORKER_TOKEN` | Minimum-32-byte token protecting worker/cron dispatch; `CRON_SECRET` is accepted as a Vercel-compatible fallback |
| `LOOPOS_EXECUTION_WORKER_MODE` | `internal` for a long-lived worker loop or `external` for protected cron dispatch; defaults to `external` on Vercel |
| `LOOPOS_EXECUTION_WORKER_POLL_SECONDS` | Poll interval for long-lived authority workers; defaults to 0.25 seconds |
| `LOOPOS_EXECUTION_WORKER_HEARTBEAT_MAX_AGE_SECONDS` | Maximum age of the durable worker-dispatch heartbeat; defaults to 180 seconds |
| `LOOPOS_EXECUTION_JOB_LEASE_SECONDS` | Renewable database lease duration; defaults to 120 seconds |
| `LOOPOS_EXECUTION_JOB_MAX_ATTEMPTS` | Maximum infrastructure dispatch attempts before a job is terminally failed |

## Production Boundary

Development sessions deliberately make local evaluation easy. Enterprise deployment must disable them and place an identity-aware gateway in front of the service. The gateway supplies a signed OIDC assertion through the same-origin session exchange; LoopOS verifies the fixed issuer, audience, RS256 signature, expiry, tenant claim, and explicit external-role mapping before issuing a 15-minute application session. Session issuance creates an audited tenant event and immediately attempts delivery through the signed external-anchor outbox. Production readiness rejects missing identity configuration, SQLite persistence, missing audit-anchor configuration, an audit sink that has never accepted a signed envelope, undelivered anchor backlog, missing durable-worker dispatch, missing retention/support/outbound bindings, and missing or stale restore-evidence references.

Starting, rolling back, and delayed-effectiveness work is committed to `execution_jobs` in the same database transaction as the run status. Workers claim rows with renewable leases; Postgres uses row locks and `SKIP LOCKED`; expired work can be reclaimed after process death. Every successful poll records a durable, mode-specific heartbeat, and production readiness rejects a missing, stale, or wrong-mode heartbeat. Long-lived deployments poll internally. Serverless deployments invoke `POST /v1/operations/jobs/drain` with `X-LoopOS-Worker-Token` or `Authorization: Bearer <CRON_SECRET>`; the checked-in Vercel schedule invokes it every minute and also drains the audit-anchor outbox. The sink and tool contracts must remain idempotent because a lease-recovery path can repeat a request after an ambiguous process failure.

Every audit-event insert atomically creates an outbox envelope containing the chain hashes and canonical event fields. The worker signs the exact canonical request bytes with `x-loopos-signature-256`, supplies `x-loopos-event-id` for sink-side idempotency, marks only 2xx responses delivered, and retains bounded failure details with exponential retry timing. Auditors and executives can inspect `GET /v1/audit/anchors/status`; executives can request an immediate retry through `POST /v1/audit/anchors/drain`.

The sink must verify the signature, deduplicate the event ID, and retain the envelope under the approved immutable retention policy. The database hash chain and outbox are not substitutes for that independently administered sink. Readiness requires credential-free HTTPS references, lowercase SHA-256 digests, and recent timestamps for both restore and operational evidence. The operational packet is bound to a deterministic fingerprint of the deployed retention URL, support route, outbound mode, and host allowlist. The production handover verifier independently reads both artifacts and requires exact digest, timestamp, fingerprint, and semantic control coverage before returning `GO`.

## Tests

```powershell
$env:PYTHONPATH="authority"
python -m unittest discover -s authority\tests -v
```

To run the live local Supabase/Postgres storage test after `supabase start`:

```powershell
$env:LOOPOS_TEST_POSTGRES_DSN="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
$env:PYTHONPATH="authority"
python -m unittest authority.tests.test_authority.PostgresStorageIntegrationTests -v
```
