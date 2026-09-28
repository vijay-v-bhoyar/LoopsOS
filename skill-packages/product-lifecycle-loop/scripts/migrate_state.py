"""Reviewed same-engine limit migration; preserve all work and a before/after journal.

Review identity must be authenticated by the caller. A JSON review grants no authority.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import progress_state as ledger


def sha_bytes(value):
    return hashlib.sha256(ledger.encoded(value) + b"\n").hexdigest()


def migrate(state_path, plan_path, review_path, expected_state_sha, expected_review_sha):
    path = ledger.checked_path(state_path)
    ledger.require(len(expected_state_sha) == 64 and len(expected_review_sha) == 64, "full input fingerprints required")
    with ledger.Lock(path):
        review_file = ledger.checked_path(review_path)
        ledger.require(ledger.file_hash(review_file) == expected_review_sha, "review changed")
        review = ledger.read_json(review_file)
        ledger.exact(review, ("kind", "previous_state_sha256", "new_plan_sha256", "reviewer", "reason", "issued_at", "expires_at", "artifact"))
        ledger.require(review["kind"] == "limit_migration_review", "wrong review kind")
        for field in ("reviewer", "reason"):
            ledger.string(review[field])
        at = ledger.timestamp(ledger.now())
        ledger.require(ledger.timestamp(review["issued_at"]) <= at < ledger.timestamp(review["expires_at"]), "review expired or future")
        ledger.artifact(path.parent, review["artifact"])
        plan = ledger.read_json(plan_path)
        ledger.validate_plan(plan)
        ledger.require(review["previous_state_sha256"] == expected_state_sha and review["new_plan_sha256"] == ledger.digest(plan), "review subject mismatch")
        journal_path = path.with_name(path.name + ".migration-" + expected_state_sha + ".json")
        current = ledger.read_json(path)
        current_sha = ledger.file_hash(path)
        journal = ledger.read_json(journal_path) if journal_path.exists() else None
        if journal:
            ledger.exact(journal, ("before_sha256", "after_sha256", "review_sha256", "before", "after", "review"))
            ledger.require(journal["before_sha256"] == expected_state_sha and journal["review_sha256"] == expected_review_sha, "migration journal conflicts")
            ledger.require(sha_bytes(journal["before"]) == expected_state_sha and sha_bytes(journal["after"]) == journal["after_sha256"], "migration journal integrity mismatch")
            ledger.require(journal["after"]["plan"] == plan and journal["review"] == review, "migration inputs changed")
            if current_sha == journal["after_sha256"]:
                ledger.replay(current, path.parent)
                return {"status": "ALREADY_MIGRATED", "revision": current["revision"], "journal": str(journal_path), "authority": "none"}
        ledger.require(current_sha == expected_state_sha, "state changed; review exact current state")
        projection = ledger.replay(current, path.parent)
        for task in projection["tasks"].values():
            ledger.require(task["status"] != "active" and not (task["operation"] and task["operation"]["effect"] == "unknown"), "reconcile or stop active work before migration")
        previous_plan = current["plan"]
        ledger.require({k: v for k, v in plan.items() if k != "limits"} == {k: v for k, v in previous_plan.items() if k != "limits"}, "this migration supports limits only; goal, tasks, subject and controls stay fixed")
        ledger.require(all(plan["limits"][k] >= v for k, v in previous_plan["limits"].items()), "migration cannot lower limits")
        ledger.require(plan["limits"] != previous_plan["limits"], "no limit change")
        after = copy.deepcopy(current)
        after["plan"] = plan
        after["plan_sha256"] = ledger.digest(plan)
        previous = after["plan_sha256"]
        for event in after["events"]:
            event["previous"] = previous
            event["sha256"] = ledger.digest({k: v for k, v in event.items() if k != "sha256"})
            previous = event["sha256"]
        ledger.replay(after, path.parent)
        ledger.require(after["projection"] == current["projection"], "migration changed work or counters")
        prepared = {"before_sha256": expected_state_sha, "after_sha256": sha_bytes(after), "review_sha256": expected_review_sha,
                    "before": current, "after": after, "review": review}
        if journal:
            ledger.require(prepared == journal, "prepared migration differs")
        else:
            ledger.atomic_write(journal_path, prepared)
        ledger.atomic_write(path, after)
        return {"status": "MIGRATED", "revision": after["revision"], "journal": str(journal_path), "authority": "none"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("state", "plan", "review", "expected-state-sha256", "expected-review-sha256"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    try:
        result = migrate(a.state, a.plan, a.review, a.expected_state_sha256, a.expected_review_sha256)
        print(json.dumps(result, indent=2))
        return 0
    except (ledger.LedgerError, OSError, RecursionError) as exc:
        print(json.dumps({"status": "MIGRATION_BLOCKED", "error": str(exc), "authority": "none"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
