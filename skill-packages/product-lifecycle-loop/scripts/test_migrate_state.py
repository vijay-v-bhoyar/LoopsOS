import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch

import migrate_state as migration
import progress_state as ledger
import test_progress_state as fixture_module


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.LedgerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture
        self.f.start()
        self.f.block()
        self.old = self.f.read()
        self.old_sha = ledger.file_hash(self.f.state)
        self.plan = copy.deepcopy(self.old["plan"])
        self.plan["limits"]["max_total_attempts"] += 2
        self.plan_path = self.f.write("new-plan.json", self.plan)
        proof = self.f.root / "review-evidence.txt"
        proof.write_text("Fixture reviewer inspected exact request and retained history.", encoding="utf-8")
        at = dt.datetime.now(dt.timezone.utc)
        self.review = {"kind": "limit_migration_review", "previous_state_sha256": self.old_sha,
                       "new_plan_sha256": ledger.digest(self.plan), "reviewer": "fixture-owner", "reason": "Two additional permitted local attempts",
                       "issued_at": (at-dt.timedelta(minutes=1)).isoformat(), "expires_at": (at+dt.timedelta(hours=1)).isoformat(),
                       "artifact": {"path": proof.name, "sha256": ledger.file_hash(proof)}}
        self.review_path = self.f.write("review.json", self.review)

    def run_migration(self):
        return migration.migrate(self.f.state, self.plan_path, self.review_path, self.old_sha, ledger.file_hash(self.review_path))

    def refresh_plan(self):
        self.f.write("new-plan.json", self.plan)
        self.review["new_plan_sha256"] = ledger.digest(self.plan)
        self.f.write("review.json", self.review)

    def test_preserves_history_counters_and_blockers(self):
        result = self.run_migration()
        self.assertEqual(result["status"], "MIGRATED")
        current = self.f.read()
        self.assertEqual(current["projection"], self.old["projection"])
        self.assertEqual(current["revision"], self.old["revision"])
        self.assertEqual([e["event"] for e in current["events"]], [e["event"] for e in self.old["events"]])
        with open(result["journal"], encoding="utf-8") as stream:
            journal = json.load(stream)
        self.assertEqual(journal["before"], self.old)
        self.assertEqual(ledger.next_action(self.f.state)["tasks"][0]["attempts"], 1)
        self.assertEqual(self.run_migration()["status"], "ALREADY_MIGRATED")

    def test_state_change_rejects_stale_review(self):
        self.f.help()
        before = self.f.state.read_bytes()
        with self.assertRaises(ledger.LedgerError): self.run_migration()
        self.assertEqual(self.f.state.read_bytes(), before)

    def test_goal_task_or_control_change_rejected(self):
        for key, value in (("goal", {"id":"new", "outcome":"weaker"}), ("controls", []), ("criteria", ["a"])):
            with self.subTest(key=key):
                self.plan = copy.deepcopy(self.old["plan"])
                self.plan["limits"]["max_total_attempts"] += 1
                self.plan[key] = value
                self.refresh_plan()
                with self.assertRaises(ledger.LedgerError): self.run_migration()

    def test_lower_or_unchanged_limits_rejected(self):
        for total in (1, 8):
            self.plan["limits"]["max_total_attempts"] = total
            self.refresh_plan()
            with self.assertRaises(ledger.LedgerError): self.run_migration()

    def test_expired_review_and_changed_proof_reject(self):
        self.review["expires_at"] = self.review["issued_at"]
        self.f.write("review.json", self.review)
        with self.assertRaises(ledger.LedgerError): self.run_migration()
        self.review["expires_at"] = (dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).isoformat()
        self.f.write("review.json", self.review)
        (self.f.root/"review-evidence.txt").write_text("changed")
        with self.assertRaises(ledger.LedgerError): self.run_migration()

    def test_pinned_review_and_engine_drift_reject(self):
        with self.assertRaises(ledger.LedgerError):
            migration.migrate(self.f.state, self.plan_path, self.review_path, self.old_sha, "0"*64)
        altered = self.f.read(); altered["engine_sha256"]="0"*64
        self.f.write("state.json", altered)
        self.old_sha=ledger.file_hash(self.f.state)
        self.review["previous_state_sha256"]=self.old_sha
        self.f.write("review.json",self.review)
        with self.assertRaises(ledger.LedgerError): self.run_migration()

    def test_active_work_rejects(self):
        self.f.start(task="b")
        self.old_sha=ledger.file_hash(self.f.state)
        self.review["previous_state_sha256"]=self.old_sha
        self.f.write("review.json",self.review)
        with self.assertRaises(ledger.LedgerError): self.run_migration()

    def test_interruption_after_journal_can_resume(self):
        original=ledger.atomic_write
        def interrupted(path, value):
            if path == self.f.state: raise OSError("injected interruption before commit")
            return original(path,value)
        with patch.object(ledger,"atomic_write",interrupted):
            with self.assertRaises(OSError): self.run_migration()
        self.assertEqual(self.f.read(),self.old)
        self.assertEqual(self.run_migration()["status"],"MIGRATED")


if __name__ == "__main__": unittest.main()
