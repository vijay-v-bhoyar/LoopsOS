-- Aggregate exposure is server-owned, tenant-scoped and cumulative; no periodic reset.
CREATE TABLE IF NOT EXISTS effect_budget_policy (
 singleton INTEGER PRIMARY KEY CHECK (singleton = 1), epoch BIGINT NOT NULL, policy_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS effect_budget_accounts (
 tenant_id TEXT NOT NULL, unit TEXT NOT NULL, used BIGINT NOT NULL CHECK (used >= 0), PRIMARY KEY (tenant_id, unit)
);
CREATE TABLE IF NOT EXISTS effect_budget_reservations (
 tenant_id TEXT NOT NULL, invocation_id TEXT NOT NULL, run_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 policy_hash TEXT NOT NULL, charges_json TEXT NOT NULL, status TEXT NOT NULL, fence BIGINT NOT NULL,
 lease_expires_at DOUBLE PRECISION NOT NULL, result_json TEXT, PRIMARY KEY (tenant_id, invocation_id)
);
CREATE TABLE IF NOT EXISTS effect_budget_events (
 event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, invocation_id TEXT NOT NULL,
 kind TEXT NOT NULL, observed_at DOUBLE PRECISION NOT NULL, detail_json TEXT NOT NULL
);
ALTER TABLE effect_budget_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE effect_budget_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE effect_budget_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE effect_budget_events ENABLE ROW LEVEL SECURITY;
DROP TRIGGER IF EXISTS effect_budget_events_no_update ON effect_budget_events;
CREATE TRIGGER effect_budget_events_no_update BEFORE UPDATE ON effect_budget_events FOR EACH ROW EXECUTE FUNCTION deny_audit_event_mutation();
DROP TRIGGER IF EXISTS effect_budget_events_no_delete ON effect_budget_events;
CREATE TRIGGER effect_budget_events_no_delete BEFORE DELETE ON effect_budget_events FOR EACH ROW EXECUTE FUNCTION deny_audit_event_mutation();
DO $$
DECLARE role_name text;
BEGIN
 FOR role_name IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated') LOOP
  EXECUTE format('REVOKE ALL ON effect_budget_policy, effect_budget_accounts, effect_budget_reservations, effect_budget_events FROM %I', role_name);
 END LOOP;
END;
$$;
