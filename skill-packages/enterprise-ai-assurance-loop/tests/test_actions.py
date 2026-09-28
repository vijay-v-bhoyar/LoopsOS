import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import support
from enterprise_assurance.actions import ActionGateway
from enterprise_assurance.common import AssuranceError


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.gateway = ActionGateway(Path(self.temp.name) / "effects.db")
        self.policy = {"id": "p", "principal": "worker", "tenant": "tenant", "environment": "test", "operations": ["pay", "refund"],
                       "targets": ["account"], "epoch": 1, "enabled": True, "limits": {"enterprise": 10, "tenant": 10}}
        self.gateway.configure(self.policy)

    def action(self, number="one", units=3):
        return {"id": number, "principal": "worker", "tenant": "tenant", "environment": "test", "operation": "pay", "target": "account",
                "resource_revision": "rev1", "parameters": {"amount": units}, "units": units, "epoch": 1, "expires_at": 100}

    def reserve(self, action):
        token = self.gateway.approve("p", action, 1)
        return self.gateway.reserve("p", action, token, 1)

    def test_approval_binds_every_action_field(self):
        for key, value in {"tenant": "other", "target": "other", "units": 9, "resource_revision": "new", "parameters": {"amount": 99}}.items():
            action = self.action(key); token = self.gateway.approve("p", action, 1); action[key] = value
            with self.assertRaises(AssuranceError): self.gateway.reserve("p", action, token, 1)

    def test_business_idempotency_not_attempt_id(self):
        action = self.action(); self.reserve(action)
        self.assertEqual(self.gateway.reserve("p", action, "invalid-new-token", 2)["status"], "AUTHORIZED")
        action["units"] = 5
        with self.assertRaises(AssuranceError): self.gateway.reserve("p", action, "old", 2)

    def test_concurrent_reservations_do_not_exceed_shared_budget(self):
        def reserve(index):
            try: self.reserve(self.action(str(index))); return True
            except AssuranceError: return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(reserve, range(12)))
        self.assertEqual(sum(outcomes), 3)

    def test_unknown_effect_reserves_exposure_and_cannot_blind_retry(self):
        action = self.action(units=8); self.reserve(action)
        self.gateway.transition("one", "DISPATCHED", 2, "dispatch", "rev1")
        self.gateway.transition("one", "UNKNOWN", 3, "response-lost")
        with self.assertRaises(AssuranceError): self.reserve(self.action("retry", 3))
        self.assertEqual(self.gateway.reserve("p", action, "unused", 4)["status"], "UNKNOWN")

    def test_revocation_blocks_disconnected_worker_dispatch(self):
        self.reserve(self.action()); stopped = self.gateway.stop("p")
        self.assertFalse(stopped["external_cancellation_confirmed"])
        with self.assertRaises(AssuranceError): self.gateway.transition("one", "DISPATCHED", 3, "late-worker", "rev1")

    def test_resource_change_after_approval_denies_dispatch(self):
        self.reserve(self.action())
        with self.assertRaises(AssuranceError): self.gateway.transition("one", "DISPATCHED", 2, "dispatch", "rev2")

    def test_restart_keeps_business_budget(self):
        self.reserve(self.action(units=8))
        self.gateway = ActionGateway(Path(self.temp.name) / "effects.db")
        with self.assertRaises(AssuranceError): self.reserve(self.action("new", 3))

    def test_shared_policy_cannot_reset_enterprise_limit(self):
        self.reserve(self.action(units=8))
        other = copy.deepcopy(self.policy); other["id"] = "another"
        self.gateway.configure(other)
        action = self.action("new", 3); token = self.gateway.approve("another", action, 1)
        with self.assertRaises(AssuranceError): self.gateway.reserve("another", action, token, 2)

    def test_failed_partial_compensation_keeps_original_exposure(self):
        self.reserve(self.action(units=6)); self.gateway.transition("one", "DISPATCHED", 2, "dispatch", "rev1")
        self.gateway.transition("one", "COMMITTED", 3, "provider-commit")
        self.gateway.compensate("one", "REQUIRED", None, "customer-harm")
        with self.assertRaises(AssuranceError): self.gateway.compensate("one", "IN_PROGRESS", "missing", "refund")
        refund = self.action("refund", 2); refund["operation"] = "refund"; self.reserve(refund)
        self.gateway.compensate("one", "IN_PROGRESS", "refund", "refund-authorized")
        result = self.gateway.compensate("one", "PARTIAL", "refund", "partial-provider-reply")
        self.assertEqual(result["status"], "COMMITTED")
        self.gateway.compensate("one", "FAILED", "refund", "refund-failed")
        with self.assertRaises(AssuranceError): self.reserve(self.action("more", 3))


if __name__ == "__main__": unittest.main()
