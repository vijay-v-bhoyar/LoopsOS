from __future__ import annotations


REQUIRED_POSTGRES_TABLES = (
    "action_artifacts",
    "approvals",
    "audit_anchor_outbox",
    "audit_events",
    "connector_events",
    "evidence",
    "execution_jobs",
    "kill_switches",
    "operational_signals",
    "probe_results",
    "release_initiatives",
    "request_rate_limits",
    "runs",
    "tool_invocations",
    "workspaces",
)
REQUIRED_AUDIT_TRIGGERS = {"audit_events_no_delete", "audit_events_no_update"}
