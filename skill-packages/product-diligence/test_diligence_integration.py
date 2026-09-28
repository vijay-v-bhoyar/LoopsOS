"""Integration regressions for diligence decisions and package-local evidence gates.

Evolution qualification is mocked only in decision-unit tests; its actual contract
is covered by test_model_evolution.py. Integrity/portable CLI tests use real files.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import derive as D
import diligence_check as C

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / "rules.json").read_text(encoding="utf-8"))
QUALIFIED = {"status": "QUALIFIED", "reasons": [], "candidate_decisions": [], "execution_authorized": False}


def strengths():
    return [{"id": f"S-{i}", "type": "strength", "title": "Control evidence",
             "surface": ["V-12"], "dimensions": ["D6"], "control": control,
             "severity": None, "evidence_mode": "cited-strength", "verifiability": "design",
             "status": "open", "citations": ["A-10:control-record"]}
            for i, control in enumerate(("MC-5", "MC-6", "MC-7"), 1)]


class DiligenceIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="diligence-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        artifact = self.root / "artifact.txt"
        artifact.write_text("Actual control design evidence.\n", encoding="utf-8")
        self.manifest = {"run": "run-001", "artifacts": {
            aid: {"path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
            for aid in ("A-10", "A-11", "A-06")},
            "model_pins": {"sweep": "provider/model-snapshot-a", "challenge": "provider/model-snapshot-b"},
            "params": {}}
        self.rows = strengths()

    def derive(self, evaluation=QUALIFIED):
        with patch("model_evolution.evaluate", return_value=evaluation):
            return D.derive_all(self.rows, RULES, self.manifest, [], base_dir=self.state)

    def d6(self, evaluation=QUALIFIED):
        return next(v for v in self.derive(evaluation)["verdicts"] if v["lens"] == "D6")

    def test_qualified_requires_cited_controls_and_reports_bounded_verdict(self):
        result = self.d6()
        self.assertEqual(result["verdict"], "Resilient within evaluated scope")
        self.assertEqual(result["rows"], [r["id"] for r in self.rows])

    def test_uncited_strength_cannot_qualify(self):
        for row in self.rows:
            row["citations"] = []
        self.assertNotEqual(self.d6()["verdict"], "Resilient within evaluated scope")
        report = C.Report()
        C._p2_citations(report, self.rows, set(self.manifest["artifacts"]))
        self.assertTrue(report.failed)

    def test_strength_wrong_evidence_mode_cannot_qualify(self):
        self.rows[0]["evidence_mode"] = "asserted"
        self.assertNotEqual(self.d6()["verdict"], "Resilient within evaluated scope")

    def test_unknown_majority_overrides_positive_rule(self):
        self.rows.extend({"id": f"U-{i}", "type": "unknown", "dimensions": ["D6"]} for i in range(100))
        self.assertEqual(self.d6()["verdict"], "Undetermined")

    def test_missing_evolution_does_not_claim_future_resilience(self):
        result = D.derive_all(self.rows, RULES, self.manifest, [], base_dir=self.state)
        self.assertEqual(next(v for v in result["verdicts"] if v["lens"] == "D6")["verdict"], "Undetermined")

    def test_not_ready_evolution_requires_adaptation(self):
        verdict = self.d6({"status": "NOT_READY", "reasons": ["stale evidence"], "execution_authorized": False})
        self.assertEqual(verdict["verdict"], "Needs core adaptation")

    def test_obsolescence_risk_blocks_despite_control_strengths(self):
        self.rows.append({"id": "R-1", "type": "risk", "status": "open", "severity": "critical",
                          "surface": ["S-11"], "dimensions": ["D6"]})
        self.assertEqual(self.d6()["verdict"], "High risk of obsolescence")
        self.assertEqual(self.d6({"status": "EVIDENCE_MISSING"})["verdict"], "High risk of obsolescence")

    def test_each_evolution_risk_blocks_positive_even_if_compensated(self):
        for surface in (f"E-{i:02}" for i in range(1, 9)):
            with self.subTest(surface=surface):
                self.rows = strengths() + [{"id": "R-1", "type": "risk", "status": "open", "severity": "high",
                    "surface": [surface], "dimensions": ["D6"], "compensating_control": {"cited": "A-10:x", "test": "A-10:test"}}]
                self.assertEqual(self.d6()["verdict"], "Needs core adaptation")

    def test_pending_proof_remains_a_blocker(self):
        row = {"id": "R-1", "type": "risk", "status": "fixed-pending-proof", "severity": "high",
               "surface": ["S-11"], "dimensions": ["D6"]}
        self.rows.append(row)
        self.assertTrue(D.is_open_risk(row))
        self.assertEqual(self.d6()["verdict"], "High risk of obsolescence")

    def test_expired_and_invalid_acceptance_fail_closed(self):
        for expiry in ("2000-01-01", "not-a-date"):
            with self.subTest(expiry=expiry):
                row = {"id": "R-1", "type": "risk", "status": "accepted",
                       "acceptance": {"owner": "owner", "expiry": expiry, "revisit_trigger": "model change"}}
                self.assertTrue(D.is_open_risk(row))
                report = C.Report()
                C._p8_lifecycle(report, [row])
                self.assertTrue(report.failed)

    def test_actual_artifact_integrity_then_byte_change(self):
        self.assertEqual(D.manifest_integrity_errors(self.manifest), [])
        Path(self.manifest["artifacts"]["A-10"]["path"]).write_text("Changed", encoding="utf-8")
        self.assertTrue(any("bytes changed" in x for x in D.manifest_integrity_errors(self.manifest)))

    def test_missing_artifact_and_fake_hash_fail(self):
        for metadata in ({"path": "missing", "sha256": "not-a-hash"}, {"path": str(self.root / "missing"), "sha256": "a" * 64}):
            self.manifest["artifacts"]["A-10"] = metadata
            self.assertTrue(D.manifest_integrity_errors(self.manifest))

    def test_required_model_pin_keys_and_placeholders(self):
        for pins in ({"other": "value"}, {"sweep": "<model>", "challenge": "snapshot"}, {"sweep": "snapshot", "challenge": ""}):
            self.manifest["model_pins"] = pins
            self.assertTrue(D.manifest_integrity_errors(self.manifest))

    def test_rules_subject_and_prompt_binding(self):
        self.manifest["rules_sha256"] = hashlib.sha256((HERE / "rules.json").read_bytes()).hexdigest()
        self.manifest["prompt_hashes"] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                            for name in ("sweep.md", "challenge.md")}
        self.manifest["subject"] = {k: "actual-value" for k in ("product", "revision", "environment", "configuration")}
        self.assertFalse(D.manifest_integrity_errors(self.manifest))
        for mutate in (lambda m: m.update(rules_sha256="0" * 64),
                       lambda m: m["subject"].update(revision=""),
                       lambda m: m["prompt_hashes"].update({"sweep.md": "0" * 64})):
            changed = copy.deepcopy(self.manifest)
            mutate(changed)
            self.assertTrue(D.manifest_integrity_errors(changed))

    def test_pending_revalidation_blocks_gate_but_not_payload_integrity(self):
        self.manifest["pending_revalidation"] = ["S-1"]
        self.assertFalse(D.manifest_integrity_errors(self.manifest))
        report = C.Report()
        C._p10_manifest(report, self.manifest)
        self.assertTrue(report.failed)

    def test_all_stored_verdict_fields_rederive(self):
        with patch("model_evolution.evaluate", return_value=QUALIFIED):
            original = D.derive_all(self.rows, RULES, self.manifest, [])["verdicts"]
            for field, value in (("rows", []), ("coverage", 1), ("confidence", "high")):
                with self.subTest(field=field):
                    stored = copy.deepcopy(original)
                    next(v for v in stored if v["lens"] == "D6")[field] = value
                    report = C.Report()
                    C._p4_rederivation(report, self.rows, RULES, self.manifest, [], stored)
                    self.assertTrue(report.failed)

    def test_p11_supplied_invalid_evidence_blocks_but_absent_allows_partial(self):
        report = C.Report()
        C._p11_evolution(report, self.rows, RULES, self.manifest, [], self.state)
        self.assertFalse(report.failed)
        self.manifest["model_evolution"] = {"path": "missing.json", "sha256": "a" * 64}
        report = C.Report()
        C._p11_evolution(report, self.rows, RULES, self.manifest, [], self.state)
        self.assertTrue(report.failed)

    def write_state(self):
        (self.state / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.state / "register.jsonl").write_text("\n".join(json.dumps(r) for r in self.rows) + "\n", encoding="utf-8")
        (self.state / "challenges.jsonl").write_text("", encoding="utf-8")

    def test_portable_cli_uses_own_rules_even_with_parent_shadow(self):
        self.write_state()
        package = self.root / "portable"
        package.mkdir()
        for name in ("derive.py", "model_evolution.py", "rules.json", "diligence_check.py"):
            shutil.copy2(HERE / name, package / name)
        (self.root / "rules.json").write_text('{"shadow": true}', encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(package / "derive.py"), "--dir", str(self.state)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = C.run(self.state, HERE / "rules.json")
        self.assertFalse(report.failed, report.results)
        derived = json.loads((self.state / "scorecard.json").read_text())
        self.assertEqual(derived["evolution"]["status"], "EVIDENCE_MISSING")

    def test_scorecard_content_tampering_is_blocked(self):
        expected = self.derive()
        stored = copy.deepcopy(expected)
        next(v for v in stored["scorecard"] if v["dimension"] == "Future resilience")["score"] = 999
        (self.state / "scorecard.json").write_text(json.dumps(stored), encoding="utf-8")
        report = C.Report()
        C._p9_rendering(report, self.state, RULES, expected)
        self.assertTrue(report.failed)


if __name__ == "__main__":
    unittest.main()
