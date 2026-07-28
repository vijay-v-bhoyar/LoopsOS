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

The Vite server proxies `/authority` to port `8787`. Open the Workspace Console, wait for `Authority connected`, choose a loop, and select `Run loop`. Authorized users can approve or reject exact payloads, request compensation, create recovery successors, and verify the tenant audit chain from the same panel.

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

The schema lives in `supabase/migrations/20260720010000_loopos_authority.sql`. It creates the authority tables, enables RLS, revokes `anon` and `authenticated` access to the exposed `public` tables, and adds triggers that reject audit-event updates and deletes.

Local Supabase requires Docker or a compatible container runtime and is for development or beta evaluation only. Do not expose the local Supabase stack to external traffic.

## Configuration

| Variable | Purpose |
| --- | --- |
| `LOOPOS_DATABASE_PATH` | Durable SQLite path; use persistent encrypted storage |
| `LOOPOS_STORAGE_BACKEND` | `sqlite` by default; set to `postgres` for Supabase/local Postgres |
| `LOOPOS_POSTGRES_DSN` | Postgres DSN required when `LOOPOS_STORAGE_BACKEND=postgres` |
| `LOOPOS_SESSION_HMAC_SECRET` | Session signing secret, minimum 32 bytes outside development |
| `LOOPOS_ALLOW_DEV_AUTH` | Enables self-service local sessions; must be `false` in enterprise environments |
| `LOOPOS_ALLOWED_HTTP_HOSTS` | Comma-separated exact connector hostname allowlist |
| `LOOPOS_CONNECTOR_BEARER_TOKENS_JSON` | Server-only JSON map of host to bearer token; never expose through Vite variables |
| `LOOPOS_WEBHOOK_SECRETS_JSON` | Server-only JSON map of `tenant:system` or `system` to HMAC secret for verified webhook evidence |
| `LOOPOS_CORS_ORIGINS` | Exact allowed UI origins |

## Production Boundary

Development sessions deliberately make local evaluation easy. Enterprise deployment must disable them and place a BFF or identity-aware gateway in front of the service that issues compatible short-lived sessions from verified IdP claims. SQLite supports a durable single-instance deployment. Supabase/Postgres is the recommended beta path when teams need shared durable storage, migration history, and a clearer route to managed Postgres. Horizontal scale still requires a managed transactional database, shared work queue, backup/restore proof, and the same store invariants.

The hash chain detects ordinary event mutation but is not a substitute for an externally anchored WORM/SIEM audit sink against a privileged database administrator. Export or replicate event hashes to that enterprise sink before treating the service as a compliance authority.

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
