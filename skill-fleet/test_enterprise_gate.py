import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill-packages/enterprise-ai-assurance-loop/tests"))
from support import Fixture
from enterprise_assurance.common import AssuranceError
from enterprise_gate import verify_parent


class ParentGateTests(unittest.TestCase):
    def test_fixture_go_cannot_clear_enterprise_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp); f.populate(); f.engine.challenge("test-run", f.review())
            with self.assertRaisesRegex(AssuranceError, "ENTERPRISE_EVIDENCE_REQUIRED"):
                verify_parent(f.engine, "test-run", "test-goal", ["acceptance"], "codex-product-build-loop", f.plan["subject_sha"])

    def test_parent_criteria_engine_and_subject_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp); f.populate(); f.engine.challenge("test-run", f.review())
            good = ("test-goal", ["acceptance"], "codex-product-build-loop", f.plan["subject_sha"])
            result = verify_parent(f.engine, "test-run", *good, enterprise_required=False)
            self.assertFalse(result["deployment_authorized"])
            for position, replacement in ((0, "other-goal"), (1, ["other-criterion"]), (2, "product-loop"), (3, "0" * 64)):
                args = list(good); args[position] = replacement
                with self.assertRaises(AssuranceError): verify_parent(f.engine, "test-run", *args, enterprise_required=False)

    def test_parent_boundary_rechecks_current_revocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp); f.populate(); f.engine.challenge("test-run", f.review())
            self.assertEqual(f.engine.decide("test-run")["decision"], "GO")
            f.trust["revoked_issuers"].append("collector")
            with self.assertRaises(AssuranceError):
                verify_parent(f.engine, "test-run", "test-goal", ["acceptance"], "codex-product-build-loop", f.plan["subject_sha"], False)


if __name__ == "__main__": unittest.main()
