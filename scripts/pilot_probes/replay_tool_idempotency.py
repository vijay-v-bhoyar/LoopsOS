from __future__ import annotations

from typing import Any

from scripts.pilot_probes._contracts import check, input_required, result


PROBE_ID = "replay-tool-idempotency-v1"


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = payload or {}
    operation_id = record.get("operation_id")
    calls = record.get("tool_call_record")
    if not isinstance(operation_id, str) or not operation_id.strip() or not isinstance(calls, list):
        return input_required(PROBE_ID, ["operation_id", "tool_call_record"])
    if len(calls) < 2 or not all(isinstance(call, dict) for call in calls[:2]):
        return input_required(PROBE_ID, ["tool_call_record[0]", "tool_call_record[1]"])

    first, replay = calls[0], calls[1]
    same_operation = first.get("operation_id") == operation_id and replay.get("operation_id") == operation_id
    same_payload = first.get("payload_hash") == replay.get("payload_hash")
    same_effect = first.get("effect_id") == replay.get("effect_id")
    one_logical_effect = record.get("logical_effect_count") == 1
    expected = str(record.get("expected", "replay")).lower()
    if expected == "conflict":
        conflicting_payload = same_operation and not same_payload
        checks = [
            check(
                "conflicting_payload_rejected",
                conflicting_payload and replay.get("decision") == "REJECTED",
                "Conflicting payload reuse is rejected only when the operation identity matches and the payload differs.",
            ),
        ]
        outcome = "BLOCKED"
    else:
        checks = [
            check("same_operation_replayed", same_operation and same_payload, "The repeated call has the same operation and payload identity."),
            check("one_logical_effect", same_effect and one_logical_effect, "The replay maps to one logical effect with no duplicate side effect."),
        ]
        outcome = "REPLAYED" if all(item["passed"] for item in checks) else "BLOCKED"
    return result(PROBE_ID, checks, outcome)
