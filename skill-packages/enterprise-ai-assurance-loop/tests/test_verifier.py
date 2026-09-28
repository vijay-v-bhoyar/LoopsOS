import copy
import tempfile
import unittest
from support import Fixture
from enterprise_assurance.common import AssuranceError, digest, loads
from enterprise_assurance.engine import Engine
from enterprise_assurance.trust import seal


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name)

    def test_positive_is_scoped_and_never_deployment_permission(self):
        self.f.populate(); self.f.engine.challenge("test-run", self.f.review())
        result = self.f.engine.decide("test-run")
        self.assertEqual(result["decision"], "GO")
        self.assertEqual(result["proof"], "FIXTURE")
        self.assertFalse(result["deployment_authorized"])
        self.assertEqual(result["observed_product_mode"], "UNKNOWN")
        self.assertEqual(len(result["coverage"]), 13)

    def test_missing_owners_cannot_pass(self):
        self.assertEqual(self.f.engine.decide("test-run")["decision"], "NO_GO")

    def test_forged_and_substituted_evidence_rejected(self):
        for attack in ("signature", "subject", "run", "nonce", "profile", "issuer"):
            with self.subTest(attack=attack):
                envelope, blobs = self.f.evidence(0)
                if attack == "signature": envelope["signature"] = "AAAA"
                elif attack == "issuer": envelope["issuer"] = "self-issued"
                elif attack == "subject": envelope["body"]["subject_sha"] = "0" * 64
                elif attack == "profile": envelope["body"]["profile_sha"] = "0" * 64
                else: envelope["body"]["run_id" if attack == "run" else "nonce"] = "other"
                with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", envelope, blobs)

    def test_signed_false_success_and_dropped_cases_rejected(self):
        for mutate in (
            lambda p: p["cases"].pop(),
            lambda p: p["cases"][0].update(outcome="PASS", observations={"seeded_assets_found": False, "coverage_gaps_declared": True, "detection_seconds": 0}),
            lambda p: p.update(case_manifest_sha="0" * 64),
            lambda p: p.update(trial_ids=["synthetic-1"]),
            lambda p: p.update(model_evidence_expires_at=9999),
            lambda p: p.update(scope="NOT_APPLICABLE"),
            lambda p: p.update(extra="unsupported"),
        ):
            envelope, blobs = self.f.evidence(0); payload = envelope["body"]["payload"]; mutate(payload)
            with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", self.f.sign("evidence", payload), blobs)

    def test_missing_raw_or_altered_bytes_rejected(self):
        envelope, blobs = self.f.evidence(0)
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", envelope, {})
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", envelope, {k: b"rewritten" for k in blobs})

    def test_retry_cannot_hide_prior_failure(self):
        e, b = self.f.evidence(1, fail=True); self.f.engine.ingest("test-run", e, b)
        self.f.populate(); self.f.engine.challenge("test-run", self.f.review())
        result = self.f.engine.decide("test-run")
        self.assertIn("UNRESOLVED_PRIOR_FAILURE:QUALITY-DENOMINATOR", result["reasons"])

    def test_duplicate_import_is_idempotent_not_new_authority(self):
        e, b = self.f.evidence(0)
        self.f.engine.ingest("test-run", e, b)
        self.assertEqual(self.f.engine.ingest("test-run", e, b)["status"], "ALREADY_INGESTED")
        e["body"]["payload"]["limitations"] = ["substituted"]
        e = seal(e["body"], e["issuer"], self.f.keys["collector"])
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", e, b)

    def test_same_person_two_names_is_not_independence(self):
        self.f.populate()
        self.f.trust["issuers"]["challenger"]["principal"] = "collector-principal"
        with self.assertRaises(AssuranceError): self.f.engine.challenge("test-run", self.f.review())

    def test_same_organization_is_not_second_line(self):
        self.f.populate()
        self.f.trust["issuers"]["challenger"]["organization_unit"] = "collector-unit"
        with self.assertRaises(AssuranceError): self.f.engine.challenge("test-run", self.f.review())

    def test_changed_manifest_invalidates_challenge(self):
        self.f.populate(); review = self.f.review()
        e, b = self.f.evidence(0); self.f.engine.ingest("test-run", e, b)
        with self.assertRaises(AssuranceError): self.f.engine.challenge("test-run", review)

    def test_veto_is_binding(self):
        self.f.populate(); self.f.engine.challenge("test-run", self.f.review("VETO"))
        self.f.engine.challenge("test-run", self.f.review())
        self.assertIn("INDEPENDENT_VETO", self.f.engine.decide("test-run")["reasons"])

    def test_test_signer_cannot_attest_enterprise(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, enterprise=True)
            e, b = f.evidence(0); e["body"]["payload"]["proof"] = "ENTERPRISE"
            with self.assertRaises(AssuranceError): f.engine.ingest("test-run", f.sign("evidence", e["body"]["payload"]), b)

    def test_revoked_signer_invalidates_existing_success(self):
        self.f.populate(); self.f.engine.challenge("test-run", self.f.review())
        self.assertEqual(self.f.engine.decide("test-run")["decision"], "GO")
        self.f.trust["revoked_issuers"] = ["collector"]
        self.assertEqual(self.f.engine.decide("test-run")["decision"], "NO_GO")

    def test_unknown_frontier_requires_owner_four_and_seven(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, product="knowledge")
            self.assertFalse(f.plan["owners"][7]["applicable"])
        self.f.subject["frontier"] = "UNKNOWN"
        # A caller cannot swap the run subject to submit an N/A under a different profile.
        e, b = self.f.evidence(7)
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", e, b)

    def test_unknown_fields_duplicate_keys_nonfinite_rejected(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(AssuranceError): loads(text)

    def test_recursive_loop_nesting_rejected(self):
        with self.assertRaises(AssuranceError):
            self.f.engine.admit("nested", self.f.subject, self.f.profile, "goal", ["one"], "product-loop", ["agentic-product-loop"])

    def test_unknown_trust_root_rejected(self):
        with self.assertRaises(AssuranceError): Engine(self.f.root / "other.db", self.f.trust, "0" * 64)

    def test_known_unaddressed_stays_visible_and_blocks(self):
        self.f.populate()
        self.f.engine.record_risk("test-run", self.f.sign("risk", self.f.risk()))
        self.f.engine.challenge("test-run", self.f.review())
        result = self.f.engine.decide("test-run")
        self.assertEqual(result["risks"][0]["treatment"], "EXPLICITLY_UNADDRESSED")
        self.assertIn("UNBOUNDED_EXPOSURE:risk-1", result["reasons"])

    def test_closed_word_without_evidence_is_not_closure(self):
        r = self.f.risk(); r.update(treatment="CLOSED", evidence="VERIFIED_CURRENT", gate_effect="NONE_WITH_CURRENT_EVIDENCE", exposure=0)
        self.f.engine.record_risk("test-run", self.f.sign("risk", r))
        self.assertIn("UNVERIFIED_CLOSURE:risk-1", self.f.engine.decide("test-run")["reasons"])

    def test_prior_signed_evidence_cannot_be_post_repair_retest(self):
        old, blobs = self.f.evidence(1)
        self.f.engine.record_risk("test-run", self.f.sign("risk", self.f.risk()))
        self.f.time += 100
        self.f.engine.operate("test-run", self.f.operation("REPAIR", "risk-1", digest("repair")))
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", old, blobs)
        old["body"]["payload"]["generation"] = 1
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", self.f.sign("evidence", old["body"]["payload"]), blobs)

    def test_decision_cannot_outlive_supporting_evidence(self):
        self.f.populate(); self.f.engine.challenge("test-run", self.f.review())
        result = self.f.engine.decide("test-run")
        self.assertLessEqual(result["permission_manifest"]["expires_at"], self.f.time + 1800)

    def test_new_signature_cannot_launder_pre_compromise_observations(self):
        old, blobs = self.f.evidence(0)
        self.f.time += 100; self.f.trust["evidence_not_before"] = self.f.time
        with self.assertRaises(AssuranceError): self.f.engine.ingest("test-run", self.f.sign("evidence", old["body"]["payload"]), blobs)


if __name__ == "__main__": unittest.main()
