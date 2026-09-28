"""Re-evaluate enterprise evidence at the parent boundary; never trust a saved GO."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill-packages/enterprise-ai-assurance-loop/scripts"))
from enterprise_assurance.common import AssuranceError, read, require
from enterprise_assurance.engine import Engine


def verify_parent(engine, run_id, goal, criteria, selected_engine, subject_sha, enterprise_required=True):
    result = engine.decide(run_id)
    require(result["parent_goal"] == goal and set(result["criterion_ids"]) == set(criteria), "parent goal or acceptance changed")
    require(result["delivery_engine"] == selected_engine and result["subject_sha"] == subject_sha, "parent engine/subject mismatch")
    require(result["decision"] == "GO", "enterprise assurance gate has not passed")
    require(not enterprise_required or result["proof"] == "ENTERPRISE", "ENTERPRISE_EVIDENCE_REQUIRED")
    return {"status": "ASSURANCE_ACCEPTED_WITHIN_SCOPE", "goal": goal, "decision": result,
            "deployment_authorized": False, "authority": "none"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("state", "trust", "trust-sha", "run-id", "goal", "engine", "subject-sha"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--criterion", action="append", required=True)
    args = parser.parse_args()
    try:
        engine = Engine(args.state, read(args.trust), args.trust_sha)
        result = verify_parent(engine, args.run_id, args.goal, args.criterion, args.engine, args.subject_sha)
        print(json.dumps(result, indent=2)); return 0
    except (AssuranceError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "authority": "none"})); return 1


if __name__ == "__main__": raise SystemExit(main())
