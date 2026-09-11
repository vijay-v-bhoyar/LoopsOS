import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md"
EXTERNAL_STANDARD = Path("C:/Users/vijay/Downloads/production-grade-continuous-improvement-loop.md")
VENDORED_STANDARD = ROOT / "standards" / "production-grade-continuous-improvement-loop.md"


CATEGORY_RE = re.compile(r"^# (\d+)\. (.+)$")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
FIELD_RE = re.compile(
    r"\*\*Trigger:\*\*\s*(.*?)\s*\*\*Run:\*\*\s*(.*?)\s*\*\*Output:\*\*\s*(.*)",
    re.DOTALL,
)
CONTROL_RE = re.compile(r"^\|\s*(LC-\d{3})\s*\|\s*(.+?)\s*\|\s*(R[0-4])\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
CONTROL_SECTION_RE = re.compile(r"^## ([A-M])\. (.+)$")


def clean(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slugify(value: str) -> str:
    value = value.lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def split_definition(value: str) -> dict[str, str]:
    match = FIELD_RE.search(value)
    if not match:
        return {"trigger": "", "run": clean(value), "output": ""}
    return {
        "trigger": clean(match.group(1)),
        "run": clean(match.group(2)),
        "output": clean(match.group(3)),
    }


def infer_risk_tier(loop: dict[str, Any]) -> str:
    category = loop["category_name"].lower()
    name = loop["name"].lower()
    if "catastrophic" in name or "critical" in name:
        return "R4"
    high_terms = [
        "security",
        "privacy",
        "compliance",
        "agent",
        "autonomy",
        "credential",
        "access",
        "forensic",
        "cryptography",
        "quantum",
        "supply-chain",
        "supply chain",
    ]
    if any(term in category or term in name for term in high_terms):
        return "R3"
    moderate_terms = ["release", "deployment", "operations", "reliability", "data", "database", "ai"]
    if any(term in category or term in name for term in moderate_terms):
        return "R2"
    return "R1"


def parse_loops() -> list[dict[str, Any]]:
    loops: list[dict[str, Any]] = []
    category_number = None
    category_name = None

    for raw_line in FRAMEWORK.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        category_match = CATEGORY_RE.match(line)
        if category_match:
            category_number = int(category_match.group(1))
            category_name = clean(category_match.group(2))
            continue

        row_match = ROW_RE.match(line)
        if not row_match or category_number is None or category_name is None:
            continue

        number = int(row_match.group(1))
        name = clean(row_match.group(2))
        definition = row_match.group(3).strip()
        cadence = clean(row_match.group(4))
        parts = split_definition(definition)
        loop_id = f"loop-{number:03d}-{slugify(name)}"
        loops.append(
            {
                "loop_id": loop_id,
                "number": number,
                "name": name,
                "slug": slugify(name),
                "category_number": category_number,
                "category_name": category_name,
                "category_slug": slugify(category_name),
                "trigger": parts["trigger"],
                "run": parts["run"],
                "output": parts["output"],
                "cadence": cadence,
            }
        )

    for loop in loops:
        loop["baseline_risk_tier"] = infer_risk_tier(loop)
        loop["markdown_path"] = (
            f"loops/{loop['category_number']:02d}-{loop['category_slug']}/"
            f"{loop['number']:03d}-{loop['slug']}.md"
        )
        loop["descriptor_path"] = f"runtime/loop-descriptors/{loop['number']:03d}-{loop['slug']}.yaml"

    return loops


def parse_controls(standard_text: str) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    current_section = None
    in_checklist = False

    for raw_line in standard_text.splitlines():
        line = raw_line.strip()
        if line == "# Complete Risk-Tiered Control Checklist":
            in_checklist = True
            continue
        if line.startswith("## 36. "):
            break
        if not in_checklist:
            continue

        section_match = CONTROL_SECTION_RE.match(line)
        if section_match:
            current_section = {
                "key": section_match.group(1),
                "name": clean(section_match.group(2)),
            }
            continue

        control_match = CONTROL_RE.match(line)
        if control_match and current_section:
            proof_text = clean(control_match.group(5))
            proof_type = proof_text.split(":", 1)[0].strip()
            controls.append(
                {
                    "control_id": control_match.group(1),
                    "control_name": clean(control_match.group(2)),
                    "section_key": current_section["key"],
                    "section_name": current_section["name"],
                    "minimum_risk_tier": control_match.group(3),
                    "applies_when": clean(control_match.group(4)),
                    "minimum_proof": proof_text,
                    "proof_required": proof_type,
                }
            )

    return controls


def tier_value(tier: str) -> int:
    return int(tier[1])


def loop_control_ids(loop: dict[str, Any], controls: list[dict[str, Any]]) -> list[str]:
    tier = loop["baseline_risk_tier"]
    ids = [c["control_id"] for c in controls if tier_value(c["minimum_risk_tier"]) <= tier_value(tier)]
    category = loop["category_name"].lower()
    name = loop["name"].lower()

    category_extra = {
        "ai": ["LC-076", "LC-077", "LC-078", "LC-097", "LC-105"],
        "agent": ["LC-046", "LC-052", "LC-055", "LC-056", "LC-061", "LC-064", "LC-087"],
        "security": ["LC-081", "LC-087", "LC-089", "LC-090"],
        "privacy": ["LC-082", "LC-083", "LC-089"],
        "release": ["LC-069", "LC-072", "LC-079", "LC-080", "LC-086"],
        "deployment": ["LC-069", "LC-072", "LC-079", "LC-080", "LC-086"],
        "data": ["LC-076", "LC-082", "LC-086", "LC-088", "LC-089"],
    }

    for term, extra_ids in category_extra.items():
        if term in category or term in name:
            ids.extend(extra_ids)

    return sorted(set(ids))


def owner_ref_for(loop: dict[str, Any]) -> str:
    return f"owner-category-{loop['category_number']:02d}"


def evidence_ref_for(loop: dict[str, Any]) -> str:
    return f"evidence-category-{loop['category_number']:02d}"


def tools_for(loop: dict[str, Any]) -> list[str]:
    tools = [
        "evidence_reader",
        "source_freshness_checker",
        "owner_registry_lookup",
        "risk_tier_calculator",
        "control_applicability_resolver",
        "probe_runner",
        "state_transition_writer",
        "result_envelope_writer",
        "verdict_writer",
        "notification_router",
        "corpus_validator",
    ]
    category = loop["category_name"].lower()
    name = loop["name"].lower()
    if "agent" in category or "agent" in name:
        tools.extend(["agent_memory_writer", "guardrail_evaluator"])
    if "security" in category or "privacy" in category or "compliance" in name:
        tools.extend(["authorization_probe_runner", "forensic_log_reader"])
    if "deployment" in name or "release" in name or "devops" in category:
        tools.extend(["deployment_smoke_runner", "rollback_drill_runner"])
    if "ai" in category or "model" in name or "rag" in name:
        tools.extend(["evaluation_runner", "drift_monitor"])
    return sorted(set(tools))


def is_enterprise_high_risk(loop: dict[str, Any]) -> bool:
    return loop["number"] in [*range(66, 81), 89, *range(100, 105)]


def build_loop_descriptor(loop: dict[str, Any], control_ids: list[str]) -> dict[str, Any]:
    action_classes = ["read_only", "reversible_write"]
    if is_enterprise_high_risk(loop):
        action_classes.extend(["external_effect", "security_privileged", "cross_tenant"])
    return {
        "loop_id": loop["loop_id"],
        "name": loop["name"],
        "version": "1.0",
        "status": "DRAFT",
        "category": {
            "number": loop["category_number"],
            "name": loop["category_name"],
        },
        "refs": {
            "markdown": loop["markdown_path"],
            "control_catalog": "controls/CONTROL_CATALOG.yaml",
            "state_machine": "runtime/state_machine.yaml",
            "loop_graph": "runtime/loop_graph.yaml",
            "owner_registry": "owners/OWNER_REGISTRY.yaml",
            "evidence_registry": "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
        },
        "purpose": {
            "outcome_to_improve": loop["output"],
            "trigger": loop["trigger"],
            "run_summary": loop["run"],
            "minimum_cadence": loop["cadence"],
        },
        "risk": {
            "baseline_tier": loop["baseline_risk_tier"],
            "effective_tier_rule": "highest_applicable_dimension",
            "escalation_dimensions": [
                "environment",
                "data_sensitivity",
                "external_effect",
                "reversibility",
                "blast_radius",
                "autonomy",
                "security_privilege",
                "regulatory_impact",
                "maximum_loss",
            ],
        },
        "authority": {
            "policy_owner_ref": owner_ref_for(loop),
            "gate_owner_ref": owner_ref_for(loop),
            "executor_ref": f"executor-{loop['loop_id']}",
            "validator_ref": f"validator-{loop['loop_id']}",
            "risk_owner_ref": owner_ref_for(loop),
        },
        "evidence": {
            "primary_location_ref": evidence_ref_for(loop),
            "freshness_policy_ref": f"freshness-{loop['baseline_risk_tier']}",
            "retention_policy_ref": f"retention-{loop['baseline_risk_tier']}",
        },
        "controls": {
            "applicability_profile_ref": f"profile-{loop['loop_id']}",
            "applicable_control_ids": control_ids,
        },
        "tools": tools_for(loop),
        "golden_tasks_ref": f"golden-{loop['loop_id']}",
        "metric_pack_ref": f"metrics-{loop['loop_id']}",
        "runtime_layers": {
            "orchestration": "langgraph_compatible_state_graph",
            "durable_execution": "restate_default_temporal_compatible",
            "policy": "opa_compatible_policy_decision_point",
            "guardrails": "external_guardrail_adapter",
            "observability": "langfuse_or_phoenix_trace_adapter",
        },
        "tool_policy": {
            "allowed_action_classes": action_classes,
            "privileged_action_rule": "R3/R4, external-effect, irreversible, financial, security-privileged, and cross-tenant actions require deterministic authorization and payload-bound approval.",
            "policy_decision_ref_required": True,
        },
        "sandbox": {
            "profile_ref": "sandbox-e2b-firecracker-production" if is_enterprise_high_risk(loop) else "sandbox-governed-standard",
            "filesystem": "read_only_default",
            "privilege": "non_privileged",
            "metadata_endpoint_blocked": True,
        },
        "egress": {
            "default_policy": "deny",
            "allowed_hosts_ref": "runtime/architecture_stack.yaml#required_layers.sandboxing",
            "private_network_block": True,
        },
        "identity": {
            "workload_identity_required": True,
            "tenant_boundary": "required",
            "authorization_model": "RBAC_ABAC",
        },
        "secrets": {
            "source": "KMS",
            "injection": "short_lived_runtime",
            "trace_redaction_required": True,
        },
        "observability": {
            "trace_sink_ref": "langfuse_or_phoenix_trace",
            "audit_sink_ref": "worm-siem-required" if loop["number"] == 89 else "tenant-audit-chain-plus-siem-export",
            "redaction_proof_required": True,
        },
        "durability": {
            "workflow_adapter_ref": "restate_default_temporal_compatible",
            "idempotency_scope": "tenant_workflow_tool_payload",
            "retry_budget": {
                "max_attempts": 3,
                "retryable_failures_only": True,
                "reconciliation_before_retry": True,
            },
        },
        "recovery": {
            "mode": "bounded_retry_then_block_or_compensate",
            "reconciliation_required": True,
            "compensation_required_for_external_effect": True,
        },
        "kill_switch": {
            "scopes": ["tenant", "agent", "tool", "global"],
            "activation_record_required": True,
        },
    }


def build_loop_graph(loops: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {loop["name"]: loop for loop in loops}
    edges: list[dict[str, Any]] = []

    def add(source_name: str, target_name: str, event: str, evidence: str, priority: str = "medium") -> None:
        if source_name in by_name and target_name in by_name:
            edges.append(
                {
                    "from": by_name[source_name]["loop_id"],
                    "to": by_name[target_name]["loop_id"],
                    "event": event,
                    "evidence": evidence,
                    "priority": priority,
                }
            )

    for loop in loops:
        add(loop["name"], "Backlog Refinement Loop", "improvement_action_required", "loop_record")
        add(loop["name"], "Risk Management Loop", "material_risk_identified", "risk_signal")

    add("Tool Execution Validation Loop", "Agent State Consistency and Idempotency Loop", "partial_effect_detected", "tool_execution_record", "high")
    add("Tool Execution Validation Loop", "Agent Failure Recovery Loop", "tool_execution_failed", "tool_error_record", "high")
    add("Agent Failure Recovery Loop", "Model Portability and Exit Loop", "repeated_provider_failure", "failure_recovery_trend")
    add("Hallucination Reduction Loop", "Evaluation Dataset Evolution Loop", "new_supported_failure_case", "hallucination_case")
    add("AI Incident Response Loop", "AI Red-Team Evolution Loop", "ai_security_incident", "incident_report", "high")
    add("Deployment Validation Loop", "Rollback, Backup and Recovery Loop", "deployment_validation_failed", "deployment_evidence", "high")
    add("Incident Management Loop", "Problem Management Loop", "repeat_incident_or_systemic_cause", "incident_timeline", "high")
    add("Privacy Engineering and Data Protection Loop", "Compliance Evidence Loop", "privacy_control_evidence_required", "privacy_assessment")
    add("Software Supply-Chain and Build Integrity Loop", "Vulnerability Management Loop", "supply_chain_vulnerability", "sbom_or_scan_result", "high")
    add("Agent Memory Loop", "Privacy Engineering and Data Protection Loop", "sensitive_memory_operation", "memory_operation_record", "high")

    seen = set()
    unique_edges = []
    for edge in edges:
        key = (edge["from"], edge["to"], edge["event"])
        if edge["from"] == edge["to"] or key in seen:
            continue
        seen.add(key)
        unique_edges.append(edge)

    return {
        "version": "1.0",
        "cycle_controls": {
            "correlation_id_required": True,
            "max_fan_out_per_event": 5,
            "duplicate_suppression": "deduplication_key per loop_id, event, asset, and proof scope",
            "loop_storm_breaker": "block and escalate when one correlation_id triggers more than 12 loop executions",
            "oscillation_escalation": "escalate when the same decision reverses more than twice inside the review window",
        },
        "edges": unique_edges,
    }


def build_state_machine() -> dict[str, Any]:
    return {
        "version": "1.0",
        "invariant": "ACTION_APPLIED is never equivalent to EFFECTIVENESS_PROVEN",
        "terminal_states": ["EFFECTIVENESS_PROVEN", "EFFECTIVENESS_FAILED", "BLOCKED", "ROLLED_BACK", "PAUSED", "RETIRED"],
        "allowed_transitions": {
            "TRIGGERED": ["QUALIFIED", "INPUT_INCOMPLETE", "BLOCKED"],
            "QUALIFIED": ["OBSERVED", "INSUFFICIENT_EVIDENCE", "BLOCKED"],
            "OBSERVED": ["DIAGNOSED", "INPUT_STALE", "INPUT_CONFLICTED", "INPUT_UNTRUSTED", "BLOCKED"],
            "DIAGNOSED": ["PRIORITIZED", "INSUFFICIENT_EVIDENCE", "BLOCKED"],
            "PRIORITIZED": ["PLANNED", "PAUSED", "BLOCKED"],
            "PLANNED": ["AUTHORIZED", "BLOCKED"],
            "AUTHORIZED": ["ACTION_IN_PROGRESS", "BLOCKED"],
            "ACTION_IN_PROGRESS": ["ACTION_APPLIED", "VALIDATION_FAILED", "ROLLED_BACK", "BLOCKED"],
            "ACTION_APPLIED": ["VALIDATION_PASSED", "VALIDATION_FAILED", "ROLLED_BACK", "BLOCKED"],
            "VALIDATION_PASSED": ["PROOF_GREEN", "PROOF_FAILED", "EFFECTIVENESS_PENDING", "BLOCKED"],
            "VALIDATION_FAILED": ["PLANNED", "ROLLED_BACK", "BLOCKED"],
            "PROOF_GREEN": ["EFFECTIVENESS_PENDING", "EFFECTIVENESS_PROVEN", "BLOCKED"],
            "PROOF_FAILED": ["PLANNED", "BLOCKED", "ROLLED_BACK"],
            "EFFECTIVENESS_PENDING": ["EFFECTIVENESS_PROVEN", "EFFECTIVENESS_FAILED", "INSUFFICIENT_EVIDENCE", "BLOCKED"],
            "INSUFFICIENT_EVIDENCE": ["OBSERVED", "CONDITIONAL_ACTIVE", "BLOCKED"],
            "CONDITIONAL_ACTIVE": ["EFFECTIVENESS_PENDING", "CONDITIONAL_EXPIRED", "BLOCKED"],
            "CONDITIONAL_EXPIRED": ["BLOCKED", "PLANNED"],
        },
    }


def build_tool_contracts() -> dict[str, Any]:
    contracts = [
        ("evidence_reader", "Fetch authoritative evidence", ["source_ref", "scope"], "evidence_bundle", ["stale", "denied", "missing"], "30s", "no retry for denied", "freshness and lineage check", "escalate"),
        ("source_freshness_checker", "Validate evidence freshness", ["evidence_ref", "freshness_policy_ref"], "freshness_verdict", ["expired", "unknown_clock"], "10s", "one retry", "timestamp and source-owner check", "mark evidence stale"),
        ("owner_registry_lookup", "Resolve policy and gate authority", ["owner_ref", "control_id"], "owner_record", ["missing", "conflict"], "10s", "no retry for conflict", "one-authority rule check", "block"),
        ("risk_tier_calculator", "Calculate effective risk tier", ["loop_id", "risk_dimensions"], "risk_tier_verdict", ["missing_dimension"], "10s", "no retry", "highest applicable dimension check", "escalate"),
        ("control_applicability_resolver", "Map controls to loop execution", ["loop_id", "risk_tier"], "applicable_controls", ["missing_catalog"], "10s", "one retry", "control catalog checksum check", "block"),
        ("probe_runner", "Execute proof probe", ["probe_id", "scope"], "probe_result", ["timeout", "failed", "inconclusive"], "120s", "policy-defined", "acceptance criteria comparison", "block or conditional"),
        ("state_transition_writer", "Record lifecycle transition", ["loop_id", "execution_id", "from_state", "to_state"], "state_event", ["illegal_transition", "write_failed"], "15s", "idempotent retry", "state machine validation", "block"),
        ("result_envelope_writer", "Persist execution result", ["result_envelope"], "durable_result_ref", ["schema_invalid", "write_failed"], "15s", "idempotent retry", "schema validation", "block"),
        ("verdict_writer", "Record gate verdict", ["loop_id", "execution_id", "verdict"], "durable_verdict", ["conflict", "write_failed"], "15s", "idempotent retry", "read-after-write", "block"),
        ("notification_router", "Notify owners and downstream loops", ["event", "recipient_refs"], "notification_record", ["recipient_missing", "delivery_failed"], "30s", "retry delivery failures", "recipient scope check", "escalate"),
        ("memory_writer", "Persist approved learning", ["learning_artifact", "classification"], "memory_record", ["privacy_block", "retention_missing"], "20s", "no retry for privacy block", "privacy and retention check", "route to backlog"),
        ("corpus_validator", "Validate static loop corpus", ["repo_root"], "validation_report", ["schema_error", "missing_artifact"], "60s", "no retry", "all required checks pass", "fail closed"),
    ]
    document = {
        "version": "1.0",
        "enterprise_execution_policy": {
            "filesystem_default": "read_only",
            "privilege_default": "non_privileged",
            "network_default": "deny",
            "egress_control": "exact_host_allowlist_only",
            "blocked_networks": ["private_address_ranges", "loopback_except_explicit_dev", "link_local", "multicast", "reserved", "cloud_metadata_endpoints"],
            "credential_handling": {"source": "KMS", "injection": "short_lived_server_side", "trace_redaction_required": True},
            "response_bounds": {"json_object_only": True, "max_response_bytes_ref": "authority_settings.http_max_response_bytes"},
            "policy_decision_log_required": True,
        },
        "contracts": [
            {
                "tool": row[0],
                "purpose": row[1],
                "required_inputs": row[2],
                "expected_output": row[3],
                "failure_modes": row[4],
                "timeout": row[5],
                "retry": row[6],
                "verification_before_use": row[7],
                "fallback": row[8],
            }
            for row in contracts
        ],
    }
    document["contracts"].extend(
        [
            {
                "tool": "sandbox_profile_resolver",
                "purpose": "Select and prove the isolated execution profile for an agent or tool action",
                "required_inputs": ["loop_id", "action_class", "risk_tier", "sandbox_profile_ref"],
                "expected_output": "sandbox_profile_verdict",
                "failure_modes": ["missing_profile", "insufficient_isolation", "metadata_endpoint_reachable", "filesystem_not_read_only"],
                "timeout": "10s",
                "retry": "no retry for insufficient isolation",
                "verification_before_use": "Firecracker or gVisor profile, non-privileged runtime, read-only default filesystem, and metadata endpoint block",
                "fallback": "block",
            },
            {
                "tool": "egress_policy_checker",
                "purpose": "Authorize connector network access before any outbound request",
                "required_inputs": ["endpoint", "tenant_id", "allowed_hosts_ref", "policy_decision_ref"],
                "expected_output": "egress_verdict",
                "failure_modes": ["host_not_allowlisted", "private_network_resolution", "embedded_credentials", "non_https", "policy_denied"],
                "timeout": "5s",
                "retry": "one DNS retry only",
                "verification_before_use": "scheme, DNS, host allowlist, private IP block, and cloud metadata endpoint block",
                "fallback": "block",
            },
            {
                "tool": "credential_injection_broker",
                "purpose": "Issue scoped short-lived connector credentials without exposing secrets to model context",
                "required_inputs": ["workload_identity_ref", "tenant_id", "connector_ref", "action_class"],
                "expected_output": "scoped_credential_ref",
                "failure_modes": ["kms_unavailable", "identity_denied", "tenant_scope_conflict", "redaction_policy_missing"],
                "timeout": "10s",
                "retry": "no retry for identity_denied or tenant_scope_conflict",
                "verification_before_use": "IdP claim, RBAC/ABAC context, KMS source, TTL, and trace-redaction policy",
                "fallback": "block",
            },
            {
                "tool": "policy_decision_logger",
                "purpose": "Persist allow, deny, modify, or escalate decisions from the policy decision point",
                "required_inputs": ["policy_ref", "input_hash", "decision", "actor_ref", "tenant_id"],
                "expected_output": "policy_decision_record",
                "failure_modes": ["policy_unavailable", "schema_invalid", "write_failed"],
                "timeout": "5s",
                "retry": "idempotent retry",
                "verification_before_use": "OPA-compatible decision payload and immutable audit sink write",
                "fallback": "block",
            },
        ]
    )
    return document


def build_owner_registry(loops: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({(loop["category_number"], loop["category_name"]) for loop in loops})
    return {
        "version": "1.0",
        "status": "draft_registry_requires_named_humans_before_active_use",
        "activation_rule": "DRAFT loops may use category placeholder owners; ACTIVE loops must resolve named policy, gate, risk, executor, validator, and backup owners.",
        "owners": [
            {
                "owner_ref": f"owner-category-{number:02d}",
                "category": f"{number}. {name}",
                "policy_owner": "UNASSIGNED",
                "gate_owner": "UNASSIGNED",
                "risk_owner": "UNASSIGNED",
                "executor_owner": "UNASSIGNED",
                "validator_owner": "UNASSIGNED",
                "backup_owner": "UNASSIGNED",
                "status": "DRAFT",
            }
            for number, name in categories
        ],
    }


def build_evidence_registry(loops: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({(loop["category_number"], loop["category_name"]) for loop in loops})
    return {
        "version": "1.0",
        "locations": [
            {
                "evidence_ref": f"evidence-category-{number:02d}",
                "category": f"{number}. {name}",
                "authoritative_location": "UNASSIGNED",
                "freshness_policy": "freshness policy must be assigned before ACTIVE status",
                "retention_policy": "retention policy must be assigned before ACTIVE status",
                "access_control": "least privilege",
                "status": "DRAFT",
            }
            for number, name in categories
        ],
        "freshness_policies": {
            "freshness-R0": "best effort",
            "freshness-R1": "current within the review cadence",
            "freshness-R2": "current within the gate or observation window",
            "freshness-R3": "current and source-bound before consequential action",
            "freshness-R4": "current, independently verified, and scope-bound before action",
        },
        "retention_policies": {
            "retention-R0": "short-lived unless promoted",
            "retention-R1": "retain through review cadence",
            "retention-R2": "retain through release or operational window",
            "retention-R3": "retain for audit and incident reconstruction",
            "retention-R4": "retain for audit, forensic, and continuity requirements",
        },
    }


def build_probe_registry(loops: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "1.0",
        "enterprise_probe_types": [
            "sandbox_escape_negative_probe",
            "egress_negative_probe",
            "credential_redaction_probe",
            "policy_decision_probe",
            "tenant_isolation_probe",
            "kill_switch_probe",
        ],
        "probes": [
            {
                "probe_id": "routing-deduplication-v1",
                "adapter": "scripts/pilot_probes/routing_deduplication.py",
                "loop_ids": [loop["loop_id"] for loop in loops],
                "method": "SCENARIO_PROBE",
                "inputs": ["trigger_record", "loop_graph"],
                "acceptance": ["trigger routes to exactly one primary loop", "duplicate active handling is suppressed"],
                "evidence_output": "routing_verdict.json",
            },
            {
                "probe_id": "authority-resolution-v1",
                "adapter": "scripts/pilot_probes/authority_resolution.py",
                "loop_ids": [loop["loop_id"] for loop in loops],
                "method": "AUTHORIZATION_PROBE",
                "inputs": ["loop_descriptor", "owner_registry"],
                "acceptance": ["policy owner resolves", "gate owner resolves", "owner conflict blocks progression"],
                "evidence_output": "authority_verdict.json",
            },
            {
                "probe_id": "state-transition-v1",
                "adapter": "scripts/pilot_probes/state_transition.py",
                "loop_ids": [loop["loop_id"] for loop in loops],
                "method": "BOUNDARY_PROBE",
                "inputs": ["state_machine", "state_event"],
                "acceptance": ["allowed transitions pass", "illegal transitions fail closed"],
                "evidence_output": "state_transition_verdict.json",
            },
            {
                "probe_id": "proof-scope-freshness-v1",
                "adapter": "scripts/pilot_probes/proof_scope_freshness.py",
                "loop_ids": [loop["loop_id"] for loop in loops],
                "method": "EVIDENCE_AUDIT",
                "inputs": ["proof_record", "evidence_registry"],
                "acceptance": ["proof is current", "proof is scope-bound", "expired proof is rejected"],
                "evidence_output": "proof_freshness_verdict.json",
            },
            {
                "probe_id": "replay-tool-idempotency-v1",
                "adapter": "scripts/pilot_probes/replay_tool_idempotency.py",
                "loop_ids": [loop["loop_id"] for loop in loops if "tool" in loop["name"].lower() or "agent" in loop["category_name"].lower()],
                "method": "REPLAY_PROBE",
                "inputs": ["operation_id", "tool_call_record"],
                "acceptance": ["repeated operation produces one logical effect", "duplicate side effects are absent"],
                "evidence_output": "idempotency_verdict.json",
            },
        ],
    }


def build_golden_tasks(loops: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = []
    for loop in loops:
        base = {
            "loop_id": loop["loop_id"],
            "golden_task_ref": f"golden-{loop['loop_id']}",
            "tasks": [
                {
                    "task_id": f"{loop['loop_id']}-happy-path",
                    "type": "happy_path",
                    "scenario": f"{loop['name']} receives sufficient fresh evidence and the correct owner is resolved.",
                    "expected": "QUALIFIED through PROOF_GREEN or EFFECTIVENESS_PENDING with evidence references.",
                },
                {
                    "task_id": f"{loop['loop_id']}-missing-proof",
                    "type": "failure_path",
                    "scenario": f"{loop['name']} has declared or implemented control but no current executed proof.",
                    "expected": "MISSING_PROOF or PROOF_FAILED blocks pass verdict.",
                },
                {
                    "task_id": f"{loop['loop_id']}-conditional-expiry",
                    "type": "conditional_path",
                    "scenario": f"{loop['name']} receives temporary approval with missing evidence and compensating controls.",
                    "expected": "CONDITIONAL_ACTIVE expires to CONDITIONAL_EXPIRED unless proof is produced.",
                },
            ],
        }
        if tier_value(loop["baseline_risk_tier"]) >= 3:
            base["tasks"].extend(
                [
                    {
                        "task_id": f"{loop['loop_id']}-authorization-denied",
                        "type": "authorization_denied",
                        "scenario": f"{loop['name']} is attempted by an actor without gate authority.",
                        "expected": "Unauthorized action is blocked and audited.",
                    },
                    {
                        "task_id": f"{loop['loop_id']}-adversarial-evidence",
                        "type": "adversarial",
                        "scenario": f"{loop['name']} receives stale, conflicted, or untrusted evidence.",
                        "expected": "Input quality failure blocks or escalates.",
                    },
                ]
            )
        tasks.append(base)
    return {
        "version": "1.0",
        "enterprise_task_types": [
            "authorization_denied",
            "idempotency_replay",
            "sandbox_egress_blocked",
            "credential_redaction",
            "tenant_isolation",
            "policy_denied",
            "rollback_required",
            "kill_switch_triggered",
        ],
        "enterprise_runtime_golden_tasks": [
            {
                "task_id": "agent-tool-authorization-denied",
                "type": "authorization_denied",
                "loop_ids": ["loop-069-tool-execution-validation-loop", "loop-079-agent-guardrail-loop"],
                "scenario": "A privileged external-effect tool call lacks a valid policy decision or payload-bound approval.",
                "expected": "The run remains blocked or awaiting approval; no external side effect is attempted.",
            },
            {
                "task_id": "agent-idempotency-replay",
                "type": "idempotency_replay",
                "loop_ids": ["loop-073-agent-state-consistency-and-idempotency-loop"],
                "scenario": "A retry uses the same tenant, workflow, tool, idempotency key, and payload.",
                "expected": "The prior invocation result is replayed; conflicting payload reuse is rejected.",
            },
            {
                "task_id": "agent-sandbox-egress-blocked",
                "type": "sandbox_egress_blocked",
                "loop_ids": ["loop-069-tool-execution-validation-loop", "loop-078-model-and-agent-interaction-security-loop"],
                "scenario": "A tool attempts non-HTTPS, private-network, metadata-endpoint, or unallowlisted outbound access.",
                "expected": "Egress is denied before execution and the policy decision is recorded.",
            },
            {
                "task_id": "agent-credential-redaction",
                "type": "credential_redaction",
                "loop_ids": ["loop-080-agent-identity-and-credential-governance-loop", "loop-089-audit-logging-and-forensic-readiness-loop"],
                "scenario": "A connector action receives a short-lived credential from KMS-backed injection.",
                "expected": "The credential never appears in prompts, traces, evidence payloads, or audit event bodies.",
            },
            {
                "task_id": "agent-tenant-isolation",
                "type": "tenant_isolation",
                "loop_ids": ["loop-075-multi-agent-coordination-loop", "loop-080-agent-identity-and-credential-governance-loop"],
                "scenario": "A user or agent from one tenant requests another tenant's run, evidence, connector event, or proof pack.",
                "expected": "The request is denied or returns not found, with no cross-tenant data disclosure.",
            },
            {
                "task_id": "agent-policy-denied",
                "type": "policy_denied",
                "loop_ids": ["loop-079-agent-guardrail-loop", "loop-102-autonomy-boundary-review-loop"],
                "scenario": "OPA-compatible policy returns deny for action class, role, tenant, environment, or data class.",
                "expected": "The action is blocked and an immutable policy decision record is available.",
            },
            {
                "task_id": "agent-rollback-required",
                "type": "rollback_required",
                "loop_ids": ["loop-074-agent-failure-recovery-loop", "loop-100-human-oversight-approval-and-calibration-loop"],
                "scenario": "An external-effect action is submitted without a rollback or compensating action contract.",
                "expected": "The plan is rejected before dispatch.",
            },
            {
                "task_id": "agent-kill-switch-triggered",
                "type": "kill_switch_triggered",
                "loop_ids": ["loop-072-agent-resource-budget-and-rate-limit-control-loop", "loop-097-catastrophic-failure-and-containment-loop"],
                "scenario": "Tenant, agent, tool, or global kill switch is activated.",
                "expected": "New work is denied, queued work is paused or blocked, and activation is auditable.",
            },
        ],
        "golden_tasks": tasks,
    }


def metric_name(loop: dict[str, Any]) -> str:
    return f"{loop['slug'].replace('-', '_')}_effectiveness_rate"


def build_metric_packs(loops: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "1.0",
        "metric_packs": [
            {
                "loop_id": loop["loop_id"],
                "metric_pack_ref": f"metrics-{loop['loop_id']}",
                "primary_metric": {
                    "name": metric_name(loop),
                    "formula": "proven_successful_executions / qualified_executions",
                    "target_value": "to_be_set_by_policy_owner",
                    "observation_window": "cadence-bound",
                },
                "guardrails": [
                    "no_unmapped_authority",
                    "no_expired_proof_passes",
                    "no_illegal_state_transition",
                    "no_unowned_action",
                ],
                "health_metrics": [
                    "trigger_volume",
                    "qualification_rate",
                    "proof_freshness_rate",
                    "repeat_gap_rate",
                    "cost_per_execution",
                    "mean_time_to_validated_result",
                ],
            }
            for loop in loops
        ],
    }


def primary_user_for(loop: dict[str, Any]) -> str:
    users = {
        1: "Product strategy owner",
        2: "Delivery or product operations lead",
        3: "Architecture or design authority",
        4: "Engineering quality lead",
        5: "Quality engineering lead",
        6: "Release or platform operations lead",
        7: "SRE or service owner",
        8: "Data platform or governance owner",
        9: "AI evaluation and safety owner",
        10: "Agent platform owner",
        11: "Security, privacy, or compliance owner",
        12: "Strategic resilience owner",
        13: "Enterprise governance and adoption lead",
    }
    return users.get(loop["category_number"], "Loop policy owner")


def automation_mode_for(loop: dict[str, Any]) -> str:
    tier = loop["baseline_risk_tier"]
    if tier in {"R0", "R1"}:
        return "agent-assisted execution with owner review before standardization"
    if tier == "R2":
        return "tool-bounded execution with named owner approval"
    if tier == "R3":
        return "human-authorized execution with independent validation and audit logging"
    return "human-led execution; agents may prepare evidence and plans only until explicit emergency authorization"


def build_practical_operation_cards(loops: list[dict[str, Any]]) -> dict[str, Any]:
    cards = []
    for loop in loops:
        cards.append(
            {
                "operation_card_id": f"card-{loop['loop_id']}",
                "loop_id": loop["loop_id"],
                "name": loop["name"],
                "primary_user": primary_user_for(loop),
                "automation_mode": automation_mode_for(loop),
                "when_to_run": {
                    "trigger": loop["trigger"],
                    "minimum_cadence": loop["cadence"],
                    "do_not_run_if": [
                        "policy owner or gate owner is unresolved for ACTIVE use",
                        "authoritative evidence location is unresolved for ACTIVE use",
                        "effective risk tier is R3 or R4 and authorization is missing",
                        "same correlation_id has tripped the loop storm breaker",
                    ],
                },
                "first_10_minutes": [
                    "create execution_id and correlation_id",
                    "open the loop descriptor, owner registry, evidence registry, and metric pack",
                    "qualify scope, asset, risk tier, owner, and minimum data",
                    "collect current evidence from the primary evidence location",
                    "record the initial state transition before planning action",
                ],
                "evidence_to_collect": [
                    "trigger record and source",
                    "current-state observation with timestamp",
                    "gap or diagnosis record",
                    "control applicability profile",
                    "authorization verdict",
                    "action or change record",
                    "validation result",
                    "proof and effectiveness observation",
                ],
                "proof_to_run": [
                    f"golden-{loop['loop_id']}",
                    "routing-deduplication-v1",
                    "authority-resolution-v1",
                    "evidence-freshness-v1",
                    "state-machine-v1",
                    "control-coverage-v1",
                ],
                "success_criteria": [
                    loop["output"],
                    f"primary metric {metric_name(loop)} meets the owner-defined target",
                    "no illegal state transition, expired proof, unresolved authority, or stale evidence remains",
                ],
                "handoff_rules": [
                    "send improvement work to Backlog Refinement when action is outside the current loop scope",
                    "send material risk to Risk Management before execution",
                    "send R3/R4, destructive, external, privacy, security, or compliance actions to a named human gate owner",
                    "send repeated validation failure to Problem Management or the relevant prevention loop",
                ],
                "minimum_viable_record": [
                    "loop_id",
                    "loop_version",
                    "execution_id",
                    "correlation_id",
                    "risk_tier",
                    "authority",
                    "trigger",
                    "scope",
                    "state",
                    "evidence",
                    "verdict",
                    "timestamp",
                ],
                "common_failure_modes": [
                    "stale or missing evidence",
                    "owner conflict",
                    "action applied without proof",
                    "temporary exception not expired or retired",
                    "fix validated locally but not monitored for effectiveness",
                ],
            }
        )
    return {"version": "1.0", "operation_cards": cards}


def build_pilot_playbooks(loops: list[dict[str, Any]]) -> dict[str, Any]:
    loop_by_name = {loop["name"]: loop for loop in loops}

    def ids(names: list[str]) -> list[str]:
        return [loop_by_name[name]["loop_id"] for name in names if name in loop_by_name]

    specs = [
        {
            "playbook_id": "pilot-sdlc-governance-os",
            "title": "Validator-backed SDLC governance operating system",
            "impact_rank": 1,
            "effort_saving": "eliminates repeated manual status chasing across requirements, review, release, deployment, and production evidence",
            "loops": ids(
                [
                    "Requirements Quality Loop",
                    "Requirements Change Control Loop",
                    "Requirements Traceability Loop",
                    "Design Review Loop",
                    "Architecture Fitness and Future Compatibility Loop",
                    "Code Quality Loop",
                    "Pull Request Review Loop",
                    "CI Pipeline Loop",
                    "Release Readiness Loop",
                    "Deployment Validation Loop",
                    "Production Health Loop",
                    "Retrospective Improvement Loop",
                ]
            ),
            "pilot_scope": "one product, one release train, one evidence store",
            "setup": [
                "assign category owners for product, delivery, architecture, engineering, quality, release, and operations",
                "map requirement, test, release, deployment, and production evidence locations",
                "choose three release-blocking controls from the control catalog",
            ],
        },
        {
            "playbook_id": "pilot-release-command-center",
            "title": "Evidence-backed release and deployment command center",
            "impact_rank": 2,
            "effort_saving": "replaces release meetings and manual gate collection with a current proof packet",
            "loops": ids(
                [
                    "Requirements Traceability Loop",
                    "Regression Testing Loop",
                    "Performance Testing Loop",
                    "Secure SDLC Loop",
                    "Release Readiness Loop",
                    "Operational Readiness and Runbook Loop",
                    "Deployment Validation Loop",
                    "Environment Drift Loop",
                    "Rollback, Backup and Recovery Loop",
                    "Observability Improvement Loop",
                    "Incident Management Loop",
                ]
            ),
            "pilot_scope": "one critical service and one normal release",
            "setup": [
                "declare release evidence packet fields",
                "connect CI, deployment, rollback, and observability evidence",
                "define ship, hold, conditional ship, and rollback verdicts",
            ],
        },
        {
            "playbook_id": "pilot-agentic-action-safety-plane",
            "title": "Agentic action safety control plane",
            "impact_rank": 3,
            "effort_saving": "prevents duplicated manual review of tool calls, delegation, memory, credentials, and recovery paths",
            "loops": ids(
                [
                    "Agent Goal Achievement Loop",
                    "Agent Planning Quality Loop",
                    "Tool Selection Loop",
                    "Tool Execution Validation Loop",
                    "Agent Context Management Loop",
                    "Agent Memory Loop",
                    "Agent Resource, Budget and Rate-Limit Control Loop",
                    "Agent State Consistency and Idempotency Loop",
                    "Agent Failure Recovery Loop",
                    "Multi-Agent Coordination Loop",
                    "Agent Delegation and Accountability Loop",
                    "Agent Guardrail Loop",
                    "Agent Identity and Credential Governance Loop",
                    "Access Governance Loop",
                    "Audit Logging and Forensic Readiness Loop",
                ]
            ),
            "pilot_scope": "one agent, three approved tools, one non-production workspace",
            "setup": [
                "register tool contracts and idempotency rules",
                "define memory write classes and retention",
                "require authority checks for external, destructive, or privileged actions",
            ],
        },
        {
            "playbook_id": "pilot-ai-lifecycle-evaluation-flywheel",
            "title": "AI model lifecycle and evaluation flywheel",
            "impact_rank": 4,
            "effort_saving": "turns repeated prompt, model, RAG, safety, and drift review into reusable evidence and golden tasks",
            "loops": ids(
                [
                    "AI Use-Case Validation Loop",
                    "Prompt Engineering Loop",
                    "Model Evaluation and Benchmarking Loop",
                    "RAG Quality Loop",
                    "AI Safety and Responsible AI Loop",
                    "Hallucination Reduction Loop",
                    "Model and Data Drift Monitoring Loop",
                    "AI Feedback Learning Loop",
                    "Evaluation Dataset Evolution Loop",
                    "Model Lifecycle and Upgrade Safety Loop",
                    "Model Portability and Exit Loop",
                    "Frontier Model Advancement Loop",
                ]
            ),
            "pilot_scope": "one AI feature, one eval dataset, one model upgrade decision",
            "setup": [
                "baseline model, prompt, retrieval, and safety evidence",
                "capture failed cases as candidate golden tasks",
                "define promote, rollback, and monitor verdicts",
            ],
        },
        {
            "playbook_id": "pilot-compliance-evidence-autopackager",
            "title": "Audit-ready compliance evidence autopackager",
            "impact_rank": 5,
            "effort_saving": "removes repeated audit preparation by continuously mapping controls to evidence and owners",
            "loops": ids(
                [
                    "Secure SDLC Loop",
                    "Privacy Engineering and Data Protection Loop",
                    "Audit Logging and Forensic Readiness Loop",
                    "Compliance Evidence Loop",
                    "Legal, Regulatory and Standards Watch Loop",
                    "Vendor and Third-Party Risk and SLA Loop",
                    "IP, Copyright and License Compliance Loop",
                    "Access Governance Loop",
                    "Software Supply-Chain and Build Integrity Loop",
                    "AI Supply-Chain Security Loop",
                ]
            ),
            "pilot_scope": "one audit domain and one evidence location per control family",
            "setup": [
                "assign named evidence stewards",
                "map control catalog entries to authoritative systems",
                "define freshness and retention policies before ACTIVE status",
            ],
        },
        {
            "playbook_id": "pilot-incident-prevention-flywheel",
            "title": "Incident-to-prevention learning flywheel",
            "impact_rank": 6,
            "effort_saving": "converts incident review, bug fixing, alert tuning, regression creation, and backlog follow-up into one proof chain",
            "loops": ids(
                [
                    "Observability Improvement Loop",
                    "Incident Management Loop",
                    "AI Incident Response Loop",
                    "Problem Management Loop",
                    "Defect Management Loop",
                    "Regression Testing Loop",
                    "Chaos Engineering and Resilience Testing Loop",
                    "Backlog Refinement Loop",
                    "Risk Management Loop",
                    "Retrospective Improvement Loop",
                ]
            ),
            "pilot_scope": "three recent incidents or defects from one service",
            "setup": [
                "link incident timelines to failed controls and missing probes",
                "add one regression or chaos proof per repeat failure",
                "route preventive work through backlog and risk loops",
            ],
        },
    ]

    for spec in specs:
        spec["operating_steps"] = [
            "trigger the primary loop from a real work item",
            "qualify scope, authority, evidence, and risk tier",
            "collect proof from authoritative systems",
            "diagnose gaps and route dependent loops through the graph",
            "authorize only the minimum bounded action",
            "validate immediate correctness",
            "monitor effectiveness through the defined observation window",
            "standardize the learning into controls, probes, golden tasks, or runbooks",
        ]
        spec["proof_bundle"] = [
            "result envelope",
            "state transition log",
            "control applicability profile",
            "evidence freshness verdict",
            "authorization verdict",
            "validation result",
            "effectiveness metric snapshot",
        ]
        spec["exit_criteria"] = [
            "all selected loops have named owners",
            "all selected loops have authoritative evidence locations",
            "golden task pass rate is recorded",
            "at least one repeated manual task is replaced by a governed proof packet",
        ]
    return {"version": "1.0", "playbooks": specs}


def build_human_handoffs() -> dict[str, Any]:
    return {
        "version": "1.0",
        "principle": "handoff before irreversible consequence, privileged access, external effect, or uncertain proof",
        "handoff_rules": [
            {
                "handoff_id": "missing_authority",
                "trigger": "policy owner, gate owner, risk owner, executor, validator, or backup owner cannot be resolved",
                "required_human": "category policy owner",
                "allowed_state": "BLOCKED",
            },
            {
                "handoff_id": "missing_evidence_source",
                "trigger": "authoritative evidence location is UNASSIGNED, stale, conflicted, or inaccessible",
                "required_human": "evidence steward",
                "allowed_state": "INSUFFICIENT_EVIDENCE",
            },
            {
                "handoff_id": "r3_or_r4_action",
                "trigger": "effective risk tier is R3 or R4 before execution",
                "required_human": "named gate owner and risk owner",
                "allowed_state": "PLANNED",
            },
            {
                "handoff_id": "external_side_effect_or_destructive_action",
                "trigger": "action changes production, customer-visible behavior, money, legal posture, identity, credentials, or data deletion",
                "required_human": "gate owner with separation of duties",
                "allowed_state": "PLANNED",
            },
            {
                "handoff_id": "conditional_expired",
                "trigger": "temporary approval reaches expiry without proof",
                "required_human": "gate owner",
                "allowed_state": "CONDITIONAL_EXPIRED",
            },
            {
                "handoff_id": "repeated_oscillation",
                "trigger": "same decision reverses more than twice inside the review window",
                "required_human": "risk owner",
                "allowed_state": "BLOCKED",
            },
            {
                "handoff_id": "security_privacy_or_compliance_failure",
                "trigger": "validation, probe, or evidence indicates security, privacy, compliance, forensic, or supply-chain failure",
                "required_human": "security, privacy, or compliance owner",
                "allowed_state": "BLOCKED",
            },
            {
                "handoff_id": "tool_or_probe_inconclusive_after_retry",
                "trigger": "tool or probe remains inconclusive after its contract retry policy",
                "required_human": "validator owner",
                "allowed_state": "PROOF_FAILED",
            },
            {
                "handoff_id": "owner_conflict_or_separation_of_duties",
                "trigger": "same actor attempts incompatible requester, executor, validator, or approver roles",
                "required_human": "policy owner",
                "allowed_state": "BLOCKED",
            },
            {
                "handoff_id": "sensitive_memory_or_learning_write",
                "trigger": "learning artifact may contain personal, confidential, credential, regulated, or customer data",
                "required_human": "privacy or data governance owner",
                "allowed_state": "PLANNED",
            },
        ],
    }


def build_observability_plan() -> dict[str, Any]:
    return {
        "version": "1.0",
        "purpose": "make each loop execution explainable, auditable, comparable, and improvable",
        "required_event_fields": [
            "timestamp",
            "loop_id",
            "loop_version",
            "execution_id",
            "correlation_id",
            "trigger_type",
            "asset_scope",
            "risk_tier",
            "state_from",
            "state_to",
            "authority_ref",
            "evidence_refs",
            "controls_evaluated",
            "tools_called",
            "probe_ids",
            "proof_state",
            "verdict",
            "failure_reason",
            "handoff_id",
            "latency_ms",
            "cost_units",
            "retry_count",
            "standard_hash",
            "policy_decision_ref",
            "sandbox_profile_ref",
            "egress_policy_ref",
            "workload_identity_ref",
            "credential_redaction_proof_ref",
            "trace_redaction_proof_ref",
            "worm_siem_event_ref",
        ],
        "event_taxonomy": [
            "trigger_received",
            "qualification_completed",
            "evidence_collected",
            "diagnosis_recorded",
            "authorization_decided",
            "action_started",
            "action_applied",
            "validation_completed",
            "recovery_started",
            "result_recorded",
            "learning_standardized",
            "effectiveness_checked",
        ],
        "dashboards": [
            {
                "dashboard": "loop_operational_health",
                "questions": [
                    "which loops run most often",
                    "which loops are blocked by missing evidence or authority",
                    "which loops create the most downstream handoffs",
                    "which fixes pass validation but fail effectiveness",
                ],
            },
            {
                "dashboard": "moat_compounding",
                "questions": [
                    "which playbooks saved manual effort",
                    "which evidence packets were reused",
                    "which failure cases became golden tasks",
                    "which controls were strengthened from real incidents",
                ],
            },
        ],
        "alerts": [
            "illegal_state_transition",
            "expired_proof_used",
            "loop_storm_breaker_tripped",
            "R3_or_R4_action_without_handoff",
            "ACTIVE_loop_with_unassigned_owner_or_evidence",
            "repeated_validation_failure",
        ],
        "enterprise_evidence_requirements": [
            "worm_siem_audit_sink",
            "kms_backed_secret_source",
            "idp_issued_workload_identity",
            "opa_policy_decision_log",
            "trace_redaction_proof",
            "sandbox_escape_negative_probe",
            "egress_negative_probe",
        ],
        "minimum_retention": "retain execution, evidence, state, authorization, and proof records according to the risk-tier retention policy",
    }


def build_practicality_gaps() -> dict[str, Any]:
    return {
        "version": "1.0",
        "status": "known_activation_gaps_before_ACTIVE_use",
        "gaps": [
            {
                "gap_id": "owners-unassigned",
                "severity": "activation_blocker",
                "description": "category owner records are placeholders until named humans or accountable teams are assigned",
                "required_fix": "replace UNASSIGNED policy, gate, risk, backup, executor, and validator ownership before ACTIVE use",
            },
            {
                "gap_id": "evidence-locations-unassigned",
                "severity": "activation_blocker",
                "description": "evidence registries intentionally avoid inventing authoritative systems",
                "required_fix": "map each active category to source control, CI, ticketing, observability, GRC, data, or model-eval evidence stores",
            },
            {
                "gap_id": "metric-targets-unset",
                "severity": "pilot_blocker",
                "description": "metric packs define formulas but not organization-specific target values",
                "required_fix": "set target values and observation windows for selected pilot loops",
            },
            {
                "gap_id": "probes-are-contracts-not-integrations",
                "severity": "pilot_blocker",
                "description": "credential-free local probe adapters and fixtures exist; real CI, observability, security, and model-eval integrations remain organization-owned",
                "required_fix": "bind probe IDs to approved external adapters and retain independent live evidence for the first pilot playbook",
            },
            {
                "gap_id": "golden-tasks-need-real-fixtures",
                "severity": "pilot_blocker",
                "description": "bounded contract fixtures exist for the pilot; real examples from the operating environment are still required",
                "required_fix": "seed and approve golden tasks from recent releases, incidents, defects, AI failures, audits, and agent tool calls",
            },
        ],
    }


def build_control_applicability(loops: list[dict[str, Any]], controls: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = []
    for loop in loops:
        control_ids = loop_control_ids(loop, controls)
        profiles.append(
            {
                "profile_id": f"profile-{loop['loop_id']}",
                "loop_id": loop["loop_id"],
                "baseline_risk_tier": loop["baseline_risk_tier"],
                "control_mappings": [
                    {"control_id": "LC-001", "status": "applicable", "proof_required": "STATIC"},
                    {"control_id": "LC-046", "status": "delegated", "proof_required": "AUTHORITY_PROBE", "owner_ref": "owner_registry"},
                    {"control_id": "LC-061", "status": "conditional", "proof_required": "POLICY_DECISION_PROBE"},
                    {"control_id": "LC-084", "status": "blocked_until_proven", "proof_required": "EVIDENCE_LOCATION_PROBE"},
                    {"control_id": "LC-109", "status": "not_applicable", "proof_required": "NOT_APPLICABLE_JUSTIFICATION"},
                ],
                "applicable_control_ids": control_ids,
                "delegated_control_refs": [
                    {
                        "control_id": "LC-046",
                        "owner_ref": owner_ref_for(loop),
                        "delegation_note": "decision authority resolved by owner registry",
                    },
                    {
                        "control_id": "LC-084",
                        "owner_ref": evidence_ref_for(loop),
                        "delegation_note": "required evidence resolved by evidence registry",
                    },
                ],
            }
        )
    return {
        "version": "1.0",
        "applicability_states": ["applicable", "conditional", "delegated", "not_applicable", "blocked_until_proven"],
        "sparse_mapping_rule": "Agents and gates consume control_mappings first; applicable_control_ids remains a compatibility index for dashboards and coverage counts.",
        "profiles": profiles,
    }


def build_architecture_stack() -> dict[str, Any]:
    return {
        "version": "1.0",
        "principle": "The model may propose; deterministic systems authorize, execute, validate, and record.",
        "status": "provider_neutral_reference_stack",
        "required_layers": {
            "orchestration": {
                "interface": "langgraph_compatible_state_graph",
                "recommended_default": "LangGraph",
                "alternatives": ["Microsoft Agent Framework", "Mastra"],
                "must_provide": ["explicit_state_nodes", "cyclic_reasoning_controls", "structured_handoffs", "deterministic_gate_integration"],
            },
            "durable_execution": {
                "interface": "durable_workflow_adapter",
                "recommended_default": "Restate",
                "enterprise_history_option": "Temporal",
                "event_driven_option": "Inngest",
                "must_provide": ["idempotency_keys", "durable_checkpoints", "bounded_retries", "crash_recovery", "reconciliation_before_retry"],
            },
            "sandboxing": {
                "interface": "isolated_execution_adapter",
                "production_untrusted_code_default": "E2B_Firecracker",
                "burst_execution_option": "Modal_gVisor",
                "must_provide": ["ephemeral_non_privileged_workloads", "read_only_filesystem_by_default", "blocked_cloud_metadata_endpoints", "default_deny_network_egress", "per_tool_resource_limits"],
            },
            "policy": {
                "interface": "opa_compatible_policy_decision_point",
                "recommended_default": "Open Policy Agent",
                "must_provide": ["policy_as_code", "tool_authorization_decisions", "tenant_and_role_conditions", "explainable_allow_deny_escalate_results", "immutable_policy_decision_logs"],
            },
            "guardrails": {
                "interface": "external_guardrail_adapter",
                "recommended_defaults": ["Guardrails AI", "NeMo Guardrails"],
                "must_provide": ["input_validation", "output_validation", "content_restriction", "pii_detection_or_redaction", "prompt_injection_detection"],
            },
            "observability": {
                "interface": "llm_observability_adapter",
                "recommended_defaults": ["Langfuse", "Arize Phoenix"],
                "must_provide": ["trace_redaction", "dataset_versioning", "pre_release_eval_suites", "production_trace_sampling", "forensic_correlation_ids"],
            },
            "identity_and_secrets": {
                "interface": "enterprise_identity_and_kms_adapter",
                "recommended_default": "IdP_issued_workload_identity_with_KMS",
                "must_provide": ["short_lived_credentials", "rbac_abac_authorization_context", "tenant_isolation_claims", "server_side_secret_injection", "trace_secret_redaction"],
            },
            "cloud_deployment_profiles": {
                "local_dev": {"purpose": "developer validation only", "required_controls": ["dev_auth_explicitly_enabled", "localhost_only_connectors", "non_production_storage"]},
                "azure_governed": {"purpose": "strict enterprise governance", "recommended_services": ["Azure AI Foundry", "Microsoft Agent Framework", "Azure Key Vault", "Microsoft Entra ID"]},
                "aws_infrastructure": {"purpose": "low-level isolation and durable infrastructure", "recommended_services": ["Firecracker", "AWS Step Functions", "AWS KMS", "CloudTrail"]},
                "gcp_native": {"purpose": "Vertex AI and Google-native runtime integration", "recommended_services": ["Google Agent Development Kit", "Vertex AI", "Cloud KMS", "Cloud Audit Logs"]},
            },
        },
        "promotion_rule": "A loop may move out of DRAFT only when required runtime layers, evidence proofs, owner references, tool contracts, and authority tests are current.",
    }


def build_schemas() -> dict[str, dict[str, Any]]:
    return {
        "loop-descriptor.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Loop Descriptor",
            "type": "object",
            "required": [
                "loop_id", "name", "version", "status", "category", "purpose", "risk", "authority", "evidence", "controls",
                "runtime_layers", "tool_policy", "sandbox", "egress", "identity", "secrets", "observability", "durability", "recovery", "kill_switch",
            ],
            "properties": {
                "loop_id": {"type": "string", "pattern": "^loop-[0-9]{3}-[a-z0-9-]+$"},
                "name": {"type": "string"},
                "version": {"type": "string"},
                "status": {"enum": ["DRAFT", "PILOT", "ACTIVE", "RESTRICTED", "PAUSED", "DEPRECATED", "RETIRED"]},
                "category": {"type": "object"},
                "purpose": {"type": "object"},
                "risk": {"type": "object"},
                "authority": {"type": "object"},
                "evidence": {"type": "object"},
                "controls": {"type": "object"},
                "runtime_layers": {"type": "object"},
                "tool_policy": {"type": "object"},
                "sandbox": {"type": "object"},
                "egress": {"type": "object"},
                "identity": {"type": "object"},
                "secrets": {"type": "object"},
                "observability": {"type": "object"},
                "durability": {"type": "object"},
                "recovery": {"type": "object"},
                "kill_switch": {"type": "object"},
            },
        },
        "result-envelope.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Standard Result Envelope",
            "type": "object",
            "required": ["loop_id", "loop_version", "execution_id", "correlation_id", "risk_tier", "authority", "trigger", "scope", "state", "evidence", "timestamp"],
            "properties": {
                "loop_id": {"type": "string"},
                "loop_version": {"type": "string"},
                "execution_id": {"type": "string"},
                "correlation_id": {"type": "string"},
                "risk_tier": {"enum": ["R0", "R1", "R2", "R3", "R4"]},
                "authority": {"type": "object"},
                "trigger": {"type": "object"},
                "scope": {"type": "object"},
                "state": {"type": "object"},
                "evidence": {"type": "array"},
                "timestamp": {"type": "string"},
            },
        },
        "control-coverage.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Control Coverage Profile",
            "type": "object",
            "required": ["profile_id", "loop_id", "baseline_risk_tier", "applicable_control_ids", "control_mappings"],
            "properties": {
                "profile_id": {"type": "string"},
                "loop_id": {"type": "string"},
                "baseline_risk_tier": {"enum": ["R0", "R1", "R2", "R3", "R4"]},
                "applicable_control_ids": {"type": "array", "items": {"type": "string", "pattern": "^LC-[0-9]{3}$"}},
                "control_mappings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["control_id", "status", "proof_required"],
                        "properties": {
                            "control_id": {"type": "string", "pattern": "^LC-[0-9]{3}$"},
                            "status": {"enum": ["applicable", "conditional", "delegated", "not_applicable", "blocked_until_proven"]},
                            "proof_required": {"type": "string"},
                            "owner_ref": {"type": "string"},
                        },
                    },
                },
            },
        },
    }


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    value = str(value)
    if value == "":
        return '""'
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value) and value not in {"true", "false", "null"}:
        return value
    return json.dumps(value, ensure_ascii=False)


def to_yaml(value: Any, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}{key}: {yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{spaces}[]"
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{spaces}-")
                lines.append(to_yaml(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{spaces}-")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{spaces}{yaml_scalar(value)}"


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_yaml(data) + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    if not EXTERNAL_STANDARD.exists() and not VENDORED_STANDARD.exists():
        raise SystemExit(f"Production standard missing: {EXTERNAL_STANDARD}")

    standard_text = (
        EXTERNAL_STANDARD.read_text(encoding="utf-8")
        if EXTERNAL_STANDARD.exists()
        else VENDORED_STANDARD.read_text(encoding="utf-8")
    )
    VENDORED_STANDARD.parent.mkdir(parents=True, exist_ok=True)
    VENDORED_STANDARD.write_text(standard_text, encoding="utf-8", newline="\n")

    loops = parse_loops()
    controls = parse_controls(standard_text)
    if len(loops) != 108:
        raise SystemExit(f"Expected 108 loops, parsed {len(loops)}")
    if len(controls) != 109:
        raise SystemExit(f"Expected 109 controls, parsed {len(controls)}")

    standard_hash = hashlib.sha256(standard_text.encode("utf-8")).hexdigest()
    write_yaml(
        ROOT / "standards" / "STANDARD_SOURCE.yaml",
        {
            "version": "1.0",
            "source": str(EXTERNAL_STANDARD),
            "vendored_path": "standards/production-grade-continuous-improvement-loop.md",
            "sha256": standard_hash,
            "last_reviewed": date.today().isoformat(),
            "status": "vendored_for_reproducible_generation",
        },
    )

    write_yaml(ROOT / "controls" / "CONTROL_CATALOG.yaml", {"version": "1.0", "controls": controls})
    write_yaml(ROOT / "runtime" / "loops.catalog.yaml", {"version": "1.0", "loop_count": len(loops), "loops": loops})
    write_yaml(ROOT / "runtime" / "control-applicability.yaml", build_control_applicability(loops, controls))
    write_yaml(ROOT / "runtime" / "architecture_stack.yaml", build_architecture_stack())
    write_yaml(ROOT / "runtime" / "loop_graph.yaml", build_loop_graph(loops))
    write_yaml(ROOT / "runtime" / "state_machine.yaml", build_state_machine())
    write_yaml(ROOT / "runtime" / "tool_contracts.yaml", build_tool_contracts())
    write_yaml(ROOT / "runtime" / "agent_topology.yaml", {
        "version": "1.0",
        "orchestration_shape": "supervisor_graph_with_deterministic_gates",
        "principle": "108 loops are runtime profiles, not 108 unconstrained autonomous agents",
        "nodes": [
            {"node": "Trigger Router", "owns": "event classification, dedupe, initial routing", "reasoning_pattern": "ReAct"},
            {"node": "Qualification Gate", "owns": "scope, owner, input sufficiency, risk tier", "reasoning_pattern": "Chain of Verification"},
            {"node": "Evidence Collector", "owns": "authoritative evidence and lineage", "reasoning_pattern": "ReWOO"},
            {"node": "Diagnosis Planner", "owns": "gap and cause analysis", "reasoning_pattern": "Chain of Thought and Graph of Thoughts"},
            {"node": "Control Applicability Mapper", "owns": "LC control mapping", "reasoning_pattern": "LLM-as-Judge with rules"},
            {"node": "Action Planner", "owns": "remediation sequence and recovery plan", "reasoning_pattern": "Plan-and-Execute"},
            {"node": "Authority Gate", "owns": "approval, policy, separation of duties", "reasoning_pattern": "Guardrail Layers"},
            {"node": "Executor", "owns": "bounded action execution", "reasoning_pattern": "ReWOO or deterministic workflow"},
            {"node": "Validator", "owns": "immediate correctness and non-regression", "reasoning_pattern": "Chain of Verification"},
            {"node": "Proof Runner", "owns": "probe, drill, replay, canary, sustained proof", "reasoning_pattern": "Tool-driven verification"},
            {"node": "Recorder", "owns": "evidence, result envelope, lifecycle events", "reasoning_pattern": "deterministic write path"},
            {"node": "Learning Node", "owns": "regression cases, standards, backlog, memory", "reasoning_pattern": "Reflexion with governed memory"},
            {"node": "Effectiveness Monitor", "owns": "observation window and drift", "reasoning_pattern": "scheduled monitor"},
        ],
    })

    for loop in loops:
        control_ids = loop_control_ids(loop, controls)
        descriptor = build_loop_descriptor(loop, control_ids)
        write_yaml(ROOT / loop["descriptor_path"], descriptor)

    for name, schema in build_schemas().items():
        write_json(ROOT / "schemas" / name, schema)

    write_yaml(ROOT / "owners" / "OWNER_REGISTRY.yaml", build_owner_registry(loops))
    write_yaml(ROOT / "evidence" / "EVIDENCE_LOCATION_REGISTRY.yaml", build_evidence_registry(loops))
    write_yaml(ROOT / "probes" / "PROBE_REGISTRY.yaml", build_probe_registry(loops))
    write_yaml(ROOT / "evals" / "GOLDEN_TASKS.yaml", build_golden_tasks(loops))
    write_yaml(ROOT / "runtime" / "metric_packs.yaml", build_metric_packs(loops))
    write_yaml(ROOT / "runtime" / "practical_operation_cards.yaml", build_practical_operation_cards(loops))
    write_yaml(ROOT / "runtime" / "pilot_playbooks.yaml", build_pilot_playbooks(loops))
    write_yaml(ROOT / "runtime" / "human_handoffs.yaml", build_human_handoffs())
    write_yaml(ROOT / "runtime" / "observability_plan.yaml", build_observability_plan())
    write_yaml(ROOT / "runtime" / "practicality_gaps.yaml", build_practicality_gaps())


if __name__ == "__main__":
    main()
