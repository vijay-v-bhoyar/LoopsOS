from __future__ import annotations

from typing import Any

from scripts.pilot_probes._contracts import check, input_required, result


PROBE_ID = "routing-deduplication-v1"


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = payload or {}
    trigger = record.get("trigger_record")
    graph = record.get("loop_graph")
    if not isinstance(trigger, dict) or not isinstance(graph, dict):
        return input_required(PROBE_ID, ["trigger_record", "loop_graph"])

    trigger_id = trigger.get("trigger_id")
    routes = graph.get("routes")
    active_handlers = trigger.get("active_handlers")
    if not isinstance(trigger_id, str) or not trigger_id.strip():
        return input_required(PROBE_ID, ["trigger_record.trigger_id"])
    if not isinstance(routes, dict) or not isinstance(active_handlers, list):
        return input_required(PROBE_ID, ["loop_graph.routes", "trigger_record.active_handlers"])

    candidates = routes.get(trigger_id)
    primary = trigger.get("primary_loop_id")
    route_is_unique = isinstance(candidates, list) and len(candidates) == 1 and all(isinstance(item, str) for item in candidates)
    primary_selected = route_is_unique and primary == candidates[0]

    keys: list[str] = []
    handlers_are_well_formed = True
    for handler in active_handlers:
        if not isinstance(handler, dict):
            handlers_are_well_formed = False
            continue
        key = handler.get("deduplication_key")
        loop_id = handler.get("loop_id")
        if not isinstance(key, str) or not key.strip() or loop_id != primary:
            handlers_are_well_formed = False
        else:
            keys.append(key)
    duplicate_suppressed = handlers_are_well_formed and len(keys) == len(set(keys)) and len(keys) <= 1

    checks = [
        check("single_primary_route", route_is_unique, "The trigger resolves to exactly one loop."),
        check("primary_loop_selected", primary_selected, "The selected primary loop matches the unique route."),
        check(
            "duplicate_active_handling_suppressed",
            duplicate_suppressed,
            "At most one active handler owns the deduplication key for the primary loop.",
        ),
    ]
    return result(PROBE_ID, checks, "ROUTED" if all(item["passed"] for item in checks) else "BLOCKED")
