# Aggregate external-effect admission

The authority reserves exposure in its own durable database before an HTTP mutation is dispatched. All runs, retries and compensating HTTP actions for a tenant share cumulative accounts. Local `record_action` remains available without external-effect policy. External HTTP action dispatch fails closed when the tenant/route policy, database, ceiling, policy epoch, reservation lease or kill-switch check is unavailable or unsuitable.

This bounds **configured request exposure**, not all financial loss, vendor invoices or business outcomes. A dispatch count is a count. `USD_minor` is an integer amount in the request's configured currency/amount fields; it is not proof that a remote service enforces that amount, that downstream charges cannot exceed it, or that a refund occurred. The organization's reviewed adapter/contract must establish what each mapped field means. Evidence reads, probe GETs and optional model calls are outside this mutation ledger and still need their own provider-cost controls before any claim of complete business-cost containment.

## Protected configuration

`LOOPOS_EFFECT_BUDGET_POLICY_JSON` is protected deployment configuration, parsed into `Settings.effect_budget_policy`. No API caller, model response or browser field can supply or enlarge it. There are no default production ceilings. The following illustrates the **shape**, with deliberately synthetic values rather than recommended organization risk appetite:

```json
{
  "version": 1,
  "scope": "cumulative",
  "policy_epoch": 1,
  "tenants": {
    "tenant-example": {
      "ceilings": { "dispatch_count": 20, "USD_minor": 10000 },
      "routes": [{
        "endpoint": "https://approved.example/payments",
        "method": "POST",
        "evidence_ref": "organization-reviewed-adapter-contract-and-budget-approval",
        "charges": [
          { "unit": "dispatch_count", "fixed": 1 },
          { "unit": "USD_minor", "amount_path": "payment.amount_minor", "currency_path": "payment.currency", "currency": "USD", "max_amount": 2000 }
        ]
      }]
    }
  }
}
```

Every route is an exact endpoint/method match and must charge one `dispatch_count`. Additional units may be fixed positive integer quantities or integer quantities from named body paths with a per-action maximum. Money units require explicit currency and amount paths; floats, booleans, numeric strings, negative quantities, missing values and mismatched currencies are refused. Units are never converted or summed across currencies. The normal allowlist, credentials, request size and approval requirements still apply.

An empty/absent policy grants no external action authority. For policy updates, supply a strictly greater `policy_epoch` and retain the organization's approval evidence. Same-epoch content changes and older worker configurations are refused. A durable shared active policy hash fences previously running workers after an epoch advancement. Existing reservations made under another policy cannot be reclaimed or dispatched; cancel only a provably unsent reservation, then replan and obtain applicable approvals. Revocation can advance the epoch with an empty `tenants` object. Removing a process environment variable alone does not revoke already running workers: advance the shared epoch or activate the kill switch.

Changing an epoch never resets cumulative usage. Raising a ceiling is a new organization-authorized policy decision. Tightening below already held exposure blocks new work and retains the exposure. No automatic daily reset, lease expiry or restart clears incurred/unknown exposure.

## States and failure behavior

1. `reserved`: all dimensions charged atomically before dispatch. A competing worker cannot reuse the live reservation. After the pre-dispatch lease expires, the same immutable request may be reclaimed with a higher fence; the old fence can neither dispatch nor cancel it.
2. `dispatched`: committed before calling the external service. Policy epoch and kill-switch state are checked at this boundary. A crash after this marker is ambiguous and cannot be automatically retried. Remote systems must enforce their own idempotency and any stronger commit-time fencing; a local kill switch cannot undo an already issued network request.
3. `consumed`: an observed successful response is stored durably. A same-request replay returns the stored result and does not charge or execute twice. A changed payload cannot reuse the reservation identity.
4. `unknown`: transport loss, malformed response, redirects, unsuccessful HTTP response or cancellation after dispatch retains every charge. A 503 is not proof that no external change occurred. Automatic redispatch is refused even with the same idempotency key.
5. `cancelled`: only a current fenced reservation known not to have dispatched can release its held charge. That identity can never dispatch afterward.
6. Reconciliation: a trusted internal operator can record `applied` or `not_applied`, with accountable actor and external evidence reference. This seam is not exposed to models or through a public API. The deploying organization must authorize the operator and independently verify the evidence. Reconciliation after dispatch never automatically refunds exposure, since an unapplied business change does not establish zero provider cost or downstream loss. Partial compensation remains unresolved until appropriately scoped external evidence establishes its result.

Tool-invocation replay is bound to the originating tenant, workspace, loop workflow, tool, idempotency key and exact request payload. A completed request may return its stored result to a retry in that same scope without dispatching again. Reusing the key from another workspace or loop fails closed with a conflict before any stored result is returned; use a new key for a distinct workflow. This protects result isolation while retaining same-workflow deduplication.

The execution engine reports unknown/denied external effects as `BLOCKED`; it does not automatically run a local rollback and claim that an uncertain remote effect was reversed. Separately authorized rollback remains possible through the existing governed mechanism and has its own aggregate reservation when consequential. Original charges remain. An operator must provision a reviewed compensation budget route beforehand if recovery requires external calls; the application will not enlarge a ceiling to make recovery proceed.

The ledger records immutable event history and policy hashes. SQLite uses the authority's `BEGIN IMMEDIATE` transaction; Postgres uses a locked active-policy row and deterministic account locking. Budget-account increments and reservation creation are one transaction. Postgres tables have RLS enabled and ordinary Supabase `anon`/`authenticated` privileges revoked. The migration is `supabase/migrations/20260921010000_effect_budget.sql`; the authority readiness schema list includes all four tables. No production schema rollback or deployment was performed during local verification.

## Readiness, evidence and remaining integration

Production allowlist mode requires available configured aggregate policy and durable ledger. Deny-all mode can satisfy `aggregate_effect_budget_verified` without an effect policy because outbound actions are disabled. The browser rejects enterprise readiness when this new field is absent or false. Unknown tenants/routes still fail at the actual tool boundary even when global readiness is healthy.

Executed local checks cover independent SQLite connection races, tenant and unit isolation, atomic multi-unit denial, restart, success replay, expired lease fencing, stale policy epochs, revocation, cancellation, kill switch, unknown HTTP outcomes, engine blocking without automatic rollback, compensation exposure, append-only events, readiness and existing connector behavior. PostgreSQL migration structure/RLS declarations were checked statically; no authenticated live PostgreSQL target was provided.

Before production, the organization must provide reviewed ceilings and metric mappings, hosted database/migration proof, actor-authorized reconciliation operation, real connector idempotency/commit semantics, cancellation/rollback observations and provider billing exposure controls. Local fixtures establish the application boundary; they do not certify an organization's risk appetite or a vendor's financial liability.
