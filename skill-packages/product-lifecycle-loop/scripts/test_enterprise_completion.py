import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_progress_state as fixtures
import progress_state as ledger


class EnterpriseCompletionTests(unittest.TestCase):
    def setUp(self):
        self.h = fixtures.LedgerTests("runTest")
        self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.binding = {"state": str(self.h.root / "enterprise.sqlite"), "trust": str(self.h.root / "trust.json"),
            "trust_sha256": "0" * 64, "subject_sha256": "1" * 64,
            "parent_subject_sha256": ledger.digest(self.h.plan["subject"]), "run_id": "assessment", "delivery_engine": "codex-product-build-loop"}
        self.h.plan["enterprise_assurance"] = self.binding

    def finish_local_tasks(self):
        for task in self.h.plan["tasks"]:
            self.h.start(task["id"]); self.h.verify(task["id"])

    def test_local_success_cannot_skip_missing_enterprise_runtime_evidence(self):
        self.finish_local_tasks()
        result = ledger.next_action(self.h.state)
        self.assertEqual(result["status"], "BLOCKED_ENTERPRISE_ASSURANCE")
        self.assertFalse(result["enterprise_assurance"]["deployment_authorized"])

    def test_fixture_go_is_rechecked_and_does_not_complete_parent(self):
        tests = Path(__file__).resolve().parents[2] / "enterprise-ai-assurance-loop/tests"
        sys.path.insert(0, str(tests)); self.addCleanup(lambda: sys.path.remove(str(tests)))
        from support import Fixture
        from enterprise_assurance import engine as module
        from enterprise_assurance.common import digest
        f = Fixture(self.h.root / "child")
        f.populate(); f.engine.challenge("test-run", f.review())
        self.h.plan["goal"]["id"] = "test-goal"
        self.h.plan["criteria"] = ["acceptance"]
        self.h.plan["tasks"] = [{"id": "acceptance", "criteria": ["acceptance"], "depends_on": []}]
        self.binding.update(state=str(f.root / "state.sqlite"), trust=str(self.h.write("trust.json", f.trust)),
            trust_sha256=digest(f.trust), run_id="test-run", subject_sha256=f.plan["subject_sha"])
        self.finish_local_tasks()
        # Use the fixture's simulated clock. All actual evidence verification still runs.
        with patch.object(module, "Engine", return_value=f.engine):
            result = ledger.next_action(self.h.state)
        self.assertEqual(result["status"], "BLOCKED_ENTERPRISE_ASSURANCE")
        self.assertIn("ENTERPRISE_EVIDENCE_REQUIRED", result["enterprise_assurance"]["reason"])

    def test_changed_subject_requires_reassessment(self):
        changed = copy.deepcopy(self.h.plan["subject"]); changed["revision"] = "new"
        with self.assertRaisesRegex(ledger.LedgerError, "subject changed"):
            ledger.enterprise_completion(self.h.plan, changed)

    def test_binding_cannot_declare_multiple_engines_or_unbound_parent(self):
        for field, value in (("delivery_engine", "all"), ("parent_subject_sha256", "2" * 64)):
            plan = copy.deepcopy(self.h.plan); plan["enterprise_assurance"][field] = value
            with self.assertRaises(ledger.LedgerError): ledger.validate_plan(plan)


if __name__ == "__main__": unittest.main()
