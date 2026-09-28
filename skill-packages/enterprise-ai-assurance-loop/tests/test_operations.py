import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from support import Fixture
from enterprise_assurance.common import AssuranceError, digest, read
from enterprise_assurance.engine import Engine
from enterprise_assurance.operations import export_pack, help_receipt, register_schedule, request_help, tick


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name)

    def test_cancel_does_not_claim_product_stopped_or_allow_resume(self):
        result = self.f.engine.operate("test-run", self.f.operation("CANCEL"))
        self.assertEqual(result["observed_product_mode"], "UNKNOWN")
        with self.assertRaises(AssuranceError): self.f.engine.operate("test-run", self.f.operation("RESUME"))

    def test_revoked_pinned_profile_prevents_resume(self):
        self.f.engine.operate("test-run", self.f.operation("SUSPEND"))
        self.f.trust["revoked_profiles"] = [digest(self.f.profile)]
        with self.assertRaises(AssuranceError): self.f.engine.operate("test-run", self.f.operation("RESUME"))
        self.assertEqual(self.f.engine.inspect("test-run")["run"]["state"], "SUSPENDED")

    def test_clock_rollback_and_expired_budget_block(self):
        self.f.time -= 1
        with self.assertRaises(AssuranceError): self.f.engine.decide("test-run")
        self.f.time = 10000 + self.f.profile["run_seconds"]
        with self.assertRaises(AssuranceError): self.f.engine.decide("test-run")

    def test_repair_budget_and_evidence_invalidation_persist(self):
        risk = self.f.risk(); self.f.engine.record_risk("test-run", self.f.sign("risk", risk))
        for index in range(3):
            self.f.engine.operate("test-run", self.f.operation("REPAIR", "risk-1", digest(index)))
        state = self.f.engine.inspect("test-run")["run"]
        self.assertEqual(state["invalidated_owners"], list(range(13)))
        self.f.engine = Engine(self.f.root / "state.sqlite", self.f.trust, digest(self.f.trust), clock=lambda: self.f.time)
        with self.assertRaises(AssuranceError): self.f.engine.operate("test-run", self.f.operation("REPAIR", "risk-1", digest(4)))

    def test_repeated_patch_is_not_progress(self):
        self.f.engine.record_risk("test-run", self.f.sign("risk", self.f.risk()))
        self.f.engine.operate("test-run", self.f.operation("REPAIR", "risk-1", digest("same")))
        with self.assertRaises(AssuranceError): self.f.engine.operate("test-run", self.f.operation("REPAIR", "risk-1", digest("same")))

    def test_help_draft_delivery_and_response_are_distinct(self):
        self.f.engine.record_risk("test-run", self.f.sign("risk", self.f.risk()))
        request = {"schema": "enterprise-help/v1", "id": "help-1", "risk_id": "risk-1", "destination": "provider-owner",
            "request": "Obtain authorized route evidence", "evidence_refs": [], "risk_while_waiting": "High-impact route remains restricted",
            "deadline": self.f.time + 100, "wake_condition": "Authenticated evidence received and retested", "status": "DRAFT", "attempts": 0,
            "delivery_reference": "not-delivered"}
        self.assertFalse(request_help(self.f.engine, "test-run", request)["delivered"])
        request.update(status="DELIVERED", attempts=1, delivery_reference="test-adapter-receipt")
        help_receipt(self.f.engine, "test-run", self.f.sign("help", request, "help"))
        request.update(status="ACKNOWLEDGED")
        help_receipt(self.f.engine, "test-run", self.f.sign("help", request, "help"))
        request.update(status="RESOLVED")
        self.assertTrue(help_receipt(self.f.engine, "test-run", self.f.sign("help", request, "help"))["retest_required"])
        self.assertEqual(self.f.engine.decide("test-run")["decision"], "NO_GO")

    def test_schedule_budget_and_repeated_tick(self):
        spec = {"schema": "enterprise-schedule/v1", "id": "job", "due": self.f.time, "interval_seconds": 5, "max_dispatches": 1, "max_failures": 1, "lease_seconds": 30}
        register_schedule(self.f.engine, "test-run", spec)
        self.assertEqual(len(tick(self.f.engine)["dispatches"]), 1)
        self.assertEqual(tick(self.f.engine)["dispatches"], [])
        self.f.time += 10
        self.assertEqual(tick(self.f.engine)["dispatches"], [])
        with self.assertRaises(AssuranceError): register_schedule(self.f.engine, "test-run", spec)

    def test_failed_scheduler_goes_dead_letter(self):
        spec = {"schema": "enterprise-schedule/v1", "id": "job", "due": self.f.time, "interval_seconds": 5, "max_dispatches": 3, "max_failures": 1, "lease_seconds": 30}
        register_schedule(self.f.engine, "test-run", spec)
        with patch.object(self.f.engine, "decide", side_effect=AssuranceError("collector unavailable")):
            self.assertEqual(tick(self.f.engine)["dispatches"][0]["status"], "DEAD_LETTER")
        self.f.time += 10
        self.assertEqual(tick(self.f.engine)["dispatches"], [])

    def test_local_history_tamper_is_detected(self):
        with self.f.engine.store.tx() as db:
            db.execute("UPDATE events SET sha=?", ("0" * 64,))
        with self.assertRaises(AssuranceError): self.f.engine.inspect("test-run")

    def test_export_preserves_risk_and_escapes_active_content(self):
        risk = self.f.risk(); risk["mechanism"] = "<script>alert('unsafe')</script>"
        self.f.engine.record_risk("test-run", self.f.sign("risk", risk))
        self.f.engine.decide("test-run")
        dest = self.f.root / "export"
        export_pack(self.f.engine, "test-run", dest)
        report = (dest / "report.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;", report)
        pack = read(dest / "evidence-pack.json")
        self.assertTrue(any(a["kind"] == "risk" for a in pack["artifacts"]))


if __name__ == "__main__": unittest.main()
