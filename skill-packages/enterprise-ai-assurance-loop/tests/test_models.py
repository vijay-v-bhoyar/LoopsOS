import copy
import unittest
import support
from enterprise_assurance.models import assess_candidate
from enterprise_assurance.common import digest


class ModelTests(unittest.TestCase):
    def entry(self, model):
        return {"id": model, "provider": "synthetic", "route": "test-route", "identity_verified": True,
                "capabilities": {"context": 100, "tools": ["read"]}, "source": "https://example.invalid/synthetic-source",
                "published_at": 1, "reviewed_at": 2, "expires_at": 100, "deprecates_at": 200,
                "fallbacks": ["separately-reviewed-fallback"], "subject_sha": digest(model)}

    def decision(self, model):
        return {"subject_sha": digest(model), "decision": "GO", "proof": "ENTERPRISE", "permission_manifest": {"expires_at": 100}}

    def test_improvement_is_candidate_not_automatic_promotion(self):
        old, new = self.entry("old"), self.entry("new"); new["capabilities"]["context"] = 10000
        result = assess_candidate(old, new, 5, self.decision("new"))
        self.assertEqual(result["capability_changes"], ["context"])
        self.assertFalse(result["promotion_authorized"])
        self.assertTrue(result["fallback_review_required"])

    def test_expired_unknown_or_deprecated_routes_require_evidence(self):
        for field, value in (("expires_at", 3), ("deprecates_at", 3), ("identity_verified", False)):
            new = self.entry("new"); new[field] = value
            self.assertEqual(assess_candidate(self.entry("old"), new, 5, self.decision("new"))["status"], "EVIDENCE_REQUIRED")

    def test_fixture_benchmark_cannot_promote_live_model(self):
        decision = self.decision("new"); decision["proof"] = "FIXTURE"
        self.assertIn("ENTERPRISE_BENCHMARK_REQUIRED", assess_candidate(self.entry("old"), self.entry("new"), 5, decision)["reasons"])


if __name__ == "__main__": unittest.main()
