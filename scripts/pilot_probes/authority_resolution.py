from __future__ import annotations

from typing import Any

from scripts.pilot_probes._contracts import check, input_required, is_bound, result


PROBE_ID = "authority-resolution-v1"


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = payload or {}
    descriptor = record.get("loop_descriptor")
    registry = record.get("owner_registry")
    if not isinstance(descriptor, dict) or not isinstance(registry, dict):
        return input_required(PROBE_ID, ["loop_descriptor", "owner_registry"])

    authority = descriptor.get("authority")
    owner_records = registry.get("owners")
    if not isinstance(authority, dict) or not isinstance(owner_records, list):
        return input_required(PROBE_ID, ["loop_descriptor.authority", "owner_registry.owners"])

    owners = {
        item.get("owner_ref"): item
        for item in owner_records
        if isinstance(item, dict) and isinstance(item.get("owner_ref"), str)
    }
    policy_ref = authority.get("policy_owner_ref")
    gate_ref = authority.get("gate_owner_ref")
    policy_owner = owners.get(policy_ref)
    gate_owner = owners.get(gate_ref)
    policy_resolves = bool(
        isinstance(policy_owner, dict)
        and policy_owner.get("status") in {"PILOT", "ACTIVE"}
        and is_bound(policy_owner.get("policy_owner"))
    )
    gate_resolves = bool(
        isinstance(gate_owner, dict)
        and gate_owner.get("status") in {"PILOT", "ACTIVE"}
        and is_bound(gate_owner.get("gate_owner"))
    )
    conflicts = registry.get("conflicts", [])
    conflict_present = isinstance(conflicts, list) and bool(conflicts)
    conflict_blocks = not conflict_present or registry.get("progression_allowed") is False

    checks = [
        check("policy_owner_resolves", policy_resolves, "The policy owner reference resolves to a bound PILOT or ACTIVE owner."),
        check("gate_owner_resolves", gate_resolves, "The gate owner reference resolves to a bound PILOT or ACTIVE owner."),
        check(
            "owner_conflict_blocks_progression",
            conflict_blocks,
            "Owner conflicts resolve to a blocked decision rather than an authorized progression."
            if conflict_present
            else "No owner conflict is present; progression is not blocked by a conflict.",
        ),
    ]
    authorized = all(item["passed"] for item in checks[:2]) and not conflict_present
    return result(PROBE_ID, checks, "AUTHORIZED" if authorized else "BLOCKED")
