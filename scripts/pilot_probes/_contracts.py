from __future__ import annotations

from typing import Any, Iterable


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def input_required(probe_id: str, required: Iterable[str]) -> dict[str, Any]:
    fields = list(required)
    return {
        "schema_version": 1,
        "probe_id": probe_id,
        "status": "INPUT_REQUIRED",
        "outcome": "INPUT_REQUIRED",
        "checks": [check("required_inputs", False, f"Required inputs are missing: {', '.join(fields)}.")],
        "missing_inputs": fields,
        "external_calls": 0,
        "proof_scope": "local_contract",
        "live_verification": "unproven",
    }


def result(probe_id: str, checks: list[dict[str, Any]], outcome: str) -> dict[str, Any]:
    passed = all(bool(item.get("passed")) for item in checks)
    return {
        "schema_version": 1,
        "probe_id": probe_id,
        "status": "PASS" if passed else "FAIL",
        "outcome": outcome,
        "checks": checks,
        "external_calls": 0,
        "proof_scope": "local_contract",
        "live_verification": "unproven",
    }


def is_bound(value: Any) -> bool:
    if not isinstance(value, str):
        return value is not None
    return value.strip().upper() not in {
        "",
        "UNASSIGNED",
        "DRAFT",
        "TO_BE_SET",
        "TO_BE_SET_BY_POLICY_OWNER",
    }
