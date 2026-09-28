from __future__ import annotations

from typing import Any

from scripts.pilot_probes._contracts import check, input_required, result


PROBE_ID = "state-transition-v1"


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = payload or {}
    machine = record.get("state_machine")
    event = record.get("state_event")
    if not isinstance(machine, dict) or not isinstance(event, dict):
        return input_required(PROBE_ID, ["state_machine", "state_event"])

    transitions = machine.get("allowed_transitions")
    from_state = event.get("from_state", event.get("from"))
    to_state = event.get("to_state", event.get("to"))
    if not isinstance(transitions, dict) or not isinstance(from_state, str) or not isinstance(to_state, str):
        return input_required(PROBE_ID, ["state_machine.allowed_transitions", "state_event.from_state", "state_event.to_state"])

    destinations = transitions.get(from_state, [])
    allowed = isinstance(destinations, list) and to_state in destinations
    expected = str(event.get("expected", "allow")).lower()
    if expected == "block":
        checks = [
            check("illegal_transition_blocked", not allowed, "An undeclared state transition is rejected before mutation."),
        ]
        outcome = "BLOCKED"
    else:
        checks = [
            check("allowed_transition_passes", allowed, "A declared state transition is accepted by the state machine."),
        ]
        outcome = "ALLOWED" if allowed else "BLOCKED"
    return result(PROBE_ID, checks, outcome)
