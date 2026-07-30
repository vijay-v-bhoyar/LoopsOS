create table if not exists runs (
  run_id text primary key,
  tenant_id text not null,
  workspace_id text not null,
  loop_id text not null,
  title text not null,
  trigger_text text not null,
  state text not null,
  runner_status text not null,
  risk_tier text not null,
  requires_approval integer not null,
  payload_hash text not null,
  plan_json text not null,
  attempt integer not null default 0,
  created_by text not null,
  created_at text not null,
  updated_at text not null,
  last_error text,
  output_json text,
  request_key text not null,
  recovery_of text references runs(run_id),
  effectiveness_due_at text,
  unique(tenant_id, request_key)
);

create index if not exists idx_runs_tenant_updated on runs(tenant_id, updated_at desc);

create table if not exists approvals (
  approval_id text primary key,
  tenant_id text not null,
  run_id text not null references runs(run_id),
  payload_hash text not null,
  render_hash text not null,
  render_json text not null,
  decision text not null,
  decision_reason text not null,
  actor_id text not null,
  actor_role text not null,
  created_at text not null,
  expires_at text not null,
  consumed_at text
);

create index if not exists idx_approvals_run_payload on approvals(tenant_id, run_id, payload_hash, decision, created_at desc);

create table if not exists evidence (
  evidence_record_id text primary key,
  tenant_id text not null,
  run_id text not null references runs(run_id),
  evidence_id text not null,
  kind text not null,
  source_ref text not null,
  content_json text not null,
  content_hash text not null,
  collected_at text not null,
  expires_at text not null,
  unique(tenant_id, run_id, evidence_id)
);

create table if not exists tool_invocations (
  invocation_id text primary key,
  tenant_id text not null,
  run_id text not null references runs(run_id),
  tool_name text not null,
  idempotency_key text not null,
  request_json text not null,
  request_hash text not null,
  status text not null,
  attempts integer not null default 0,
  result_json text,
  error_code text,
  error_message text,
  started_at text not null,
  completed_at text,
  unique(tenant_id, tool_name, idempotency_key)
);

create table if not exists probe_results (
  probe_result_id text primary key,
  tenant_id text not null,
  run_id text not null references runs(run_id),
  phase text not null,
  probe_id text not null,
  passed integer not null,
  detail_json text not null,
  created_at text not null
);

create table if not exists action_artifacts (
  artifact_id text primary key,
  tenant_id text not null,
  run_id text not null references runs(run_id),
  idempotency_key text not null,
  artifact_json text not null,
  created_at text not null,
  compensated_at text,
  unique(tenant_id, idempotency_key)
);

create table if not exists workspaces (
  tenant_id text not null,
  workspace_id text not null,
  revision integer not null,
  document_json text not null,
  document_hash text not null,
  created_by text not null,
  updated_by text not null,
  created_at text not null,
  updated_at text not null,
  primary key(tenant_id, workspace_id)
);

create index if not exists idx_workspaces_tenant_updated on workspaces(tenant_id, updated_at desc);

create table if not exists release_initiatives (
  initiative_id text primary key,
  tenant_id text not null,
  workspace_id text not null,
  title text not null,
  description text not null,
  workflow_type text not null,
  business_outcome text not null,
  maturity text not null,
  risk_tier text not null,
  status text not null,
  release_name text not null,
  loop_bundle_json text not null,
  source_event_ids_json text not null default '[]',
  release_assurance_json text not null,
  freshness_summary_json text not null default '{}',
  readiness_verdict_json text not null default '{}',
  created_by text not null,
  created_at text not null,
  updated_at text not null,
  request_key text not null,
  unique(tenant_id, request_key)
);

create index if not exists idx_release_initiatives_tenant_workspace on release_initiatives(tenant_id, workspace_id, updated_at desc);

create table if not exists connector_events (
  connector_event_id text primary key,
  tenant_id text not null,
  workspace_id text not null,
  system text not null,
  event_kind text not null,
  external_id text not null,
  label text not null,
  url text,
  observed_at text not null,
  payload_hash text not null,
  payload_json text not null,
  verification_status text not null default 'session_authenticated',
  delivery_id text,
  created_by text not null,
  created_at text not null,
  unique(tenant_id, system, external_id, payload_hash)
);

create index if not exists idx_connector_events_tenant_workspace on connector_events(tenant_id, workspace_id, observed_at desc);
create unique index if not exists idx_connector_events_delivery on connector_events(tenant_id, system, delivery_id) where delivery_id is not null;

create table if not exists audit_events (
  sequence bigint generated always as identity primary key,
  event_id text not null unique,
  tenant_id text not null,
  run_id text references runs(run_id),
  event_type text not null,
  state text,
  actor_id text not null,
  payload_json text not null,
  created_at text not null,
  previous_hash text not null,
  event_hash text not null unique
);

create index if not exists idx_audit_tenant_sequence on audit_events(tenant_id, sequence);
create index if not exists idx_audit_run_sequence on audit_events(run_id, sequence);

create table if not exists audit_anchor_outbox (
  event_id text primary key references audit_events(event_id),
  tenant_id text not null,
  envelope_json text not null,
  attempts integer not null default 0,
  next_attempt_at text not null,
  last_error text,
  delivered_at text,
  created_at text not null
);

create index if not exists idx_audit_anchor_pending
  on audit_anchor_outbox(delivered_at, next_attempt_at, created_at);

create or replace function deny_audit_event_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'audit events are append-only';
end;
$$;

drop trigger if exists audit_events_no_update on audit_events;
create trigger audit_events_no_update
before update on audit_events
for each row execute function deny_audit_event_mutation();

drop trigger if exists audit_events_no_delete on audit_events;
create trigger audit_events_no_delete
before delete on audit_events
for each row execute function deny_audit_event_mutation();

alter table runs enable row level security;
alter table approvals enable row level security;
alter table evidence enable row level security;
alter table tool_invocations enable row level security;
alter table probe_results enable row level security;
alter table action_artifacts enable row level security;
alter table workspaces enable row level security;
alter table release_initiatives enable row level security;
alter table connector_events enable row level security;
alter table audit_events enable row level security;
alter table audit_anchor_outbox enable row level security;

revoke all on runs, approvals, evidence, tool_invocations, probe_results, action_artifacts, workspaces, release_initiatives, connector_events, audit_events, audit_anchor_outbox from anon, authenticated;
