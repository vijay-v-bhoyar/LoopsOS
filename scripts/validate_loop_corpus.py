import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CATEGORY_COUNTS = {
    "01-product-strategy-discovery-and-lifecycle": 5,
    "02-requirements-backlog-and-delivery-management": 9,
    "03-architecture-design-and-modernization": 6,
    "04-software-engineering-and-build": 5,
    "05-testing-validation-and-experience-quality": 10,
    "06-devops-release-and-environment-management": 5,
    "07-operations-reliability-and-service-management": 8,
    "08-data-database-and-knowledge-management": 8,
    "09-ai-and-generative-ai-lifecycle-and-quality": 9,
    "10-agentic-ai-execution-and-orchestration": 11,
    "11-security-privacy-and-supply-chain-assurance": 14,
    "12-frontier-quantum-and-strategic-resilience": 8,
    "13-enterprise-governance-adoption-and-workforce": 10,
}

REQUIRED_FILES = [
    "standards/production-grade-continuous-improvement-loop.md",
    "standards/STANDARD_SOURCE.yaml",
    "controls/CONTROL_CATALOG.yaml",
    "schemas/loop-descriptor.schema.json",
    "schemas/result-envelope.schema.json",
    "schemas/control-coverage.schema.json",
    "schemas/operational-evidence.schema.json",
    "runtime/loops.catalog.yaml",
    "runtime/control-applicability.yaml",
    "runtime/architecture_stack.yaml",
    "runtime/loop_graph.yaml",
    "runtime/state_machine.yaml",
    "runtime/tool_contracts.yaml",
    "runtime/agent_topology.yaml",
    "runtime/metric_packs.yaml",
    "runtime/practical_operation_cards.yaml",
    "runtime/pilot_playbooks.yaml",
    "runtime/human_handoffs.yaml",
    "runtime/observability_plan.yaml",
    "runtime/practicality_gaps.yaml",
    "runtime/PRACTICAL_OPERATING_GUIDE.md",
    "owners/OWNER_REGISTRY.yaml",
    "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
    "probes/PROBE_REGISTRY.yaml",
    "evals/GOLDEN_TASKS.yaml",
]


def read(path: str | Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, re.MULTILINE))


def values(pattern: str, text: str) -> list[str]:
    return re.findall(pattern, text, re.MULTILINE)


def check(condition: bool, message: str, errors: list[str], ok: list[str]) -> None:
    if condition:
        ok.append(message)
    else:
        errors.append(message)


def markdown_loop_files() -> list[Path]:
    return [p for p in (ROOT / "loops").rglob("*.md") if p.name != "README.md"]


def framework_loop_names() -> list[str]:
    text = read("SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md")
    names = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*\d+\s*\|\s*\*\*(.*?)\*\*", line)
        if match:
            names.append(match.group(1).strip())
    return names


def markdown_headings() -> list[str]:
    headings = []
    for path in markdown_loop_files():
        first = path.read_text(encoding="utf-8").splitlines()[0]
        headings.append(first.lstrip("#").strip())
    return headings


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_required_files(errors: list[str], ok: list[str]) -> None:
    for rel in REQUIRED_FILES:
        check((ROOT / rel).exists(), f"required file exists: {rel}", errors, ok)


def validate_markdown_corpus(errors: list[str], ok: list[str]) -> None:
    loop_files = markdown_loop_files()
    check(len(loop_files) == 108, f"expanded Markdown loop files count is 108, found {len(loop_files)}", errors, ok)

    category_dirs = sorted([p for p in (ROOT / "loops").iterdir() if p.is_dir()])
    check(len(category_dirs) == 13, f"category folder count is 13, found {len(category_dirs)}", errors, ok)
    for category, expected in EXPECTED_CATEGORY_COUNTS.items():
        files = [p for p in (ROOT / "loops" / category).glob("*.md") if p.name != "README.md"]
        check(len(files) == expected, f"{category} has {expected} loop files, found {len(files)}", errors, ok)

    source_names = sorted(framework_loop_names())
    headings = sorted(markdown_headings())
    check(len(source_names) == 108, f"source taxonomy has 108 loop rows, found {len(source_names)}", errors, ok)
    check(source_names == headings, "expanded Markdown headings match source taxonomy loop names", errors, ok)


def validate_runtime_catalogs(errors: list[str], ok: list[str]) -> None:
    loops_catalog = read("runtime/loops.catalog.yaml")
    loop_ids = values(r"^\s*loop_id: (loop-[0-9]{3}-[a-z0-9-]+)$", loops_catalog)
    check(len(loop_ids) == 108, f"runtime loop catalog has 108 loop IDs, found {len(loop_ids)}", errors, ok)
    check(len(set(loop_ids)) == 108, "runtime loop IDs are unique", errors, ok)
    check(count(r"^\s*descriptor_path: runtime/loop-descriptors/", loops_catalog) == 108, "runtime loop catalog has 108 descriptor paths", errors, ok)

    descriptors = sorted((ROOT / "runtime" / "loop-descriptors").glob("*.yaml"))
    check(len(descriptors) == 108, f"runtime descriptor count is 108, found {len(descriptors)}", errors, ok)

    descriptor_ids = []
    bad_descriptors = []
    enterprise_field_counts = {
        "runtime_layers": 0,
        "tool_policy": 0,
        "sandbox": 0,
        "egress": 0,
        "identity": 0,
        "secrets": 0,
        "observability": 0,
        "durability": 0,
        "recovery": 0,
        "kill_switch": 0,
    }
    high_risk_missing = []
    for path in descriptors:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^loop_id: (loop-[0-9]{3}-[a-z0-9-]+)$", text, re.MULTILINE)
        if match:
            descriptor_ids.append(match.group(1))
        if re.search(r"^\s*trigger: \"?\"?$", text, re.MULTILINE):
            bad_descriptors.append(path.name)
        if re.search(r"^\s*outcome_to_improve: \"?\"?$", text, re.MULTILINE):
            bad_descriptors.append(path.name)
        for field in enterprise_field_counts:
            if re.search(rf"^{field}:", text, re.MULTILINE):
                enterprise_field_counts[field] += 1
        number = int(path.name[:3])
        if number in [*range(66, 81), 89, *range(100, 105)]:
            if "sandbox-e2b-firecracker-production" not in text or "security_privileged" not in text:
                high_risk_missing.append(path.name)
    check(sorted(loop_ids) == sorted(descriptor_ids), "descriptor loop IDs match runtime loop catalog", errors, ok)
    check(not bad_descriptors, f"descriptors have non-empty trigger and outcome fields; bad={bad_descriptors[:5]}", errors, ok)
    for field, found in enterprise_field_counts.items():
        check(found == 108, f"runtime descriptors declare enterprise field {field}, found {found}", errors, ok)
    check(not high_risk_missing, f"high-risk descriptors declare Firecracker sandbox and privileged action policy; bad={high_risk_missing[:5]}", errors, ok)


def validate_controls(errors: list[str], ok: list[str]) -> None:
    control_catalog = read("controls/CONTROL_CATALOG.yaml")
    control_ids = values(r"^\s*control_id: (LC-[0-9]{3})$", control_catalog)
    expected_ids = [f"LC-{i:03d}" for i in range(1, 110)]
    check(len(control_ids) == 109, f"control catalog has 109 controls, found {len(control_ids)}", errors, ok)
    check(control_ids == expected_ids, "control catalog IDs are LC-001 through LC-109 in order", errors, ok)

    applicability = read("runtime/control-applicability.yaml")
    profiles = values(r"^\s*profile_id: profile-(loop-[0-9]{3}-[a-z0-9-]+)$", applicability)
    check(len(profiles) == 108, f"control applicability has 108 profiles, found {len(profiles)}", errors, ok)
    check(count(r"^\s*applicable_control_ids:", applicability) == 108, "control applicability has control lists for all 108 loops", errors, ok)
    check(count(r"^\s*control_mappings:", applicability) == 108, "control applicability has sparse control mappings for all 108 loops", errors, ok)
    for status in ["applicable", "conditional", "delegated", "not_applicable", "blocked_until_proven"]:
        check(status in applicability, f"control applicability supports status: {status}", errors, ok)


def validate_graph_and_state(errors: list[str], ok: list[str]) -> None:
    graph = read("runtime/loop_graph.yaml")
    edge_count = count(r"^\s*from: loop-", graph)
    check(edge_count >= 108, f"loop graph has at least 108 edges, found {edge_count}", errors, ok)
    for required in ["correlation_id_required", "max_fan_out_per_event", "loop_storm_breaker", "oscillation_escalation"]:
        check(required in graph, f"loop graph contains cycle control: {required}", errors, ok)

    state = read("runtime/state_machine.yaml")
    for required_state in ["TRIGGERED", "QUALIFIED", "ACTION_APPLIED", "VALIDATION_PASSED", "PROOF_GREEN", "EFFECTIVENESS_PENDING", "EFFECTIVENESS_PROVEN"]:
        check(required_state in state, f"state machine contains state: {required_state}", errors, ok)
    check("ACTION_APPLIED is never equivalent to EFFECTIVENESS_PROVEN" in state, "state machine preserves action/effectiveness invariant", errors, ok)


def validate_registries_and_runtime_assets(errors: list[str], ok: list[str]) -> None:
    owners = read("owners/OWNER_REGISTRY.yaml")
    evidence = read("evidence/EVIDENCE_LOCATION_REGISTRY.yaml")
    probes = read("probes/PROBE_REGISTRY.yaml")
    golden = read("evals/GOLDEN_TASKS.yaml")
    metrics = read("runtime/metric_packs.yaml")
    tools = read("runtime/tool_contracts.yaml")
    topology = read("runtime/agent_topology.yaml")
    operation_cards = read("runtime/practical_operation_cards.yaml")
    playbooks = read("runtime/pilot_playbooks.yaml")
    handoffs = read("runtime/human_handoffs.yaml")
    observability = read("runtime/observability_plan.yaml")
    gaps = read("runtime/practicality_gaps.yaml")
    stack = read("runtime/architecture_stack.yaml")

    check(count(r"^\s*owner_ref: owner-category-", owners) == 13, "owner registry has 13 category owner records", errors, ok)
    check(count(r"^\s*evidence_ref: evidence-category-", evidence) == 13, "evidence registry has 13 category evidence records", errors, ok)
    check(count(r"^\s*probe_id:", probes) >= 5, "probe registry has at least 5 probes", errors, ok)
    check(count(r"^\s*golden_task_ref: golden-loop-", golden) == 108, "golden task registry has 108 loop task groups", errors, ok)
    check(count(r"^\s*task_id: loop-", golden) >= 324, "golden task registry has at least 3 tasks per loop", errors, ok)
    check(count(r"^\s*metric_pack_ref: metrics-loop-", metrics) == 108, "metric pack registry has 108 metric packs", errors, ok)
    check(count(r"^\s*tool:", tools) >= 12, "tool contract registry has at least 12 tool contracts", errors, ok)
    for required_tool_policy in ["filesystem_default", "egress_control", "blocked_networks", "credential_handling", "policy_decision_log_required"]:
        check(required_tool_policy in tools, f"tool contracts define enterprise execution policy: {required_tool_policy}", errors, ok)
    for required_tool in ["sandbox_profile_resolver", "egress_policy_checker", "credential_injection_broker", "policy_decision_logger"]:
        check(required_tool in tools, f"tool contract registry contains enterprise tool: {required_tool}", errors, ok)
    check("108 loops are runtime profiles" in topology, "agent topology defines loops as runtime profiles, not unconstrained autonomous agents", errors, ok)
    for required_layer in ["orchestration", "durable_execution", "sandboxing", "policy", "guardrails", "observability", "identity_and_secrets", "cloud_deployment_profiles"]:
        check(required_layer in stack, f"architecture stack defines required layer: {required_layer}", errors, ok)
    for required_default in ["LangGraph", "Restate", "Temporal", "Open Policy Agent", "E2B_Firecracker", "Modal_gVisor", "Langfuse", "Arize Phoenix"]:
        check(required_default in stack, f"architecture stack names adapter/default: {required_default}", errors, ok)
    check(count(r"^\s*operation_card_id: card-loop-", operation_cards) == 108, "practical operation card registry has 108 loop cards", errors, ok)
    check(count(r"^\s*playbook_id: pilot-", playbooks) >= 6, "pilot playbook registry has at least 6 high-impact compound playbooks", errors, ok)
    for required_handoff in [
        "missing_authority",
        "missing_evidence_source",
        "r3_or_r4_action",
        "external_side_effect_or_destructive_action",
        "conditional_expired",
        "security_privacy_or_compliance_failure",
    ]:
        check(required_handoff in handoffs, f"human handoff registry contains: {required_handoff}", errors, ok)
    for required_field in ["loop_id", "correlation_id", "risk_tier", "proof_state", "tools_called", "standard_hash"]:
        check(required_field in observability, f"observability plan requires field: {required_field}", errors, ok)
    for required_evidence in ["worm_siem_audit_sink", "kms_backed_secret_source", "idp_issued_workload_identity", "opa_policy_decision_log", "trace_redaction_proof", "sandbox_escape_negative_probe", "egress_negative_probe"]:
        check(required_evidence in observability, f"observability plan requires enterprise evidence: {required_evidence}", errors, ok)
    for required_gap in ["owners-unassigned", "evidence-locations-unassigned", "metric-targets-unset", "probes-are-contracts-not-integrations"]:
        check(required_gap in gaps, f"practicality gap registry names activation gap: {required_gap}", errors, ok)
    for task_type in ["authorization_denied", "idempotency_replay", "sandbox_egress_blocked", "credential_redaction", "tenant_isolation", "policy_denied", "rollback_required", "kill_switch_triggered"]:
        check(task_type in golden, f"golden task registry includes enterprise task type: {task_type}", errors, ok)


def validate_schemas(errors: list[str], ok: list[str]) -> None:
    for path in (ROOT / "schemas").glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            ok.append(f"schema JSON parses: schemas/{path.name}")
        except json.JSONDecodeError as exc:
            errors.append(f"schema JSON failed to parse: schemas/{path.name}: {exc}")


def validate_standard(errors: list[str], ok: list[str]) -> None:
    standard_path = ROOT / "standards" / "production-grade-continuous-improvement-loop.md"
    source_meta = read("standards/STANDARD_SOURCE.yaml")
    match = re.search(r"^sha256: ([a-f0-9]{64})$", source_meta, re.MULTILINE)
    check(match is not None, "standard source metadata includes sha256", errors, ok)
    if match:
        check(file_sha256(standard_path) == match.group(1), "vendored standard hash matches STANDARD_SOURCE.yaml", errors, ok)


def main() -> int:
    errors: list[str] = []
    ok: list[str] = []

    validate_required_files(errors, ok)
    validate_markdown_corpus(errors, ok)
    validate_runtime_catalogs(errors, ok)
    validate_controls(errors, ok)
    validate_graph_and_state(errors, ok)
    validate_registries_and_runtime_assets(errors, ok)
    validate_schemas(errors, ok)
    validate_standard(errors, ok)

    print(f"PASS checks: {len(ok)}")
    for message in ok:
        print(f"PASS: {message}")
    if errors:
        print(f"FAIL checks: {len(errors)}")
        for message in errors:
            print(f"FAIL: {message}")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
