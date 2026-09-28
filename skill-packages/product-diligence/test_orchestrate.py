"""Real CLI workflows in isolated products; no model or provider calls."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="diligence-cli-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "isolated-skill"
        self.package.mkdir()
        for p in HERE.iterdir():
            if p.is_file() and not p.name.startswith("test_"):
                shutil.copy2(p, self.package / p.name)
        # A broken neighboring rules file must never be loaded.
        (self.root / "rules.json").write_text("not JSON", encoding="utf-8")
        self.product = self.root / "product"
        self.product.mkdir()
        self.write("artifact.txt", "Actual test artifact, not product evidence.")
        self.mapping = {a: "artifact.txt" for a in ("A-06", "A-10", "A-11", "A-22")}
        self.write("map.json", self.mapping)
        self.write("config.json", {"model_pins": {"sweep": "recorded-reviewer-a", "challenge": "recorded-reviewer-b"}})
        self.call("init", "--map", "map.json", "--config", "config.json")

    def write(self, path, value):
        p = self.product / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")
        return p

    def call(self, *args, ok=True):
        proc = subprocess.run([sys.executable, "-B", "-X", "utf8", str(self.package / "orchestrate.py"), *args],
                              cwd=self.product, capture_output=True, text=True)
        if ok:
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        else:
            self.assertNotEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc

    def row(self):
        return {"type": "unknown", "title": "Upgrade evidence missing", "statement": "Need measured comparison",
                "surface": ["E-03"], "dimensions": ["D6"], "severity": None,
                "impact_class": None, "evidence_mode": "missing", "control": None,
                "citations": [], "verifiability": "design"}

    def ingest(self):
        self.write("findings.json", [self.row()])
        self.call("ingest-findings", "findings.json")

    def finish(self):
        self.call("derive")
        self.call("challenge-payload")
        self.write("challenges.json", [])
        self.call("ingest-challenges", "challenges.json")
        self.call("reconcile")
        self.call("render")

    def test_relocated_pipeline_renders_missing_evolution_as_unknown(self):
        self.call("admit")
        self.call("sweep-payload", "--group", "model_evolution")
        payload = (self.product / ".diligence/payloads/sweep-model_evolution.md").read_text(encoding="utf-8")
        self.assertIn("A-22", payload)
        self.ingest()
        self.finish()
        sc = json.loads((self.product / ".diligence/scorecard.json").read_text(encoding="utf-8"))
        d6 = next(v for v in sc["verdicts"] if v["lens"] == "D6")
        self.assertEqual("Undetermined", d6["verdict"])
        self.assertFalse(sc["evolution"]["execution_authorized"])

    def test_changed_artifact_blocks_payload_before_rerun(self):
        self.write("artifact.txt", "Changed source")
        p = self.call("sweep-payload", ok=False)
        self.assertIn("artifact bytes changed", p.stderr)

    def test_revalidation_preserves_id_history_and_requires_fresh_challenge(self):
        self.ingest()
        self.finish()
        self.write("artifact.txt", "Changed source")
        self.call("rerun", "--map", "map.json")
        state = self.product / ".diligence"
        m = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
        rid = m["pending_revalidation"][0]
        self.assertTrue(list((state / "history").rglob("scorecard.md")))
        self.call("render", ok=False)
        row = self.row()
        row["revalidates"] = rid
        self.write("revalidated.json", [row])
        self.call("ingest-findings", "revalidated.json")
        self.call("render", ok=False)
        self.finish()
        rows = [json.loads(l) for l in (state / "register.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([rid], [r["id"] for r in rows])
        self.assertEqual("revalidated", rows[0]["history"][-1]["event"])

    def test_removed_artifact_and_changed_model_config_invalidate(self):
        self.ingest()
        self.write("map.json", {k: v for k, v in self.mapping.items() if k != "A-22"})
        self.write("next.json", {"model_pins": {"sweep": "new-reviewer", "challenge": "recorded-reviewer-b"}})
        self.call("rerun", "--map", "map.json", "--config", "next.json")
        m = json.loads((self.product / ".diligence/manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("A-22", m["artifacts"])
        self.assertTrue(m["pending_revalidation"])
        self.assertEqual("new-reviewer", m["model_pins"]["sweep"])

    def test_init_cannot_overwrite_existing_review(self):
        before = (self.product / ".diligence/manifest.json").read_bytes()
        self.call("init", "--map", "map.json", "--config", "config.json", ok=False)
        self.assertEqual(before, (self.product / ".diligence/manifest.json").read_bytes())

    def test_parameter_only_change_invalidates_and_explicit_null_clears(self):
        self.ingest()
        self.write("next.json", {"owner_roster": ["new-owner"], "release_calendar": {"beta": "supplied-release"}})
        self.call("rerun", "--map", "map.json", "--config", "next.json")
        state = self.product / ".diligence/manifest.json"
        m = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(["new-owner"], m["params"]["owner_roster"])
        self.assertTrue(m["pending_revalidation"])
        self.write("clear.json", {"release_calendar": None})
        self.call("rerun", "--map", "map.json", "--config", "clear.json")
        m = json.loads(state.read_text(encoding="utf-8"))
        self.assertIsNone(m["params"]["release_calendar"])
        self.assertEqual(["new-owner"], m["params"]["owner_roster"])

    def test_bad_sweep_batch_does_not_write_partial_results(self):
        self.write("findings.json", [self.row(), {"type": "risk"}])
        self.call("ingest-findings", "findings.json", ok=False)
        self.assertEqual(b"", (self.product / ".diligence/register.jsonl").read_bytes())

    def test_evolution_input_path_is_bound_under_state(self):
        self.write(".diligence/evolution/config.json", {"schema": "deliberately-incomplete"})
        digest = hashlib.sha256((self.product / ".diligence/evolution/config.json").read_bytes()).hexdigest()
        self.write("next.json", {"model_evolution": {"path": ".diligence/evolution/config.json", "sha256": digest}})
        self.call("rerun", "--map", "map.json", "--config", "next.json")
        m = json.loads((self.product / ".diligence/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("evolution/config.json", m["model_evolution"]["path"])
        self.call("evolution-check", ok=False)

    def test_qualified_evolution_pipeline_and_tamper_blocks_render(self):
        """Exercise real evaluator, bytes, CLI phases, pins and subject binding."""
        from datetime import datetime, timedelta, timezone
        from test_model_evolution import EvolutionTests

        fixture = EvolutionTests("test_actual_receipts_qualify_capability_and_candidate_without_authority")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        now = datetime.now(timezone.utc)
        window = {"observed_at": (now - timedelta(minutes=2)).isoformat(),
                  "expires_at": (now + timedelta(days=1)).isoformat()}
        # Refresh every time-bound receipt and recompute its real byte digest.
        # Nothing depends on a calendar date embedded in the unit-test fixture.
        for control, record in fixture.controls.items():
            name = f"{control}.json"
            proof = json.loads((fixture.root / name).read_bytes())
            proof.update(window)
            record["evidence"] = fixture.write(name, proof)
        fixture.config.update(window)
        refresh = fixture.config["refresh"]
        refresh["last_reviewed_at"] = (now - timedelta(minutes=1)).isoformat()
        refresh["next_review_at"] = (now + timedelta(hours=23)).isoformat()
        for source in refresh["official_sources"]:
            source.update(window)
        fixture.report.update(window)
        fixture.candidate["evaluation"] = fixture.write("evaluation.json", fixture.report)
        evolution_receipt = fixture.write("evolution.json", fixture.config)

        # A fresh product is needed because init intentionally refuses overwrite.
        self.product = self.root / "qualified-product"
        self.product.mkdir()
        state = self.product / ".diligence"
        state.mkdir()
        for artifact in fixture.root.iterdir():
            if artifact.is_file():
                shutil.copy2(artifact, state / artifact.name)
        self.write("artifact.txt", "Test reports: MC-5 scoped approval; MC-6 audit; MC-7 cancellation.")
        self.write("map.json", {**self.mapping, "A-22": ".diligence/evolution.json"})
        self.write("settings/assessment.json", {
            "subject": fixture.subject,
            "model_pins": {"sweep": "recorded-reviewer-a", "challenge": "recorded-reviewer-b"},
            # This path is relative to settings/assessment.json; init must bind
            # it relative to the manifest directory before evaluator admission.
            "model_evolution": {**evolution_receipt, "path": "../.diligence/evolution.json"},
        })
        self.call("init", "--map", "map.json", "--config", "settings/assessment.json")
        manifest = json.loads((state / "manifest.json").read_bytes())
        self.assertEqual("evolution.json", manifest["model_evolution"]["path"])
        self.assertEqual(fixture.subject, manifest["subject"])
        self.assertEqual({"sweep": "recorded-reviewer-a", "challenge": "recorded-reviewer-b"},
                         manifest["model_pins"])
        strengths = [
            {"type": "strength", "title": f"Exercised {control}",
             "statement": f"Supplied test report exercises {control}",
             "surface": ["V-12"], "dimensions": ["D6"], "severity": None,
             "impact_class": "controlled-autonomy", "evidence_mode": "cited-strength",
             "control": control, "citations": [f"A-10:artifact.txt#{control}"],
             "verifiability": "test-report"}
            for control in ("MC-5", "MC-6", "MC-7")
        ]
        self.write("strengths.json", strengths)
        self.call("ingest-findings", "strengths.json")
        self.finish()
        rows = [json.loads(line) for line in (state / "register.jsonl").read_text().splitlines()]
        self.assertEqual(3, len(rows), "Distinct controls must not deduplicate")
        scorecard = json.loads((state / "scorecard.json").read_bytes())
        d6 = next(verdict for verdict in scorecard["verdicts"] if verdict["lens"] == "D6")
        self.assertEqual("Resilient within evaluated scope", d6["verdict"])
        evolution = scorecard["evolution"]
        self.assertEqual("QUALIFIED", evolution["status"])
        self.assertFalse(evolution["execution_authorized"])
        self.assertFalse(evolution["capability_only"])
        self.assertEqual("QUALIFIED", evolution["candidate_decisions"][0]["status"])
        self.assertFalse(evolution["candidate_decisions"][0]["execution_authorized"])

        # A passing scorecard/challenge receipt cannot conceal changed proof bytes.
        (state / "policy_enforcement.json").write_text("tampered proof", encoding="utf-8")
        refused = self.call("render", ok=False)
        self.assertIn("hash mismatch", refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main()
