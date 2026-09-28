from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.pilot_probes.authority_resolution import run as run_authority
from scripts.pilot_probes.proof_scope_freshness import run as run_freshness
from scripts.pilot_probes.replay_tool_idempotency import run as run_replay
from scripts.pilot_probes.routing_deduplication import run as run_routing
from scripts.pilot_probes.state_transition import run as run_transition
from scripts.run_pilot_probes import _validate_result, run_probes


ROOT = Path(__file__).resolve().parents[2]


class PilotProbeAdapterTests(unittest.TestCase):
    def test_fixture_runner_executes_every_registered_adapter(self) -> None:
        report = run_probes(ROOT)

        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["probe_count"], 5)
        self.assertEqual(report["case_count"], 9)
        self.assertEqual(report["external_calls"], 0)
        self.assertEqual(report["live_verification"], "unproven")

    def test_routing_rejects_multiple_primary_routes(self) -> None:
        result = run_routing(
            {
                "trigger_record": {
                    "trigger_id": "requirement-123",
                    "primary_loop_id": "loop-a",
                    "active_handlers": [],
                },
                "loop_graph": {"routes": {"requirement-123": ["loop-a", "loop-b"]}},
            }
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["outcome"], "BLOCKED")

    def test_authority_conflict_requires_blocked_progression(self) -> None:
        payload = {
            "loop_descriptor": {"authority": {"policy_owner_ref": "owner", "gate_owner_ref": "owner"}},
            "owner_registry": {
                "owners": [{"owner_ref": "owner", "status": "PILOT", "policy_owner": "policy", "gate_owner": "gate"}],
                "conflicts": ["conflict"],
                "progression_allowed": True,
            },
        }

        result = run_authority(payload)

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["outcome"], "BLOCKED")

    def test_transition_and_freshness_fail_closed(self) -> None:
        transition = run_transition(
            {
                "state_machine": {"allowed_transitions": {"TRIGGERED": ["QUALIFIED"]}},
                "state_event": {"from_state": "TRIGGERED", "to_state": "EFFECTIVENESS_PROVEN", "expected": "block"},
            }
        )
        freshness = run_freshness(
            {
                "proof_record": {
                    "scope": "loop-a",
                    "captured_at": "2026-01-01T00:00:00Z",
                    "sha256": "a" * 64,
                },
                "evidence_registry": {
                    "scope": "loop-a",
                    "freshness_policy": {"now": "2026-02-01T00:00:00Z", "max_age_seconds": 60},
                },
                "expected_decision": "reject",
            }
        )

        self.assertEqual(transition["status"], "PASS")
        self.assertEqual(transition["outcome"], "BLOCKED")
        self.assertEqual(freshness["status"], "PASS")
        self.assertEqual(freshness["outcome"], "BLOCKED")

    def test_replay_rejects_conflicting_payload(self) -> None:
        result = run_replay(
            {
                "operation_id": "operation-1",
                "tool_call_record": [
                    {"operation_id": "operation-1", "payload_hash": "a", "effect_id": "effect-1"},
                    {"operation_id": "operation-1", "payload_hash": "b", "effect_id": "effect-2", "decision": "REJECTED"},
                ],
                "expected": "conflict",
            }
        )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["outcome"], "BLOCKED")

    def test_replay_does_not_misclassify_same_payload_as_conflict(self) -> None:
        result = run_replay(
            {
                "operation_id": "operation-1",
                "tool_call_record": [
                    {"operation_id": "operation-1", "payload_hash": "a", "effect_id": "effect-1"},
                    {"operation_id": "operation-1", "payload_hash": "a", "effect_id": "effect-2", "decision": "REJECTED"},
                ],
                "expected": "conflict",
            }
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["outcome"], "BLOCKED")

    def test_fixture_is_valid_json(self) -> None:
        fixture = json.loads((ROOT / "evals" / "fixtures" / "pilot-sdlc-governance-os.json").read_text(encoding="utf-8"))

        self.assertEqual(fixture["fixture_kind"], "bounded_contract_fixture")
        self.assertEqual(len(fixture["probe_cases"]), 5)

    def test_runner_requires_local_proof_envelope(self) -> None:
        with self.assertRaisesRegex(ValueError, "proof_scope"):
            _validate_result(
                "probe",
                {
                    "schema_version": 1,
                    "probe_id": "probe",
                    "status": "PASS",
                    "checks": [{"passed": True}],
                    "external_calls": 0,
                    "proof_scope": "live",
                    "live_verification": "verified",
                },
            )

    def test_runner_rejects_fixture_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "external-fixture.json"
            fixture.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "inside the repository"):
                run_probes(ROOT, fixture)


if __name__ == "__main__":
    unittest.main()
