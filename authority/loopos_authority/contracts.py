from __future__ import annotations


REQUIRED_POSTGRES_TABLES = (
    "action_artifacts",
    "approvals",
    "audit_anchor_outbox",
    "audit_anchor_control",
    "audit_anchor_attempts",
    "audit_events",
    "connector_events",
    "effect_budget_accounts",
    "effect_budget_reservations",
    "effect_budget_events",
    "effect_budget_policy",
    "evidence",
    "execution_jobs",
    "kill_switches",
    "operational_signals",
    "probe_results",
    "release_initiatives",
    "release_policy_control",
    "request_rate_limits",
    "runs",
    "sessions",
    "tool_invocations",
    "workspaces",
)
REQUIRED_AUDIT_TRIGGERS = {"audit_events_no_delete", "audit_events_no_update"}
REQUIRED_RELEASE_POLICY_TRIGGERS = {
    "release_policy_control_monotonic",
    "release_policy_control_no_delete",
    "release_policy_control_no_truncate",
}
