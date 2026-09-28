# Shared audit-anchor worker fence

## Authority and invariants

`audit_anchor_control` is the shared, monotonic writer authority. Every configured
worker has a positive `LOOPOS_AUDIT_ANCHOR_EPOCH` and a destination binding that
includes the epoch, endpoint, and signing key. The first worker initializes the
control row. A greater epoch enters `draining`; it becomes active only after all
admitted and uncertain attempts for the previous active epoch are resolved. A
lower epoch, an equal epoch with a different destination, or a conflicting
pending rotation is rejected.

Each outbound event requires a durable `audit_anchor_attempts` admission before
HTTP. The database transaction serializes the shared control row, checks the
event's `delivery_epoch`, enforces one admitted attempt per event, and returns an
attempt token. The transaction ends before network I/O. Completion compares the
exact token, event ID, epoch, and binding. A stale or duplicate completion cannot
mark delivery, increment backoff, or change the active epoch.

The outbox records the epoch eligible to deliver each event. On first adoption,
legacy unassigned rows are bound to that initial epoch. During later rotations,
existing rows keep their old epoch. New audit events created while rotation is
draining are assigned to the pending epoch. Old-epoch workers may retry only an
event with an unresolved uncertain attempt; they cannot claim new events while
draining. This prevents implicit historical replay to a different sink.

Network errors, cancellations, and non-2xx responses become `uncertain`. They
remain durable and block cutover; no age-based lease expires them. A same-ID
successful retry under the same epoch resolves earlier uncertainty because the
sink contract requires event-ID deduplication. If a process dies while an
attempt is `admitted`, or no same-epoch worker can safely retry an uncertain
event, the rotation stays parked. Operators must establish whether the old
process has stopped and reconcile the exact event ID against the sink before
restarting that epoch or escalating for an independently approved resolution.
Never clear an attempt by TTL or edit the row directly.

## Signed request contract

The v2 destination binding is:

```text
HMAC-SHA256(key,
  "loopos-audit-anchor-destination-v2\0" + decimal_epoch + "\0" + exact_endpoint)
```

For request body `B` and decimal epoch `E`, the sender sets
`x-loopos-anchor-epoch: E`, retains `x-loopos-event-id`, and computes:

```text
HMAC-SHA256(key, "loopos-audit-anchor-v2\n" + E + "\n" + B)
```

The sink must verify the epoch-bound signature, enforce its accepted epoch
high-water mark, reject lower epochs, deduplicate event IDs, and return 2xx only
after durable acceptance. A 2xx proves transport acknowledgment only. The sink's
high-water enforcement, WORM/SIEM retention, identity, and restore contract still
need independent evidence. The local app cannot prove those properties by
itself.

## Rotation runbook

1. Review the exact next endpoint, key custody, and greater epoch with the
   service owner. Configure the sink to verify v2 and reject lower epochs.
2. Drain old workers before removing network or key access. Legacy binaries do
   not consult `audit_anchor_control`; the shared fence only coordinates
   binaries that implement this protocol. Revoke their old capability as part
   of the controlled cutover.
3. Keep the old worker on its old configuration while durable attempts remain.
   It can retry only uncertain event IDs. Check
   `GET /v1/audit/anchors/status` for `phase`, active/pending epochs, unresolved
   attempts, and whether this worker is admitted.
4. Start the new worker with the greater `LOOPOS_AUDIT_ANCHOR_EPOCH`. It remains
   non-admitted while old attempts are unresolved. When the last old attempt is
   acknowledged, it activates the pending epoch. New events are then eligible
   for the new sink.
5. Reconcile any old-epoch undelivered rows under the approved retention and
   transfer policy. They remain parked and keep production readiness fail-closed;
   a destination change never silently forwards historical data.
6. Verify the new epoch, a fresh acknowledged event, zero backlog, sink-side
   deduplication, and independently retained evidence before changing the
   operational release decision.

If an attempt remains `admitted` after its worker dies, do not infer that it is
safe to retry or rotate. Preserve the row and raise an operations escalation
with the event ID, attempt ID, epoch, endpoint binding digest, last observed
transport state, and sink lookup result. Local readiness remains `NO_GO` until
the authoritative owner documents and records a safe resolution.

## Database and verification boundary

SQLite creates the control and attempt tables locally. PostgreSQL adds them
through `20260921030000_audit_anchor_shared_fence.sql`, enables RLS, revokes
`anon` and `authenticated`, and adds `delivery_epoch` without backfilling it.
The store refuses PostgreSQL startup when the fencing migration is absent.
Hosted migration status is **UNKNOWN / NOT EXECUTED**. Local two-connection
tests prove the source-level lock and token behavior against SQLite only; they
do not prove hosted PostgreSQL lock timing, mixed-version shutdown, sink
high-water enforcement, WORM retention, or operational rollback.
