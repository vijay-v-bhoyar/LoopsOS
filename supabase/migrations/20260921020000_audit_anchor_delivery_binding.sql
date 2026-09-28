-- Additive migration: legacy acknowledgments stay retained but unbound.
-- No historical payload is replayed to a new destination by this migration.
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '60s';
ALTER TABLE audit_anchor_outbox ADD COLUMN IF NOT EXISTS delivery_binding TEXT;
