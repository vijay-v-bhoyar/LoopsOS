"""Track owned strategic unknowns and evidence-bound, explicitly accepted scope."""
from evidence_io import fields, word, strings, need, receipt, artifact, is_current, run


def validate(record, root, current):
    fields(record, "id owner criteria assumptions events")
    word(record["id"])
    word(record["owner"])
    criteria = strings(record["criteria"])
    need(isinstance(record["assumptions"], list) and record["assumptions"], "assumptions required")
    assumptions, experiments, decisions = {}, {}, {}
    for item in record["assumptions"]:
        fields(item, "id claim owner affected_criteria experiment decision_owner revisit_trigger")
        for key in ("id", "claim", "owner", "experiment", "decision_owner", "revisit_trigger"):
            word(item[key])
        need(item["id"] not in assumptions, "duplicate assumption")
        need(strings(item["affected_criteria"]) <= criteria, "unknown affected criterion")
        assumptions[item["id"]] = item
    need(set().union(*(set(item["affected_criteria"]) for item in assumptions.values())) == criteria, "criteria lack assumption coverage")
    need(isinstance(record["events"], list), "events must be list")
    for event in record["events"]:
        need(isinstance(event, dict), "event must be object")
        ident = word(event.get("assumption_id"))
        need(ident in assumptions, "unknown assumption")
        if event.get("kind") == "experiment":
            fields(event, "kind assumption_id receipt interpretation")
            receipt(event["receipt"], root, None, fresh=False)
            need(event["receipt"]["actor"] == assumptions[ident]["owner"], "wrong experiment owner")
            word(event["interpretation"])
            experiments[ident] = event
            decisions.pop(ident, None)
        elif event.get("kind") == "decision":
            fields(event, "kind assumption_id actor outcome rationale acceptance evidence_sha256")
            need(ident in experiments, "experiment evidence required before decision")
            need(event["actor"] == assumptions[ident]["decision_owner"], "wrong decision owner")
            need(event["outcome"] in {"accepted", "rejected", "deferred"}, "invalid decision")
            word(event["rationale"])
            artifact(event["acceptance"], root)
            need(event["evidence_sha256"] == experiments[ident]["receipt"]["output"]["sha256"], "decision cites different experiment")
            decisions[ident] = event
        else:
            raise ValueError("unknown vision event")
    accepted, unresolved = set(criteria), []
    for ident, item in assumptions.items():
        usable = ident in decisions and decisions[ident]["outcome"] == "accepted" and is_current(experiments[ident]["receipt"], current)
        if not usable:
            accepted -= set(item["affected_criteria"])
            unresolved.append({"id": ident, "owner": item["decision_owner"], "question": item["claim"],
                               "experiment": item["experiment"], "revisit_trigger": item["revisit_trigger"]})
    return {"status": "VISION_ACCEPTANCE_REVIEW_READY" if not unresolved else "PROPOSED_OR_PARTIALLY_ACCEPTED",
            "accepted_criteria_recorded": sorted(accepted), "unresolved": unresolved,
            "execution_authorized": False}


if __name__ == "__main__":
    raise SystemExit(run(validate))
