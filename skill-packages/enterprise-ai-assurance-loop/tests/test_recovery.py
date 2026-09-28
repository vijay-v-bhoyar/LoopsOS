import copy
import tempfile
import unittest
from support import Fixture
from enterprise_assurance.common import AssuranceError, digest
from enterprise_assurance.trust import seal


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name)

    def test_repair_fresh_retest_and_independent_closure_complete(self):
        f = self.f
        envelope, blobs = f.evidence(1, fail=True); f.engine.ingest("test-run", envelope, blobs)
        f.engine.record_risk("test-run", f.sign("risk", f.risk()))
        f.time += 10; f.engine.operate("test-run", f.operation("REPAIR", "risk-1", digest("bounded-fix")))
        refs = {}
        for owner in range(13):
            e, b = f.evidence(owner); refs[owner] = f.engine.ingest("test-run", e, b)["sha"]
        risk = f.risk(); risk.update(treatment="CLOSED", evidence="VERIFIED_CURRENT", gate_effect="NONE_WITH_CURRENT_EVIDENCE", exposure=0, evidence_refs=[refs[1]])
        f.engine.record_risk("test-run", f.sign("risk", risk)); f.engine.challenge("test-run", f.review())
        result = f.engine.decide("test-run")
        self.assertEqual(result["decision"], "GO")
        self.assertFalse(result["parent_goal_accepted"])
        self.assertTrue(result["assurance_criteria_satisfied"])

    def test_verified_timeboxed_acceptance_preserves_unaddressed_risk(self):
        f = self.f; f.populate()
        risk = f.risk(); risk.update(exposure=5, gate_effect="PERMIT_WITH_VALID_ACCEPTANCE", acceptance="VALID")
        risk_sha = f.engine.record_risk("test-run", f.sign("risk", risk))["sha"]
        with f.engine.store.tx() as db:
            ref = next(s for s, e in f.engine.store.artifacts(db, "test-run", "evidence") if e["body"]["payload"]["owner"] == 12)
        waiver = {"schema": "enterprise-waiver/v1", "risk_id": "risk-1", "risk_sha": risk_sha,
                  "case_ids": ["QUALITY-DENOMINATOR"], "compensating_evidence": [ref], "exposure_limit": 5,
                  "scope": "synthetic-journey", "reason": "Test bounded independent human review"}
        f.engine.waiver("test-run", f.sign("waiver", waiver, "executive", expires=f.time + 100))
        f.engine.challenge("test-run", f.review()); result = f.engine.decide("test-run")
        self.assertEqual(result["decision"], "GO")
        self.assertEqual(result["risks"][0]["treatment"], "EXPLICITLY_UNADDRESSED")
        self.assertEqual(result["permission_manifest"]["expires_at"], f.time + 100)
        f.time += 100
        self.assertNotEqual(f.engine.decide("test-run")["decision"], "GO")

    def test_explicit_original_challenger_can_resolve_veto(self):
        f = self.f; f.populate()
        veto = f.engine.challenge("test-run", f.review("VETO"))["sha"]
        approval = f.review(); approval["body"]["payload"]["resolves_vetoes"] = [veto]
        approval = seal(approval["body"], "challenger", f.keys["challenger"])
        f.engine.challenge("test-run", approval)
        self.assertEqual(f.engine.decide("test-run")["decision"], "GO")

    def test_new_run_cannot_reset_existing_parent_budget(self):
        f = self.f
        with self.assertRaises(AssuranceError):
            f.engine.admit("another", f.subject, f.profile, "test-goal", ["acceptance"], "codex-product-build-loop")

    def test_reviewed_subject_migration_carries_risks_and_deadline(self):
        f = self.f; f.engine.record_risk("test-run", f.sign("risk", f.risk()))
        previous = f.engine.inspect("test-run")["run"]
        new_subject = copy.deepcopy(f.subject); new_subject["manifest"]["source"] = digest("new-code")
        grant = f.operation("MIGRATE")
        grant["body"].update(run_id="continued", subject_sha=digest(new_subject))
        grant["body"]["payload"]["references"] = [digest(new_subject), digest(f.profile)]
        grant = seal(grant["body"], "operator", f.keys["operator"])
        f.engine.continue_run("test-run", "continued", new_subject, f.profile, grant)
        new = f.engine.inspect("continued")["run"]
        self.assertEqual(new["deadline"], previous["deadline"])
        self.assertEqual(new["continuation_of"], "test-run")
        self.assertIn("risk-1", new["inherited_risks"])
        self.assertEqual(f.engine.inspect("test-run")["run"]["state"], "CANCELLED")
        self.assertIn("INHERITED_RISK_REASSESSMENT_REQUIRED:risk-1", f.engine.decide("continued")["reasons"])
        with self.assertRaises(AssuranceError): f.engine.continue_run("test-run", "continued-again", new_subject, f.profile, grant)

    def test_second_continuation_cannot_drop_inherited_risk_or_failure(self):
        f = self.f
        e, b = f.evidence(1, fail=True); f.engine.ingest("test-run", e, b)
        f.engine.record_risk("test-run", f.sign("risk", f.risk()))
        parent_id = "test-run"
        for index in (1, 2):
            old = f.engine.inspect(parent_id)
            subject = copy.deepcopy(f.subject); subject["manifest"]["source"] = digest(index)
            grant = f.operation("MIGRATE")
            grant["body"].update(run_id=f"next-{index}", subject_sha=digest(subject), nonce=old["run"]["nonce"])
            grant["body"]["payload"].update(expected_state_sha=old["state_sha"], references=[digest(subject), digest(f.profile)])
            grant = seal(grant["body"], "operator", f.keys["operator"])
            f.engine.continue_run(parent_id, f"next-{index}", subject, f.profile, grant)
            parent_id = f"next-{index}"
        result = f.engine.decide(parent_id)
        self.assertIn("INHERITED_RISK_REASSESSMENT_REQUIRED:risk-1", result["reasons"])
        self.assertIn("UNRESOLVED_PRIOR_FAILURE:QUALITY-DENOMINATOR", result["reasons"])

    def test_decision_expires_with_risk_closure_attestation(self):
        f = self.f; f.populate()
        with f.engine.store.tx() as db:
            ref = next(s for s, e in f.engine.store.artifacts(db, "test-run", "evidence") if e["body"]["payload"]["owner"] == 1)
        risk = f.risk(); risk.update(treatment="MITIGATED_VERIFIED", evidence="VERIFIED_CURRENT", gate_effect="NONE_WITH_CURRENT_EVIDENCE", exposure=0, evidence_refs=[ref])
        f.engine.record_risk("test-run", f.sign("risk", risk, expires=f.time + 30))
        f.engine.challenge("test-run", f.review())
        self.assertEqual(f.engine.decide("test-run")["permission_manifest"]["expires_at"], f.time + 30)


if __name__ == "__main__": unittest.main()
