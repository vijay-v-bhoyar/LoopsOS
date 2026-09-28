# Audit anchor transport, integrity and delivery binding

The audit anchor is an independently configured destination. Its default client
uses the same numeric-address connection guard as the HTTP tools, with the exact
configured hostname as its allowlist. Ambient proxy routing is disabled, TLS
verification is mandatory, redirects are not followed, and the constructor
rejects unsafe URL syntax, missing/short signing keys and nonpositive/nonfinite
timeouts. Explicit local HTTP is available only through development composition.
See [the connection contract](CONNECTOR_EGRESS.md).

Before signing, the dispatcher reconstructs each envelope from its append-only
audit row, recomputes that row's content hash and requires the outbox's exact
canonical bytes to match. Wrong identities, tenant, sequence, payload, hash or
extra fields cannot become a newly signed event. This is a per-event check,
not replacement for full-chain verification or an external immutable ledger.

Malformed records are retained. Each failure receives the existing durable
backoff, and independent valid records in the batch continue. The dispatcher
does not silently repair, erase or replace audit data. A reviewed repair must
restore bytes from the authoritative event and preserve its identity. Database
unavailability itself remains an operational fault; a backoff write is not
guaranteed when storage cannot commit.

After a 2xx response, `delivery_binding` binds the acknowledgment to the exact
URL, signing key, and configured epoch using a versioned HMAC digest. The key
itself is never persisted in the delivery row or returned in status. Public
readiness and tenant-scoped status queries require the current binding and an
admitted shared writer epoch. URL, key, or epoch changes invalidate old proof
for that target. Unconfigured and legacy unbound records cannot satisfy current
readiness. Store-level queries with no binding remain historical diagnostics
and must not be used as an enterprise gate.

Old receipts stay retained. A target change does not automatically replay
historical events to a new sink; historical transfer needs separately approved
scope and retention policy. A fresh startup event or other new valid event must
be acknowledged under the new binding before readiness succeeds. Tenant status
requires that tenant's own bound evidence.

## Delivery and recovery limits

Delivery is at least once. Timeouts and lost responses can cause later retries.
The shared database now serializes admissions and epoch activation across
current-version processes. Durable attempt tokens fence completion, and
uncertain attempts block rotation until same-ID acknowledgment or explicit
operator reconciliation. See [the shared fence and rotation runbook](AUDIT_ANCHOR_FENCING.md).
The destination must verify the epoch-bound v2 signature and deduplicate
`x-loopos-event-id`. The sink's high-water enforcement, durable acknowledgment,
immutability, retention and backup/restore contract remain deployment evidence
requirements. An HTTP 2xx is a transport acknowledgment, not independent proof
that a WORM/SIEM record exists or will remain retained.

The database fence coordinates only workers running this implementation. Old
binaries do not consult it, so they must be stopped and their network/key
capabilities revoked during target/key rotation. The v2 sink must reject epochs
below its accepted high-water mark. The control plane, secret custody, firewall
and custom transport composition remain trusted platform boundaries. Hosted
routing, TLS custody and custom network translation require their own
verification.

## Schema and deployment

SQLite adds nullable `delivery_binding` and `delivery_epoch` columns, plus
shared control and attempt tables. The tested local upgrade retains old receipts
without inventing a binding or epoch. PostgreSQL migration
`20260921020000_audit_anchor_delivery_binding.sql` adds the nullable binding;
`20260921030000_audit_anchor_shared_fence.sql` adds the epoch and shared fence
tables without backfill or historical replay. Each migration uses a two-second
lock timeout and sixty-second statement timeout. PostgreSQL schema admission
rejects a missing binding or epoch column.

Hosted migration status is **UNKNOWN / NOT EXECUTED**. Static parsing and local
SQLite tests do not establish PostgreSQL lock behavior or reversibility. Before
hosted use, run the migration on an authorized disposable restored clone, verify
row/chain/receipt parity and old/new application behavior, and measure delivery
query cost at representative volume. A production index plan must be reviewed
separately; this transactional migration does not build a blocking large index.
New code must not start against an unmigrated PostgreSQL schema. Preserve the
additive column on application rollback; dropping it discards binding evidence.
Old code cannot enforce the current-target readiness rule and must not receive
enterprise traffic during a rollback merely because the schema is compatible.

Safe-local tests: `authority/tests/test_audit_anchor_security.py`, existing
authority anchor/API tests, and independent probes retained under
`output/loopsos-enterprise-repair/anchor/`. No hosted migration, real anchor write
or secret use is implied by these tests.
