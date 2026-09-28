"""Real-process fixtures plus negative contract and persistence tests."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DOMAIN = "assurance"
SCRIPT = "finding_ledger.py"


class OwnerLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.subject = dict(product="fixture", target="local", revision="r2", configuration="test")
        self.write("subject.json", self.subject)
        self.file("oracle.py", "import sys\nassert sys.argv[1] == 'fixed'\nprint('assertion passed')\n")
        self.file("regression.py", "assert 2 + 2 == 4\nprint('adjacent assertion passed')\n")
        self.file("baseline.txt", "broken")
        self.file("changed.txt", "fixed")
        self.file("acceptance.md", "Owner reviewed the current local evidence for bounded scope.")
        self.failure = self.probe("before", "oracle.py", "broken", "baseline.txt")
        self.original = self.probe("after", "oracle.py", "fixed", "changed.txt")
        self.regression = self.probe("adjacent", "regression.py", "fixed", "changed.txt")
        self.record = self.fixture()

    def file(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def write(self, name, value):
        self.file(name, json.dumps(value))

    def ref(self, name):
        return dict(path=name, sha256=hashlib.sha256((self.root / name).read_bytes()).hexdigest())

    def probe(self, name, oracle, argument, artifact):
        command = [sys.executable, "-B", str(self.root / oracle), argument]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.file(name + ".txt", result.stdout + result.stderr)
        now = datetime.now(timezone.utc)
        return dict(subject=self.subject.copy(), actor="verifier", at=(now - timedelta(seconds=1)).isoformat(),
                    expires=(now + timedelta(hours=1)).isoformat(), command=command,
                    exit_code=result.returncode, assertions=1, output=self.ref(name + ".txt"),
                    oracle=self.ref(oracle), artifacts=[self.ref(artifact)])

    def fixture(self):
        if DOMAIN == "build":
            return dict(id="R-1", parent_goal="G-1", criteria=["C-1"], mode="IMPLEMENT", max_attempts=3, events=[
                dict(kind="failure", id="A-1", criterion="C-1", category="product", hypothesis="wrong value", receipt=self.failure),
                dict(kind="repair", failure_id="A-1", owner="builder", diagnosis="value corrected", changes=[self.ref("changed.txt")]),
                dict(kind="verify", failure_id="A-1", criteria=["C-1"], original=self.original, regression=self.regression)])
        if DOMAIN == "assurance":
            return dict(id="F-1", parent_goal="G-1", criteria=["C-1"], mode="REMEDIATE_APPROVED_SCOPE", owner="owner", require_independent=True, events=[
                dict(kind="reproduction", receipt=self.failure, cause="wrong value", confidence="confirmed"),
                dict(kind="repair", owner="builder", changes=[self.ref("changed.txt")], rationale="restore expected value"),
                dict(kind="verify", criteria=["C-1"], original=self.original, regression=self.regression, acceptance=self.ref("acceptance.md"), acceptance_owner="owner", residual_risk="Local fixture only")])
        self.original["actor"] = "researcher"
        return dict(id="V-1", owner="founder", criteria=["C-1"], assumptions=[
            dict(id="A-1", claim="Chosen local format can be delivered", owner="researcher", affected_criteria=["C-1"], experiment="exercise file delivery", decision_owner="founder", revisit_trigger="format or subject changes")], events=[
                dict(kind="experiment", assumption_id="A-1", receipt=self.original, interpretation="Local test supports delivery"),
                dict(kind="decision", assumption_id="A-1", actor="founder", outcome="accepted", rationale="bounded delivery accepted", acceptance=self.ref("acceptance.md"), evidence_sha256=self.original["output"]["sha256"])])

    def invoke(self, record=None, append=None):
        if record is not None:
            self.write("record.json", record)
        command = [sys.executable, "-B", str(Path(__file__).with_name(SCRIPT)), str(self.root / "record.json"), "--subject", str(self.root / "subject.json")]
        if append is not None:
            self.write("event.json", append)
            command += ["--append", str(self.root / "event.json")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_real_process_evidence_ready_without_authority(self):
        self.assertNotEqual(self.failure["exit_code"], 0)
        self.assertEqual(self.original["exit_code"], 0)
        code, result = self.invoke(self.record)
        self.assertEqual(code, 0, result)
        self.assertIn("READY", result["status"])
        self.assertEqual(result["authority"], "none")

    def test_append_survives_new_process(self):
        last = self.record["events"].pop()
        code, before = self.invoke(self.record)
        self.assertEqual(code, 0, before)
        self.assertNotIn("READY", before["status"])
        code, after = self.invoke(append=last)
        self.assertEqual(code, 0, after)
        self.assertIn("READY", after["status"])
        self.assertEqual(self.invoke()[1], after)
        self.assertEqual(len(json.loads((self.root / "record.json").read_text())["events"]), len(self.record["events"]) + 1)

    def test_changed_artifact_rejected(self):
        self.file("changed.txt", "tampered")
        self.assertEqual(self.invoke(self.record)[0], 2)

    def test_changed_subject_invalidates_readiness(self):
        self.subject["revision"] = "r3"
        self.write("subject.json", self.subject)
        code, result = self.invoke(self.record)
        self.assertEqual(code, 0, result)
        self.assertNotIn("READY", result["status"])

    def test_no_assertions_not_evidence(self):
        self.original["assertions"] = 0
        self.assertEqual(self.invoke(self.record)[0], 2)

    def test_boolean_exit_code_rejected(self):
        self.original["exit_code"] = False
        self.assertEqual(self.invoke(self.record)[0], 2)

    def test_stale_receipt_keeps_history_and_withholds_readiness(self):
        now = datetime.now(timezone.utc)
        self.original["at"] = (now - timedelta(hours=2)).isoformat()
        self.original["expires"] = (now - timedelta(hours=1)).isoformat()
        code, result = self.invoke(self.record)
        self.assertEqual(code, 0, result)
        self.assertNotIn("READY", result["status"])

    def test_relative_escape_rejected(self):
        self.original["output"]["path"] = "../outside.txt"
        self.assertEqual(self.invoke(self.record)[0], 2)

    def test_competing_writer_lock_preserved(self):
        self.write("record.json", self.record)
        self.file("record.json.lock", "other writer")
        code, _ = self.invoke(append=self.record["events"][-1])
        self.assertEqual(code, 2)
        self.assertEqual((self.root / "record.json.lock").read_text(), "other writer")

    def test_rejected_append_preserves_record(self):
        self.write("record.json", self.record)
        before = (self.root / "record.json").read_bytes()
        code, _ = self.invoke(append={"kind": "forged-pass"})
        self.assertEqual(code, 2)
        self.assertEqual((self.root / "record.json").read_bytes(), before)
        self.assertFalse((self.root / "record.json.lock").exists())

    def test_empty_or_duplicate_criteria_rejected(self):
        for criteria in ([], ["C-1", "C-1"]):
            self.record["criteria"] = criteria
            self.assertEqual(self.invoke(self.record)[0], 2)

    def test_domain_specific_boundary(self):
        if DOMAIN == "build":
            self.record["criteria"].append("C-2")
            code, result = self.invoke(self.record)
            self.assertEqual(code, 0)
            self.assertEqual(result["unmet_criteria"], ["C-2"])
            self.assertFalse(result["parent_complete"])
        elif DOMAIN == "assurance":
            self.original["actor"] = "builder"
            self.assertEqual(self.invoke(self.record)[0], 2)
            self.original["actor"] = "verifier"
            self.record["mode"] = "ASSESS_AND_PLAN"
            self.assertEqual(self.invoke(self.record)[0], 2)
        else:
            self.record["events"][-1]["actor"] = "builder"
            self.assertEqual(self.invoke(self.record)[0], 2)
            self.record["events"][-1]["actor"] = "founder"
            self.record["events"][-1]["outcome"] = "deferred"
            code, result = self.invoke(self.record)
            self.assertEqual(code, 0)
            self.assertEqual(result["accepted_criteria_recorded"], [])

    def test_original_oracle_and_experiment_binding(self):
        if DOMAIN in {"build", "assurance"}:
            self.original["oracle"] = self.ref("regression.py")
        else:
            self.record["events"][-1]["evidence_sha256"] = "0" * 64
        self.assertEqual(self.invoke(self.record)[0], 2)

    def test_scope_or_attempt_boundary(self):
        if DOMAIN == "build":
            self.record["events"].extend([copy.deepcopy(self.record["events"][1])] * 3)
            self.assertEqual(self.invoke(self.record)[0], 2)
            self.record["events"] = self.record["events"][:3]
            self.record["mode"] = "TEST"
            self.assertEqual(self.invoke(self.record)[0], 2)
        elif DOMAIN == "assurance":
            self.record["events"][-1]["criteria"] = ["another criterion"]
            self.assertEqual(self.invoke(self.record)[0], 2)
        else:
            self.record["assumptions"].append(dict(self.record["assumptions"][0], id="A-2"))
            code, result = self.invoke(self.record)
            self.assertEqual(code, 0)
            self.assertEqual(result["accepted_criteria_recorded"], [])

    def test_changed_artifact_omitted_from_verification(self):
        if DOMAIN in {"build", "assurance"}:
            self.original["artifacts"] = [self.ref("baseline.txt")]
        else:
            self.record["assumptions"][0]["affected_criteria"] = ["unknown"]
        self.assertEqual(self.invoke(self.record)[0], 2)

    def test_new_work_invalidates_prior_readiness(self):
        if DOMAIN == "build":
            self.record["criteria"].append("C-2")
            self.record["events"][-1]["criteria"].append("C-2")
            self.record["events"].append(copy.deepcopy(self.record["events"][1]))
        elif DOMAIN == "assurance":
            self.record["events"].append(copy.deepcopy(self.record["events"][1]))
        else:
            self.record["events"].append(copy.deepcopy(self.record["events"][0]))
        code, result = self.invoke(self.record)
        self.assertEqual(code, 0, result)
        self.assertNotIn("READY", result["status"])
        self.assertEqual(result.get("verified_criteria", result.get("accepted_criteria_recorded")), [])


if __name__ == "__main__":
    unittest.main()

