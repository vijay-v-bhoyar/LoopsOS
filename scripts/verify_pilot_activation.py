from __future__ import annotations

import argparse
import ast
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = REPO_ROOT / "authority"
if str(AUTHORITY_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTHORITY_ROOT))

from loopos_authority.config import _http_host_is_valid  # noqa: E402

ACTIVE_STATUSES = {"PILOT", "ACTIVE"}
# A pilot may span several dependent loops, but the full corpus must be
# expanded in separately authorized slices rather than activated at once.
MAX_PILOT_LOOPS = 15
OWNER_FIELDS = (
    "policy_owner",
    "gate_owner",
    "risk_owner",
    "executor_owner",
    "validator_owner",
    "backup_owner",
)
PLACEHOLDER_VALUES = {
    "",
    "DRAFT",
    "UNASSIGNED",
    "TO_BE_SET_BY_POLICY_OWNER",
    "FRESHNESS POLICY MUST BE ASSIGNED BEFORE ACTIVE STATUS",
    "RETENTION POLICY MUST BE ASSIGNED BEFORE ACTIVE STATUS",
}


def _activation_contract() -> dict[str, Any]:
    """Describe the human-owned inputs without supplying any of their values."""
    return {
        "descriptor_statuses": sorted(ACTIVE_STATUSES),
        "owner_registry": {
            "path": "owners/OWNER_REGISTRY.yaml",
            "required_statuses": sorted(ACTIVE_STATUSES),
            "required_fields": list(OWNER_FIELDS),
        },
        "evidence_registry": {
            "path": "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
            "required_statuses": sorted(ACTIVE_STATUSES),
            "required_fields": ["authoritative_location", "freshness_policy", "retention_policy"],
            "authoritative_location": "credential-free HTTPS URL on a globally routable host",
        },
        "metric_registry": {
            "path": "runtime/metric_packs.yaml",
            "required_fields": ["target_value", "observation_window"],
            "target_value": "finite numeric rate between 0 and 1",
        },
        "human_authority": "Organization-owned values must be supplied by named owners; placeholders must not be promoted by automation.",
    }


def _load_yaml(root: Path, relative_path: str) -> Any:
    path = root / relative_path
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _is_bound(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip()
        return bool(normalized) and normalized.upper() not in PLACEHOLDER_VALUES
    return True


def _secure_evidence_location(value: Any) -> bool:
    if not isinstance(value, str) or not _is_bound(value):
        return False
    location = value.strip()
    if any(ord(character) < 32 for character in location) or "\\" in location:
        return False
    try:
        parsed = urlparse(location)
        parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and _http_host_is_valid(parsed.hostname.lower())
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def _metric_target_is_bound(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        target = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            target = float(value.strip())
        except ValueError:
            return False
    else:
        return False
    return math.isfinite(target) and 0 <= target <= 1


def _records(document: Any, key: str, id_key: str) -> dict[str, dict[str, Any]]:
    values = document.get(key, []) if isinstance(document, dict) else []
    records: dict[str, dict[str, Any]] = {}
    if not isinstance(values, list):
        return records
    for record in values:
        if not isinstance(record, dict):
            continue
        record_id = record.get(id_key)
        if isinstance(record_id, str):
            records[record_id] = record
    return records


def _duplicate_record_ids(document: Any, key: str, id_key: str) -> list[str]:
    values = document.get(key, []) if isinstance(document, dict) else []
    counts: dict[str, int] = {}
    if not isinstance(values, list):
        return []
    for record in values:
        if not isinstance(record, dict):
            continue
        record_id = record.get(id_key)
        if isinstance(record_id, str):
            counts[record_id] = counts.get(record_id, 0) + 1
    return sorted(record_id for record_id, count in counts.items() if count > 1)


def _safe_repo_path(root: Path, relative_path: str) -> Path | None:
    if not isinstance(relative_path, str) or not relative_path.strip() or "\x00" in relative_path:
        return None
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return candidate


def _bound_repo_file(root: Path, value: Any) -> Path | None:
    if not _is_bound(value):
        return None
    candidate = _safe_repo_path(root, value)
    return candidate if candidate is not None and candidate.is_file() else None


def _approved_fixture_failure(path: Path) -> str | None:
    """Require explicit approval metadata before a fixture counts as real."""
    try:
        if path.suffix.lower() == ".json":
            fixture = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix.lower() in {".yaml", ".yml"}:
            fixture = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            return "fixture must be JSON or YAML to prove approval metadata"
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        return f"fixture metadata could not be loaded: {error}"
    if not isinstance(fixture, dict):
        return "fixture metadata must be a mapping"
    if fixture.get("fixture_kind") != "approved_golden_fixture":
        return (
            f"fixture_kind is {fixture.get('fixture_kind') or 'missing'}, "
            "expected approved_golden_fixture"
        )
    if not _is_bound(fixture.get("approval_ref")):
        return "approval_ref must identify the organization-owned golden-fixture approval"
    return None


def _probe_adapter_failure(root: Path, value: Any) -> str | None:
    candidate = _bound_repo_file(root, value)
    if candidate is None:
        return "adapter must resolve to a repository file"
    if candidate.suffix.lower() != ".py":
        return "adapter must be a Python file with a run(...) entrypoint"
    try:
        source = candidate.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(candidate))
    except (OSError, UnicodeError) as error:
        return f"adapter could not be read: {error}"
    except SyntaxError as error:
        return f"adapter has invalid Python syntax: {error.msg}"
    if not any(
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "run"
        for node in module.body
    ):
        return "adapter must define a top-level run(...) entrypoint"
    return None


def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def _failure_summary(checks: list[dict[str, Any]]) -> list[str]:
    return [check["detail"] for check in checks if not check["passed"]]


def pilot_activation_report(
    playbook_id: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    selected_id = (playbook_id or os.getenv("LOOPOS_ACTIVE_PLAYBOOK_ID", "")).strip()
    generated_at = datetime.now(timezone.utc).isoformat()
    checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "verdict": "NO_GO",
        "playbook_id": selected_id,
        "available_playbooks": [],
        "selected_loop_count": 0,
        "activation_contract": _activation_contract(),
        "selected_loop_requirements": [],
        "checks": checks,
        "next_actions": [],
    }

    try:
        playbooks_document = _load_yaml(repo_root, "runtime/pilot_playbooks.yaml")
        catalog_document = _load_yaml(repo_root, "runtime/loops.catalog.yaml")
        owners_document = _load_yaml(repo_root, "owners/OWNER_REGISTRY.yaml")
        evidence_document = _load_yaml(repo_root, "evidence/EVIDENCE_LOCATION_REGISTRY.yaml")
        metrics_document = _load_yaml(repo_root, "runtime/metric_packs.yaml")
        golden_document = _load_yaml(repo_root, "evals/GOLDEN_TASKS.yaml")
        probes_document = _load_yaml(repo_root, "probes/PROBE_REGISTRY.yaml")
    except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
        _check(checks, "activation_inputs_load", False, f"Activation inputs could not be loaded: {error}")
        report["next_actions"] = ["Repair the activation registry inputs before selecting a pilot playbook."]
        report["failures"] = _failure_summary(checks)
        return report

    playbooks = _records(playbooks_document, "playbooks", "playbook_id")
    report["available_playbooks"] = [
        {
            "playbook_id": playbook_id,
            "title": playbook.get("title", playbook_id),
            "impact_rank": playbook.get("impact_rank"),
            "loop_count": len(playbook.get("loops", [])) if isinstance(playbook.get("loops"), list) else 0,
            "pilot_scope": playbook.get("pilot_scope", ""),
        }
        for playbook_id, playbook in sorted(
            playbooks.items(),
            key=lambda item: (item[1].get("impact_rank", float("inf")), item[0]),
        )
    ]
    catalog = _records(catalog_document, "loops", "loop_id")
    owners = _records(owners_document, "owners", "owner_ref")
    evidence_locations = _records(evidence_document, "locations", "evidence_ref")
    metrics = _records(metrics_document, "metric_packs", "loop_id")
    golden_tasks = _records(golden_document, "golden_tasks", "loop_id")
    probes = _records(probes_document, "probes", "probe_id")

    duplicate_registry_failures: list[str] = []
    for path, document, key, id_key in (
        ("runtime/pilot_playbooks.yaml", playbooks_document, "playbooks", "playbook_id"),
        ("runtime/loops.catalog.yaml", catalog_document, "loops", "loop_id"),
        ("owners/OWNER_REGISTRY.yaml", owners_document, "owners", "owner_ref"),
        ("evidence/EVIDENCE_LOCATION_REGISTRY.yaml", evidence_document, "locations", "evidence_ref"),
        ("runtime/metric_packs.yaml", metrics_document, "metric_packs", "loop_id"),
        ("evals/GOLDEN_TASKS.yaml", golden_document, "golden_tasks", "loop_id"),
        ("probes/PROBE_REGISTRY.yaml", probes_document, "probes", "probe_id"),
    ):
        duplicate_ids = _duplicate_record_ids(document, key, id_key)
        if duplicate_ids:
            duplicate_registry_failures.append(
                f"{path}: duplicate {id_key}(s): {', '.join(duplicate_ids)}."
            )
    _check(
        checks,
        "activation_registries_have_unique_ids",
        not duplicate_registry_failures,
        "Activation registry IDs are unique."
        if not duplicate_registry_failures
        else " ".join(duplicate_registry_failures),
    )

    selected_playbook = playbooks.get(selected_id)
    _check(
        checks,
        "active_playbook_selected",
        selected_playbook is not None,
        (
            f"Selected pilot playbook resolves: {selected_id}."
            if selected_playbook is not None
            else "Select one real pilot with LOOPOS_ACTIVE_PLAYBOOK_ID before activation."
        ),
    )
    if selected_playbook is None:
        report["next_actions"] = [
            "Select one scoped pilot playbook; do not activate the complete 108-loop corpus as one change."
        ]
        report["failures"] = _failure_summary(checks)
        return report

    selected_loop_ids = selected_playbook.get("loops", [])
    if not isinstance(selected_loop_ids, list):
        selected_loop_ids = []
    report["selected_loop_count"] = len(selected_loop_ids)
    _check(
        checks,
        "pilot_scope_declared",
        _is_bound(selected_playbook.get("pilot_scope")),
        (
            f"Pilot scope is declared: {selected_playbook.get('pilot_scope')}."
            if _is_bound(selected_playbook.get("pilot_scope"))
            else "Selected pilot playbook must declare a bounded pilot_scope."
        ),
    )
    _check(
        checks,
        "pilot_scope_contains_loops",
        bool(selected_loop_ids),
        f"The selected playbook declares {len(selected_loop_ids)} loop(s)."
        if selected_loop_ids
        else "Selected pilot playbook must declare at least one loop.",
    )
    _check(
        checks,
        "pilot_scope_size_bounded",
        bool(selected_loop_ids) and len(selected_loop_ids) <= MAX_PILOT_LOOPS,
        (
            f"Pilot scope contains {len(selected_loop_ids)} loop(s), within the maximum of {MAX_PILOT_LOOPS}."
            if bool(selected_loop_ids) and len(selected_loop_ids) <= MAX_PILOT_LOOPS
            else f"Pilot scope contains {len(selected_loop_ids)} loop(s); the maximum bounded pilot size is {MAX_PILOT_LOOPS}.")
    )
    duplicate_loop_ids = sorted(
        {
            loop_id
            for loop_id in selected_loop_ids
            if isinstance(loop_id, str) and selected_loop_ids.count(loop_id) > 1
        }
    )
    _check(
        checks,
        "pilot_scope_has_unique_loops",
        not duplicate_loop_ids,
        "Selected pilot loop IDs are unique."
        if not duplicate_loop_ids
        else f"Selected pilot playbook repeats loop ID(s): {', '.join(duplicate_loop_ids)}.",
    )

    active_loop_failures: list[str] = []
    owner_failures: list[str] = []
    evidence_failures: list[str] = []
    metric_failures: list[str] = []
    golden_failures: list[str] = []
    golden_approval_failures: list[str] = []
    probe_failures: list[str] = []
    activation_requirements: list[dict[str, Any]] = []

    for loop_id in selected_loop_ids:
        if not isinstance(loop_id, str):
            active_loop_failures.append("selected playbook contains a non-string loop ID")
            activation_requirements.append({
                "loop_id": loop_id,
                "blocking_requirements": ["selected loop ID must be a string"],
            })
            continue
        catalog_entry = catalog.get(loop_id)
        if catalog_entry is None:
            active_loop_failures.append(f"{loop_id}: missing runtime catalog entry")
            activation_requirements.append({
                "loop_id": loop_id,
                "blocking_requirements": ["runtime catalog entry"],
            })
            continue

        descriptor_path = catalog_entry.get("descriptor_path")
        descriptor_file = (
            _safe_repo_path(repo_root, descriptor_path)
            if isinstance(descriptor_path, str)
            else None
        )
        if descriptor_file is None or not descriptor_file.exists():
            active_loop_failures.append(f"{loop_id}: descriptor path is missing or escapes the repository")
            activation_requirements.append({
                "loop_id": loop_id,
                "descriptor_path": descriptor_path,
                "blocking_requirements": ["descriptor path"],
            })
            continue
        try:
            descriptor = yaml.safe_load(descriptor_file.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
            active_loop_failures.append(f"{loop_id}: descriptor cannot be loaded: {error}")
            activation_requirements.append({
                "loop_id": loop_id,
                "descriptor_path": descriptor_path,
                "blocking_requirements": ["descriptor can be loaded"],
            })
            continue

        if not isinstance(descriptor, dict):
            active_loop_failures.append(f"{loop_id}: descriptor must be a mapping")
            activation_requirements.append({
                "loop_id": loop_id,
                "descriptor_path": descriptor_path,
                "blocking_requirements": ["descriptor mapping"],
            })
            continue
        if descriptor.get("loop_id") != loop_id:
            active_loop_failures.append(
                f"{loop_id}: descriptor loop_id is {descriptor.get('loop_id') or 'missing'}, expected {loop_id}"
            )

        status = descriptor.get("status")
        if status not in ACTIVE_STATUSES:
            active_loop_failures.append(f"{loop_id}: descriptor status is {status or 'missing'}, expected PILOT or ACTIVE")

        authority = descriptor.get("authority", {}) if isinstance(descriptor, dict) else {}
        owner_ref = authority.get("policy_owner_ref") if isinstance(authority, dict) else None
        owner = owners.get(owner_ref) if isinstance(owner_ref, str) else None
        missing_owner_fields = [field for field in OWNER_FIELDS if not owner or not _is_bound(owner.get(field))]
        if not owner or owner.get("status") not in ACTIVE_STATUSES or missing_owner_fields:
            owner_failures.append(
                f"{loop_id}: owner {owner_ref or 'missing'} must be PILOT/ACTIVE with bound {', '.join(missing_owner_fields or OWNER_FIELDS)}"
            )

        evidence = descriptor.get("evidence", {}) if isinstance(descriptor, dict) else {}
        evidence_ref = evidence.get("primary_location_ref") if isinstance(evidence, dict) else None
        evidence_location = evidence_locations.get(evidence_ref) if isinstance(evidence_ref, str) else None
        missing_evidence_fields = [
            field
            for field in ("authoritative_location", "freshness_policy", "retention_policy")
            if not evidence_location or not _is_bound(evidence_location.get(field))
        ]
        if evidence_location and _is_bound(evidence_location.get("authoritative_location")) and not _secure_evidence_location(
            evidence_location.get("authoritative_location")
        ):
            missing_evidence_fields.append("authoritative_location must be a safe HTTPS URL")
        if (
            not evidence_location
            or evidence_location.get("status") not in ACTIVE_STATUSES
            or missing_evidence_fields
        ):
            evidence_failures.append(
                f"{loop_id}: evidence {evidence_ref or 'missing'} must be PILOT/ACTIVE with bound {', '.join(missing_evidence_fields or ('status',))}"
            )

        metric = metrics.get(loop_id)
        primary_metric = metric.get("primary_metric", {}) if isinstance(metric, dict) else {}
        missing_metric_fields: list[str] = []
        if not metric or not _metric_target_is_bound(primary_metric.get("target_value")):
            missing_metric_fields.append("target_value")
            metric_failures.append(
                f"{loop_id}: metric target must be a finite numeric rate between 0 and 1 assigned by the policy owner"
            )
        if not metric or not _is_bound(primary_metric.get("observation_window")):
            missing_metric_fields.append("observation_window")
            metric_failures.append(f"{loop_id}: metric observation window is not assigned by the policy owner")

        activation_requirements.append({
            "loop_id": loop_id,
            "descriptor_path": descriptor_path,
            "descriptor_status": status,
            "required_descriptor_statuses": sorted(ACTIVE_STATUSES),
            "owner_ref": owner_ref,
            "owner_status": owner.get("status") if isinstance(owner, dict) else None,
            "required_owner_fields": list(OWNER_FIELDS),
            "missing_owner_fields": missing_owner_fields,
            "evidence_ref": evidence_ref,
            "evidence_status": evidence_location.get("status") if isinstance(evidence_location, dict) else None,
            "required_evidence_fields": ["authoritative_location", "freshness_policy", "retention_policy"],
            "missing_evidence_fields": missing_evidence_fields,
            "metric_pack_ref": metric.get("metric_pack_ref") if isinstance(metric, dict) else None,
            "required_metric_fields": ["target_value", "observation_window"],
            "missing_metric_fields": missing_metric_fields,
        })

        golden = golden_tasks.get(loop_id)
        tasks = golden.get("tasks", []) if isinstance(golden, dict) else []
        fixture_refs: list[str] = []
        if not golden or not isinstance(tasks, list) or not tasks:
            golden_failures.append(f"{loop_id}: golden tasks need a non-empty tasks list with fixture_ref values")
        else:
            invalid_fixtures = []
            for task in tasks:
                if not isinstance(task, dict):
                    invalid_fixtures.append("task must be a mapping with a fixture_ref")
                    continue
                task_id = task.get("task_id", "unknown")
                fixture_ref = task.get("fixture_ref")
                fixture_file = _bound_repo_file(repo_root, fixture_ref)
                if fixture_file is None:
                    invalid_fixtures.append(f"{task_id} fixture_ref must resolve to a repository file")
                    continue
                fixture_refs.append(str(fixture_ref))
                approval_failure = _approved_fixture_failure(fixture_file)
                if approval_failure is not None:
                    golden_approval_failures.append(f"{loop_id} {task_id}: {approval_failure}")
            if invalid_fixtures:
                golden_failures.append(f"{loop_id}: " + "; ".join(invalid_fixtures))

        if activation_requirements:
            activation_requirements[-1]["golden_task_count"] = len(tasks) if isinstance(tasks, list) else 0
            activation_requirements[-1]["golden_fixture_refs"] = fixture_refs

        loop_probes = [
            probe
            for probe in probes.values()
            if loop_id in (probe.get("loop_ids", []) if isinstance(probe, dict) else [])
        ]
        valid_adapters = []
        invalid_adapters = []
        for probe in loop_probes:
            probe_id = probe.get("probe_id", "unknown") if isinstance(probe, dict) else "unknown"
            adapter = probe.get("adapter") if isinstance(probe, dict) else None
            adapter_failure = _probe_adapter_failure(repo_root, adapter)
            if adapter_failure is None:
                valid_adapters.append(probe_id)
            else:
                invalid_adapters.append(f"{probe_id} {adapter_failure}")
        if not valid_adapters:
            probe_failures.append(
                f"{loop_id}: "
                + ("; ".join(invalid_adapters) if invalid_adapters else "at least one probe needs a bound executable adapter")
            )

    _check(
        checks,
        "selected_loops_have_activation_status",
        not active_loop_failures,
        "All selected loops are PILOT or ACTIVE."
        if not active_loop_failures
        else "; ".join(active_loop_failures),
    )
    _check(
        checks,
        "selected_loops_have_named_owners",
        not owner_failures,
        "All selected loops resolve six named owner roles."
        if not owner_failures
        else "; ".join(owner_failures),
    )
    _check(
        checks,
        "selected_loops_have_authoritative_evidence",
        not evidence_failures,
        "All selected loops resolve active authoritative evidence locations."
        if not evidence_failures
        else "; ".join(evidence_failures),
    )
    _check(
        checks,
        "selected_loops_have_metric_targets",
        not metric_failures,
        "All selected loops have policy-owned metric targets."
        if not metric_failures
        else "; ".join(metric_failures),
    )
    _check(
        checks,
        "selected_loops_have_real_golden_fixtures",
        not golden_failures and not golden_approval_failures,
        "All selected loops have approved golden fixtures."
        if not golden_failures and not golden_approval_failures
        else "; ".join(golden_failures + golden_approval_failures),
    )
    _check(
        checks,
        "selected_loops_have_fixture_bound_golden_tasks",
        not golden_failures,
        "All selected loops have repository-bound golden tasks."
        if not golden_failures
        else "; ".join(golden_failures),
    )
    _check(
        checks,
        "selected_loops_have_executable_probes",
        not probe_failures,
        "All selected loops have at least one executable probe adapter."
        if not probe_failures
        else "; ".join(probe_failures),
    )

    failures = _failure_summary(checks)
    report["failures"] = failures
    report["selected_loop_requirements"] = activation_requirements
    if not failures:
        report["verdict"] = "GO"
        report["next_actions"] = ["Keep the selected scope bounded and record the first live result envelope before expansion."]
    else:
        report["next_actions"] = [
            "Resolve every failed activation check with organization-owned evidence before changing a loop to PILOT or ACTIVE.",
            "Keep production handover blocked until the selected pilot and the runtime deployment proofs are independently verified.",
        ]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a bounded LoopsOS pilot activation scope.")
    parser.add_argument("--playbook-id", default=os.getenv("LOOPOS_ACTIVE_PLAYBOOK_ID", ""))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = pilot_activation_report(args.playbook_id)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["verdict"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
