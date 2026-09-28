from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from scripts.pilot_probes._contracts import check, input_required, result


PROBE_ID = "proof-scope-freshness-v1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = payload or {}
    proof = record.get("proof_record", record.get("evidence_record"))
    registry = record.get("evidence_registry")
    policy = record.get("freshness_policy")
    if not isinstance(proof, dict) or not isinstance(registry, dict):
        return input_required(PROBE_ID, ["proof_record", "evidence_registry"])
    if not isinstance(policy, dict):
        policy = registry.get("freshness_policy")
    if not isinstance(policy, dict):
        return input_required(PROBE_ID, ["evidence_registry.freshness_policy"])

    captured_at = _timestamp(proof.get("captured_at"))
    now = _timestamp(policy.get("as_of", policy.get("now")))
    max_age = policy.get("max_age_seconds")
    expected_scope = record.get("expected_scope", registry.get("scope"))
    age = (now - captured_at).total_seconds() if now and captured_at else None
    current = isinstance(age, (int, float)) and 0 <= age <= max_age if isinstance(max_age, (int, float)) and not isinstance(max_age, bool) else False
    scope_bound = isinstance(expected_scope, str) and expected_scope.strip() == proof.get("scope")
    digest_valid = isinstance(proof.get("sha256"), str) and bool(SHA256_PATTERN.fullmatch(proof["sha256"]))
    accepted = current and scope_bound and digest_valid
    expected = str(record.get("expected_decision", "accept")).lower()
    if expected == "reject":
        checks = [
            check("expired_or_out_of_scope_proof_rejected", not accepted, "Stale, out-of-scope, or malformed proof is blocked."),
        ]
        outcome = "BLOCKED"
    else:
        checks = [
            check("proof_is_current", current, "The proof timestamp is within the declared freshness window."),
            check("proof_is_scope_bound", scope_bound, "The proof scope matches the expected evidence scope."),
            check("proof_digest_is_valid", digest_valid, "The proof carries a lowercase SHA-256 digest."),
        ]
        outcome = "ACCEPTED" if accepted else "BLOCKED"
    return result(PROBE_ID, checks, outcome)
