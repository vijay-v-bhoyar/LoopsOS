# LoopsOS audit-anchor assurance continuation

**Result: PASS for the tested local boundaries. Parent goal: PARTIAL. Enterprise release: NO_GO.**

This continuation follows the [connector repair](LOOPSOS_CONNECTOR_EGRESS_REPAIR_2026-09-21.md)
and updates the [thirteen-owner assessment](LOOPSOS_13_OWNER_REPAIR_ASSESSMENT_2026-09-21.md).
It strengthens agentic operations, security, data lifecycle, independent challenge
and human/AI operations. The original requirements remain intact; the risk register
now also retains findings F11 and F12.

## Reproduced failures

The independent baseline demonstrated that the audit-anchor client could select a
private numeric destination through DNS or a literal URL, and could route through
an ambient proxy. These were safe local protocol tests with controlled sockets and
synthetic data. They establish destination-selection defects, not a hosted exploit
with a real certificate-valid handshake. Unlike the tool connector, the old anchor
client had no initial DNS validation; the baseline does not prove a two-resolution
rebinding exploit on that particular path.

**F11 — outbox integrity and recovery:** changing a queued envelope's tenant or
hash did not stop the service from signing and transmitting it. Some malformed
envelopes raised before the per-record error handler, and malformed JSON could
abort the batch before valid records were attempted. Changing an envelope event
ID could also misattribute the acknowledgment. The threat boundary is queue
corruption or unauthorized queue mutation; no public API exploit is claimed.

**F12 — acknowledgment scope:** a recent acknowledgment was counted without
binding it to the current URL or signing key. A separate independent rotation
probe showed that a replacement destination received no event while historical
delivery status remained verified. This is a delivery-evidence binding defect,
not proof that every production readiness gate could be bypassed.

The [independent baseline](../output/loopsos-enterprise-repair/anchor/independent-baseline.json),
[rotation reproduction](../output/loopsos-enterprise-repair/anchor/independent-rotation.json)
and [author failing tests](../output/loopsos-enterprise-repair/anchor/author-baseline.log)
remain retained. The five initial author methods produced six failed subtests and
five errors before the repair.

## Implemented repairs

The default audit client now uses the shared numeric-destination transport with
the exact configured hostname as its allowlist. DNS answers are checked at each
new connection, unsafe address sets are denied, TLS retains the original hostname
and certificate checks, and ambient proxy routing is disabled. The constructor
validates the URL, signing key and finite positive timeout even when called
outside normal application initialization. Empty query and fragment delimiters
are rejected along with embedded credentials and other unsafe syntax.

The dispatcher reconstructs the envelope from its append-only audit event,
recomputes the event's content hash, and requires the queued canonical bytes to
match exactly. It signs the reconstructed source only after those checks. A bad
record remains visible, receives durable backoff, and does not prevent following
valid records from being processed. Recovery preserves the original event ID;
the service does not fabricate replacement audit history or silently repair data.

A nullable `delivery_binding` records a versioned HMAC of the exact endpoint under
the signing key. The public readiness and tenant-status routes query only the
current binding. URL, path or key changes cannot inherit old acknowledgment proof.
Legacy unbound records remain historical data; no historical payload is
automatically replayed to a replacement sink. New valid delivery can establish
current-bound status, while another tenant remains unverified.

SQLite performs an additive upgrade. PostgreSQL has an additive migration with
lock and statement timeouts, and schema admission rejects the missing column.
No hosted migration was executed. The [migration packet](../.loop/migrations/20260921020000_audit_anchor_delivery_binding/PLAN.md)
retains **UNKNOWN** hosted classification and the exact evidence needed to unpark it.

## Verification actually executed

| Check | Result | Scope and qualification |
|---|---|---|
| Focused author regressions | 13 passed | Queue/source integrity, batch isolation, recovery, destination/key changes, tenant scope, reopening, populated legacy SQLite upgrade and static PostgreSQL admission |
| Independent routing/integrity checks | 12 passed | Controlled socket/TLS streams; no real endpoint |
| Independent configuration/recovery checks | 13 passed | Unsafe configuration, redirect rejection, durable backoff and recovery after reopening |
| Independent binding/API checks | 12 passed | URL/path/key rotation, legacy receipts, old-writer receipt rejection, actual authenticated local ASGI status/drain and no historical replay |
| Full authority suite | 374 passed executions, 1 skipped | 375 executions, 355 distinct cases; 20 imported API cases are discovered twice |
| Release browser journey | 6 passed | Desktop/mobile against the real local authority, including current review and rejection behavior |
| Registry admission | PASS | Unchanged registry digest and lifecycle policy 1.1.0 |
| Refreshed graph | 164 code files; 2,033 nodes; 6,342 edges | Structural extraction; 82 unresolved references, zero dangling endpoints |

The independent total is **37 checks**, separate from and potentially overlapping
the author regressions. The skipped authority test requires a PostgreSQL DSN;
live PostgreSQL behavior remains unproven. The first integrated run retained two
failures caused by one old API assertion discovered twice: it expected an
unconfigured target to count historical delivery. The corrected test requires
zero current delivery and separately proves the historical record remains stored.
The [failed integrated run](../output/loopsos-enterprise-repair/anchor/full-first.log)
is retained alongside the passing rerun.

UI source and configuration were unchanged. Earlier full UI-unit/full-browser
results remain evidence for those unchanged surfaces; this slice reran the
six-case release journey. No claim is made that every earlier suite was rerun.

## Identity and evidence

One parent run, `LOOPSOS-ENTERPRISE-REPAIR-20260920`, remains governed by
`product-lifecycle-loop` with `codex-product-build-loop` as its sole delivery
engine. The [completion receipt](../output/loopsos-enterprise-repair/anchor/completion-receipt.json)
binds the executed checks to current source hashes. The [independent review](../output/loopsos-enterprise-repair/anchor/independent-review.md)
records its own source hashes and scope limits. Prior parent, report, risk and
verification snapshots are preserved under the anchor evidence directory.

Current source manifest: **315 files**; SHA-256:

`af68e093015bf19cea8636e464825632b44284e4ff44c3f952440661404a6226`

Registry: `skill-fleet/registry.json`; lifecycle policy **1.1.0**; registry SHA-256:

`1a3b198b8d6a6108ab0a3a8a194e86fc22039465ce724ee8782ba8ab732974b0`

## Known but unaddressed risks

An old worker can still transmit to its old endpoint. The independent probe
demonstrated this explicitly: current readers reject its receipt, but receipt
filtering is not revocation. Shared active-configuration fencing, worker draining
and credential revocation are the next local/operational boundaries to strengthen.

Delivery is at least once. A lost response, crash after acceptance, or concurrent
dispatchers can resend an event. The sink must verify exact signed bytes and
deduplicate event IDs. A 2xx/202 response proves HTTP acceptance, not durable
storage, immutable retention, independent custody, successful backup or restore.
Those sink contracts need organization-owned evidence.

The local source comparison does not defend against an administrator who can
rewrite the audit source and its database protections. Storage outages can also
prevent recording backoff. Sustained recovery time, alerting, queue volume and
database performance require operational validation. Hosted TLS/DNS/firewall
behavior, PostgreSQL/RLS and migration reversibility remain unproven.

All prior organizational, provider, privacy, cryptographic and enterprise-signoff
prerequisites remain open. Security scanner coverage remains degraded, and the
previous npm metadata permission request remains pending. No deployment, hosted
migration, provider charge, real anchor write or external notification occurred.

The next runnable work is shared configuration fencing for stale audit workers,
followed by the remaining OIDC network boundary. Hosted verification still needs
a named approved target, responsible owner, trust profile and execution authority.
The parent remains **PARTIAL** and enterprise release remains **NO_GO**.
