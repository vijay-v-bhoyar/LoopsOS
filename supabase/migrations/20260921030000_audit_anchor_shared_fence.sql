-- Shared monotonic delivery fencing. Existing delivery receipts remain bound
-- to their old target and are not backfilled or replayed by this migration.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '60s';

ALTER TABLE audit_anchor_outbox ADD COLUMN IF NOT EXISTS delivery_epoch BIGINT;

CREATE TABLE IF NOT EXISTS audit_anchor_control (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  active_epoch BIGINT NOT NULL,
  active_binding TEXT NOT NULL,
  pending_epoch BIGINT,
  pending_binding TEXT,
  phase TEXT NOT NULL CHECK (phase IN ('active', 'draining')),
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_anchor_attempts (
  attempt_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES audit_anchor_outbox(event_id),
  epoch BIGINT NOT NULL,
  binding TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('admitted', 'uncertain', 'resolved')),
  admitted_at TEXT NOT NULL,
  resolved_at TEXT,
  detail TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_anchor_one_admitted_attempt
  ON audit_anchor_attempts(event_id) WHERE state = 'admitted';
CREATE INDEX IF NOT EXISTS idx_audit_anchor_unresolved_attempts
  ON audit_anchor_attempts(epoch, binding, state);

ALTER TABLE audit_anchor_control ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_anchor_attempts ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE role_name text;
BEGIN
 FOR role_name IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated') LOOP
  EXECUTE format('REVOKE ALL ON audit_anchor_control, audit_anchor_attempts FROM %I', role_name);
 END LOOP;
END;
$$;
