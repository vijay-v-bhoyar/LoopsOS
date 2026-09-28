"""Regression tests for owner 11's observed harm predicates, not live probes."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "enterprise-ai-assurance-loop" / "scripts"))
from enterprise_assurance.catalog import catalog, evaluate, applicable
from enterprise_assurance.common import AssuranceError

class OwnerTests(unittest.TestCase):
    def test_known_acceptable_and_harmful_observations(self):
        for case in catalog()[11]["cases"]:
            limits = {m["limit"]: 10 for m in case["metrics"] if "limit" in m}
            observed = {m["field"]: m.get("expected", 5) for m in case["metrics"]}
            self.assertEqual(evaluate(case, observed, limits), [])
            for metric in case["metrics"]:
                bad = dict(observed)
                expected = observed[metric["field"]]
                bad[metric["field"]] = (not expected) if type(expected) is bool else (11 if "limit" in metric else expected + 1)
                self.assertIn(metric["field"], evaluate(case, bad, limits))

    def test_missing_observation_is_not_success(self):
        for case in catalog()[11]["cases"]:
            with self.assertRaises(AssuranceError): evaluate(case, {}, {})

    def test_applicability_includes_unknown_frontier(self):
        self.assertTrue(applicable(11, {"frontier": "UNKNOWN", "autonomy": 0}))
        self.assertTrue(applicable(11, {"frontier": "OFF", "autonomy": 2}))

if __name__ == "__main__": unittest.main()
