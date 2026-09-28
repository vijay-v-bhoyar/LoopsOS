"""Persistent repair episodes return verified criteria to their parent goal."""
from evidence_io import fields, word, strings, need, receipt, artifacts, is_current, run

CATEGORIES = {"product", "baseline", "environment", "dependency", "test", "capability", "authority", "unknown"}


def covers_verification(receipts, changes):
    verified = {(entry["path"], entry["sha256"])
                for value in receipts for entry in value["artifacts"]}
    need(all((entry["path"], entry["sha256"]) in verified for entry in changes),
         "verification receipts omit changed artifacts")


def validate(record, root, current):
    fields(record, "id parent_goal criteria mode max_attempts events")
    word(record["id"])
    word(record["parent_goal"])
    criteria = strings(record["criteria"])
    need(record["mode"] in {"IMPLEMENT", "DIAGNOSE", "TEST"}, "invalid build mode")
    need(type(record["max_attempts"]) is int and record["max_attempts"] > 0, "positive attempt limit required")
    need(isinstance(record["events"], list), "events must be a list")
    failures, covered, help_items, repair_attempts = {}, set(), [], 0
    for event in record["events"]:
        need(isinstance(event, dict), "event must be object")
        kind = event.get("kind")
        if kind == "failure":
            fields(event, "kind id criterion category hypothesis receipt")
            ident = word(event["id"])
            need(ident not in failures and len(failures) < record["max_attempts"], "duplicate failure or attempt cap reached")
            need(word(event["criterion"]) in criteria and word(event["category"]) in CATEGORIES, "unknown criterion/category")
            word(event["hypothesis"])
            receipt(event["receipt"], root, None, success=False, fresh=False)
            failures[ident] = {"event": event, "repair": None, "verified": False, "coverage": set()}
            covered.discard(event["criterion"])
        elif kind == "finding":
            fields(event, "kind id criterion category hypothesis observation receipt")
            ident = word(event["id"])
            need(ident not in failures and len(failures) < record["max_attempts"], "duplicate finding or attempt cap reached")
            need(word(event["criterion"]) in criteria and word(event["category"]) in CATEGORIES, "unknown criterion/category")
            word(event["hypothesis"])
            word(event["observation"])
            # An exploit or adversarial probe can exit successfully because it
            # reproduced the vulnerable behavior. Keep that observation
            # distinct from a failing regression test; verify both that the
            # same probe is rejected after repair and that secure acceptance
            # plus adjacent regressions pass.
            receipt(event["receipt"], root, None, success=True, fresh=False)
            failures[ident] = {"event": event, "repair": None, "verified": False, "coverage": set()}
            covered.discard(event["criterion"])
        elif kind in {"repair", "verify", "help"}:
            failure_id = word(event.get("failure_id"))
            need(failure_id in failures, "failure must exist")
            item = failures[failure_id]
            if kind == "repair":
                fields(event, "kind failure_id owner diagnosis changes")
                need(record["mode"] == "IMPLEMENT", "mode forbids recording an executed repair")
                repair_attempts += 1
                need(repair_attempts <= record["max_attempts"], "repair attempt cap reached")
                word(event["owner"])
                word(event["diagnosis"])
                artifacts(event["changes"], root)
                item["repair"] = event
                item["verified"] = False
                item["coverage"] = set()
                covered.discard(item["event"]["criterion"])
            elif kind == "help":
                fields(event, "kind failure_id owner question needs wake_condition")
                for key in ("owner", "question", "needs", "wake_condition"):
                    word(event[key])
                help_items.append(event)
            else:
                need(item["repair"] is not None, "repair evidence required")
                if item["event"]["kind"] == "finding":
                    fields(event, "kind failure_id criteria reproduction original regression")
                    receipt(event["reproduction"], root, None, success=False, fresh=False)
                    need(event["reproduction"]["oracle"] == item["event"]["receipt"]["oracle"], "finding reproduction oracle changed")
                    changed = {(entry["path"], entry["sha256"]) for entry in item["repair"]["changes"]}
                    reproduced = {(entry["path"], entry["sha256"]) for entry in event["reproduction"]["artifacts"]}
                    need(bool(changed & reproduced), "finding retest omits repaired runtime artifact")
                else:
                    fields(event, "kind failure_id criteria original regression")
                coverage = strings(event["criteria"])
                need(coverage <= criteria and item["event"]["criterion"] in coverage, "parent criterion missing")
                receipt(event["original"], root, None, fresh=False)
                receipt(event["regression"], root, None, fresh=False)
                covers_verification([event["original"], event["regression"]], item["repair"]["changes"])
                if item["event"]["kind"] == "finding":
                    item["verified"] = all(is_current(event[key], current) for key in ("reproduction", "original", "regression"))
                else:
                    need(event["original"]["oracle"] == item["event"]["receipt"]["oracle"], "original oracle changed")
                    item["verified"] = all(is_current(event[key], current) for key in ("original", "regression"))
                item["coverage"] = coverage if item["verified"] else set()
        else:
            raise ValueError("unknown repair event")
    pending = [ident for ident, item in failures.items() if not item["verified"]]
    covered = set().union(*(item["coverage"] for item in failures.values()))
    covered -= {failures[ident]["event"]["criterion"] for ident in pending}
    return {"status": "PARENT_REVIEW_READY" if not pending and covered == criteria else "REPAIR_OR_HELP_REQUIRED",
            "parent_goal": record["parent_goal"], "verified_criteria": sorted(covered),
            "unmet_criteria": sorted(criteria - covered), "pending_failures": pending,
            "attempts": len(failures), "repair_attempts": repair_attempts, "help": help_items, "parent_complete": False}


if __name__ == "__main__":
    raise SystemExit(run(validate))
