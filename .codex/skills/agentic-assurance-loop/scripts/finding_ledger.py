"""Bind one stable defect finding to repair and independent closure review."""
from evidence_io import fields, word, strings, need, receipt, artifacts, artifact, is_current, covers_changes, run


def validate(record, root, current):
    fields(record, "id parent_goal criteria mode owner require_independent events")
    for key in ("id", "parent_goal", "owner"):
        word(record[key])
    criteria = strings(record["criteria"])
    need(record["mode"] in {"ASSESS_AND_PLAN", "VERIFY_APPROVED_SANDBOX", "REMEDIATE_APPROVED_SCOPE"}, "invalid mode")
    need(type(record["require_independent"]) is bool, "independence policy required")
    need(isinstance(record["events"], list), "events must be list")
    reproduction, repair, closure, help_items = None, None, None, []
    for event in record["events"]:
        need(isinstance(event, dict), "event must be object")
        kind = event.get("kind")
        if kind == "reproduction":
            fields(event, "kind receipt cause confidence")
            word(event["cause"])
            need(event["confidence"] in {"hypothesis", "supported", "confirmed"}, "invalid cause confidence")
            receipt(event["receipt"], root, None, success=False, fresh=False)
            if reproduction is not None:
                need(event["receipt"]["oracle"] == reproduction["receipt"]["oracle"], "original reproduction oracle changed")
            reproduction, repair, closure = event, None, None
        elif kind == "repair":
            fields(event, "kind owner changes rationale")
            need(record["mode"] == "REMEDIATE_APPROVED_SCOPE", "mode forbids recording an executed repair")
            need(reproduction is not None, "reproduce before repair")
            word(event["owner"])
            word(event["rationale"])
            artifacts(event["changes"], root)
            repair, closure = event, None
        elif kind == "verify":
            fields(event, "kind criteria original regression acceptance acceptance_owner residual_risk")
            need(record["mode"] != "ASSESS_AND_PLAN" and repair is not None, "repair and execution mode required")
            need(strings(event["criteria"]) == criteria, "closure criteria incomplete")
            for key in ("original", "regression"):
                receipt(event[key], root, None, fresh=False)
                covers_changes(event[key], repair["changes"])
                if record["require_independent"]:
                    need(event[key]["actor"] != repair["owner"], "independent verifier required")
            need(event["original"]["oracle"] == reproduction["receipt"]["oracle"], "original reproduction oracle changed")
            artifact(event["acceptance"], root)
            word(event["acceptance_owner"])
            need(event["acceptance_owner"] == record["owner"], "wrong acceptance owner")
            word(event["residual_risk"])
            closure = event
        elif kind == "help":
            fields(event, "kind owner question needs wake_condition")
            for key in ("owner", "question", "needs", "wake_condition"):
                word(event[key])
            help_items.append(event)
        else:
            raise ValueError("unknown finding event")
    ready = closure is not None and all(is_current(closure[key], current) for key in ("original", "regression"))
    return {"status": "CLOSURE_REVIEW_READY" if ready else "FINDING_OPEN", "finding_id": record["id"],
            "parent_goal": record["parent_goal"], "verified_criteria": sorted(criteria) if ready else [],
            "help": help_items, "independence": "named distinct actors" if ready and record["require_independent"] else "not established",
            "closed": False}


if __name__ == "__main__":
    raise SystemExit(run(validate))
