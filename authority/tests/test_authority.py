from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from loopos_authority.api import create_app
from loopos_authority.config import Settings
from loopos_authority.corpus import Corpus
from loopos_authority.engine import ExecutionEngine
from loopos_authority.models import Actor, ApprovalRequest, ConnectorEventRequest, CreateReleaseInitiativeRequest, CreateRunRequest, EvidenceRequest, ExecutionPlan, ProbeSpec
from loopos_authority.persistence import create_authority_store
from loopos_authority.postgres_store import PostgresConnection, split_postgres_script
from loopos_authority.store import AuthorityStore, Conflict, Forbidden
from loopos_authority.tools import ToolRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]


class PostgresConnectionContractTests(unittest.TestCase):
    def test_disables_prepared_statements_for_transaction_poolers(self) -> None:
        with patch("psycopg.connect") as connect:
            PostgresConnection("postgresql://authority.example/loopos")

        self.assertIsNone(connect.call_args.kwargs["prepare_threshold"])


class ProductionIdentityApiTests(unittest.TestCase):
    class IdentityVerifier:
        def verify(self, assertion: str) -> Actor:
            if assertion != "verified-identity-assertion":
                raise ValueError("Identity assertion is invalid.")
            return Actor(
                tenant_id="tenant-enterprise",
                user_id="oidc-user-42",
                name="Enterprise Approver",
                email="approver@example.com",
                role="Approver",
            )

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "identity.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=(),
            cors_origins=(),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_exchanges_a_verified_gateway_identity_for_a_short_lived_session(self) -> None:
        with TestClient(create_app(self.settings, identity_verifier=self.IdentityVerifier())) as client:
            response = client.post(
                "/v1/sessions",
                headers={"x-loopos-identity-token": "verified-identity-assertion"},
            )

            self.assertEqual(response.status_code, 200, response.text)
            session = response.json()
            self.assertLessEqual(session["expires_in"], 900)
            self.assertEqual(session["actor"]["tenant_id"], "tenant-enterprise")
            self.assertEqual(session["actor"]["user_id"], "oidc-user-42")
            self.assertEqual(session["actor"]["email"], "approver@example.com")
            verified = client.get(
                "/v1/session",
                headers={"authorization": f"Bearer {session['access_token']}"},
            )
            self.assertEqual(verified.status_code, 200)
            self.assertEqual(verified.json()["role"], "Approver")

    def test_production_readiness_fails_without_an_identity_provider(self) -> None:
        with TestClient(create_app(self.settings)) as client:
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Production identity is not configured.")

    def test_development_session_route_is_absent_in_production(self) -> None:
        with TestClient(create_app(self.settings)) as client:
            response = client.post("/v1/dev/sessions", json={})

        self.assertEqual(response.status_code, 404)

    def test_production_readiness_rejects_ephemeral_sqlite_persistence(self) -> None:
        with TestClient(create_app(self.settings, identity_verifier=self.IdentityVerifier())) as client:
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Production persistence must use Postgres.")


def enterprise_context() -> dict:
    return {
        "policy_decision_ref": "policy-decision-test",
        "sandbox_profile_ref": "sandbox-e2b-firecracker-production",
        "idempotency_scope": "tenant_workflow_tool_payload",
        "evidence_refs": ["workspace"],
    }


def plan(*, expected: str = "applied", rollback: bool = False, external: bool = False, tool: str = "record_action", arguments=None, enterprise: bool = False) -> ExecutionPlan:
    action_key = "action-test-key"
    rollback_action = {
        "tool": "record_action",
        "idempotency_key": "rollback-test-key",
        "arguments": {"operation": "compensate", "summary": "Undo governed action", "target_idempotency_key": action_key},
    } if rollback else None
    return ExecutionPlan.model_validate({
        "evidence": [{"evidence_id": "workspace", "kind": "workspace_snapshot", "source_ref": "workspace:test", "content": {"owner": "team-a"}}],
        "action": {
            "tool": tool,
            "idempotency_key": action_key,
            "external_effect": external,
            "arguments": arguments or {"operation": "apply", "summary": "Apply test improvement", "outputs": ["change-record"]},
        },
        "validation_probes": [{"probe_id": "validation-status", "kind": "json_equals", "path": "status", "expected": expected}],
        "effectiveness_probes": [{"probe_id": "effectiveness-status", "kind": "json_equals", "path": "status", "expected": "applied"}],
        "rollback": rollback_action,
        "enterprise_context": enterprise_context() if enterprise or external else None,
        "max_attempts": 3,
    })


def request(loop_id: str = "loop-001-product-discovery-loop", execution_plan: ExecutionPlan | None = None) -> CreateRunRequest:
    execution_plan = execution_plan or plan()
    high_risk_loop_numbers = [*range(66, 81), 89, *range(100, 105)]
    loop_number = int(loop_id.split("-", 2)[1])
    if loop_number in high_risk_loop_numbers and execution_plan.enterprise_context is None:
        execution_plan = ExecutionPlan.model_validate({**execution_plan.model_dump(mode="json"), "enterprise_context": enterprise_context()})
    return CreateRunRequest(
        workspace_id="workspace-test",
        loop_id=loop_id,
        title="Governed execution test",
        trigger="A production signal crossed its threshold.",
        requested_risk_tier="R1",
        plan=execution_plan,
    )


def connector_event_request(system: str = "github", external_id: str = "pr-123", observed_at: str = "2026-07-23T12:00:00+00:00") -> ConnectorEventRequest:
    return ConnectorEventRequest(
        workspace_id="workspace-release",
        system=system,
        event_kind="pull_request" if system == "github" else "release" if system == "jira" else "manual_note",
        external_id=external_id,
        label=f"{system} evidence {external_id}",
        url=f"https://example.local/{system}/{external_id}",
        observed_at=observed_at,
        payload={"status": "green", "source": system, "external_id": external_id},
    )


def release_request(source_event_ids: list[str] | None = None) -> CreateReleaseInitiativeRequest:
    return CreateReleaseInitiativeRequest(
        workspace_id="workspace-release",
        title="Prepare release 2026.08",
        description="Use Jira release scope and GitHub pull request evidence to govern a production deployment.",
        workflow_type="release",
        business_outcome="Reduce release meetings and audit prep while preserving approval evidence.",
        maturity="pilot",
        risk_tier="R3",
        status="planned",
        release_name="Release 2026.08",
        loop_bundle_ids=[
            "loop-008-requirements-traceability-loop",
            "loop-023-pull-request-review-loop",
            "loop-025-ci-pipeline-loop",
            "loop-036-release-readiness-loop",
            "loop-038-deployment-validation-loop",
            "loop-040-rollback-backup-and-recovery-loop",
        ],
        source_event_ids=source_event_ids or [],
        release_assurance={
            "operating_mode": "shadow_release",
            "connectors": [{"system": "jira", "mode": "shadow_read"}, {"system": "github", "mode": "shadow_read"}],
            "gates": [{"gate_id": "gate-release-readiness", "status": "blocked", "source_ref_ids": ["jira-release-scope", "github-change-set"]}],
            "proof_pack_scope": ["Jira release scope", "GitHub change evidence", "Gate decisions"],
        },
    )


def json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def webhook_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class AuthorityHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "authority.db",
            session_secret="test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=True,
            allowed_http_hosts=("enterprise.example",),
            cors_origins=("http://127.0.0.1:5173",),
            event_poll_seconds=0.01,
            retry_wait_seconds=0,
        )
        self.corpus = Corpus.load(REPO_ROOT)
        self.store = AuthorityStore(self.settings.database_path, self.corpus)
        self.tools = ToolRegistry(self.settings, self.store)
        self.engine = ExecutionEngine(self.corpus, self.store, self.tools)
        self.operator = Actor(tenant_id="tenant-a", user_id="operator-a", name="Operator", role="Operator")
        self.approver = Actor(tenant_id="tenant-a", user_id="approver-a", name="Approver", role="Approver")

    def tearDown(self) -> None:
        asyncio.run(self.tools.close())
        self.store.close()
        self.tempdir.cleanup()


class StoreAndEngineTests(AuthorityHarness):
    def test_records_connector_events_with_idempotency_and_audit(self) -> None:
        event = self.store.record_connector_event(self.operator, connector_event_request())
        replay = self.store.record_connector_event(self.operator, connector_event_request())

        self.assertEqual(replay.connector_event_id, event.connector_event_id)
        self.assertEqual(event.system, "github")
        self.assertEqual(event.payload_hash, replay.payload_hash)
        self.assertEqual(self.store.list_connector_events(self.operator.tenant_id, "workspace-release")[0].connector_event_id, event.connector_event_id)
        self.assertIn("CONNECTOR_EVENT_RECORDED", {record["event_type"] for record in self.store.events_after(self.operator.tenant_id, None)})

    def test_records_release_initiative_with_idempotency_and_audit(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        initiative = self.store.create_release_initiative(self.operator, release_request([connector.connector_event_id]), "release-create-key")
        replay = self.store.create_release_initiative(self.operator, release_request([connector.connector_event_id]), "release-create-key")

        self.assertEqual(replay.initiative_id, initiative.initiative_id)
        self.assertEqual(initiative.release_name, "Release 2026.08")
        self.assertEqual(initiative.source_event_ids, [connector.connector_event_id])
        self.assertEqual(initiative.release_assurance["operating_mode"], "shadow_release")
        self.assertEqual(initiative.freshness_summary["status"], "fresh")
        self.assertEqual(initiative.freshness_summary["source_event_count"], 1)
        self.assertEqual(initiative.freshness_summary["session_authenticated_count"], 1)
        self.assertEqual(initiative.readiness_verdict["verdict"], "NO_GO")
        self.assertIn("blocked", initiative.readiness_verdict["failing_reasons"][0])
        self.assertEqual(self.store.list_release_initiatives(self.operator.tenant_id, "workspace-release")[0].initiative_id, initiative.initiative_id)
        self.assertIn("RELEASE_INITIATIVE_RECORDED", {event["event_type"] for event in self.store.events_after(self.operator.tenant_id, None)})

        changed = release_request().model_copy(update={"release_name": "Release 2026.09"})
        with self.assertRaises(Conflict):
            self.store.create_release_initiative(self.operator, changed, "release-create-key")
        with self.assertRaisesRegex(Exception, "Unknown connector event IDs"):
            self.store.create_release_initiative(self.operator, release_request(["connector-event-missing"]), "release-missing-event")

    def test_release_initiative_marks_old_connector_evidence_stale(self) -> None:
        stale = self.store.record_connector_event(self.operator, connector_event_request(observed_at="2000-01-01T00:00:00+00:00"))
        initiative = self.store.create_release_initiative(self.operator, release_request([stale.connector_event_id]), "release-stale-evidence-key")

        self.assertEqual(initiative.freshness_summary["status"], "stale")
        self.assertEqual(initiative.freshness_summary["stale_event_ids"], [stale.connector_event_id])
        self.assertEqual(initiative.freshness_summary["max_age_seconds"], 86400)
        self.assertEqual(initiative.readiness_verdict["verdict"], "NO_GO")
        self.assertIn("connector evidence freshness is stale", initiative.readiness_verdict["failing_reasons"])

    def test_release_initiative_marks_all_passed_fresh_gates_go(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        ready_request = release_request([connector.connector_event_id])
        ready_request = ready_request.model_copy(update={
            "release_assurance": {
                **ready_request.release_assurance,
                "gates": [
                    {"gate_id": "gate-release-readiness", "status": "passed", "source_ref_ids": ["jira-release-scope"]},
                    {"gate_id": "gate-deployment-validation", "status": "passed", "source_ref_ids": ["github-change-set"]},
                ],
            }
        })
        initiative = self.store.create_release_initiative(self.operator, ready_request, "release-ready-key")

        self.assertEqual(initiative.readiness_verdict["verdict"], "GO")
        self.assertEqual(initiative.readiness_verdict["failing_reasons"], [])
        self.assertEqual(initiative.readiness_verdict["review_reasons"], [])

    def test_release_initiative_marks_review_gates_review_required(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        review_request = release_request([connector.connector_event_id])
        review_request = review_request.model_copy(update={
            "release_assurance": {
                **review_request.release_assurance,
                "gates": [{"gate_id": "gate-rollback", "status": "review_required", "source_ref_ids": ["manual-release-attestation"]}],
            }
        })
        initiative = self.store.create_release_initiative(self.operator, review_request, "release-review-key")

        self.assertEqual(initiative.readiness_verdict["verdict"], "REVIEW_REQUIRED")
        self.assertEqual(initiative.readiness_verdict["failing_reasons"], [])
        self.assertTrue(initiative.readiness_verdict["review_reasons"])

    def test_release_proof_pack_is_built_from_stored_authority_record(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        initiative = self.store.create_release_initiative(self.operator, release_request([connector.connector_event_id]), "release-proof-pack-key")
        proof_pack = self.store.build_release_proof_pack(self.operator.tenant_id, initiative.initiative_id, self.operator.user_id)

        self.assertEqual(proof_pack.initiative_id, initiative.initiative_id)
        self.assertEqual(proof_pack.readiness_verdict["verdict"], "NO_GO")
        self.assertIn("Decision Boundary", proof_pack.markdown)
        self.assertIn(connector.connector_event_id, proof_pack.markdown)
        self.assertEqual(len(proof_pack.markdown_hash), 64)
        proof_events = [event for event in self.store.events_after(self.operator.tenant_id, None) if event["event_type"] == "PROOF_PACK_GENERATED"]
        self.assertEqual(proof_events[-1]["actor_id"], self.operator.user_id)
        self.assertEqual(proof_events[-1]["payload"]["initiative_id"], initiative.initiative_id)
        self.assertEqual(proof_events[-1]["payload"]["markdown_hash"], proof_pack.markdown_hash)
        self.assertEqual(proof_events[-1]["payload"]["source_event_ids"], [connector.connector_event_id])
        self.assertEqual(proof_events[-1]["payload"]["readiness_verdict"], "NO_GO")
        replayed = self.store.build_release_proof_pack(self.operator.tenant_id, initiative.initiative_id, self.operator.user_id)
        self.assertEqual(replayed.markdown_hash, proof_pack.markdown_hash)
        proof_events = [event for event in self.store.events_after(self.operator.tenant_id, None) if event["event_type"] == "PROOF_PACK_GENERATED"]
        self.assertEqual(len(proof_events), 2)
        self.assertEqual(proof_events[-1]["payload"]["markdown_hash"], proof_pack.markdown_hash)
        self.assertNotIn("Generated at:", proof_pack.markdown)

    def test_external_http_actions_cannot_downgrade_their_risk_flag(self) -> None:
        document = plan().model_dump(mode="json")
        document["action"] = {
            "tool": "http_json_action",
            "idempotency_key": "downgraded-action-key",
            "external_effect": False,
            "arguments": {"endpoint": "https://enterprise.example/change", "method": "POST", "body": {}},
        }
        with self.assertRaisesRegex(ValidationError, "always an external-effect action"):
            ExecutionPlan.model_validate(document)

    def test_authority_uses_the_verified_vendored_standard_hash(self) -> None:
        expected = hashlib.sha256((REPO_ROOT / "standards" / "production-grade-continuous-improvement-loop.md").read_bytes()).hexdigest()
        self.assertEqual(self.corpus.standard_hash, expected)

    def test_executes_a_durable_loop_and_proves_effectiveness(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-test-001")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))

        completed = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(completed.state, "EFFECTIVENESS_PROVEN")
        self.assertEqual(completed.runner_status, "completed")
        self.assertEqual(completed.output["action"]["status"], "applied")
        self.assertNotEqual(completed.output["standard_hash"], "")
        evidence = self.store.list_evidence(run.tenant_id, run.run_id)
        self.assertEqual(evidence[0]["evidence_id"], "workspace")
        valid, count, invalid = self.store.verify_audit_chain(run.tenant_id)
        self.assertTrue(valid)
        self.assertGreater(count, 10)
        self.assertIsNone(invalid)

    def test_create_idempotency_replays_only_the_same_payload(self) -> None:
        original = self.store.create_run(self.operator, request(), "same-create-key")
        replay = self.store.create_run(self.operator, request(), "same-create-key")
        self.assertEqual(replay.run_id, original.run_id)

        changed = request().model_copy(update={"trigger": "A different production signal."})
        with self.assertRaises(Conflict):
            self.store.create_run(self.operator, changed, "same-create-key")
        self.assertIn("IDEMPOTENCY_KEY_CONFLICT", {event["event_type"] for event in self.store.events_after(original.tenant_id, original.run_id)})

    def test_high_risk_execution_waits_for_payload_bound_approval(self) -> None:
        run = self.store.create_run(self.operator, request("loop-069-tool-execution-validation-loop"), "create-high-risk")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))
        waiting = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(waiting.state, "PLANNED")
        self.assertEqual(waiting.runner_status, "awaiting_approval")

        with self.assertRaises(Forbidden):
            self.store.approve(self.operator, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Operator cannot approve."))
        with self.assertRaises(Conflict):
            self.store.approve(self.approver, run.run_id, ApprovalRequest(payload_hash="0" * 64, decision_reason="Wrong payload."))
        denied_events = self.store.events_after(run.tenant_id, run.run_id)
        self.assertIn("APPROVE_AND_SWAP_DENIED", {event["event_type"] for event in denied_events})

        self.store.approve(self.approver, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Evidence and action scope reviewed."))
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))
        self.assertEqual(self.store.get_run(run.tenant_id, run.run_id).state, "EFFECTIVENESS_PROVEN")

    def test_high_risk_execution_requires_enterprise_runtime_context(self) -> None:
        high_risk_request = CreateRunRequest(
            workspace_id="workspace-test",
            loop_id="loop-069-tool-execution-validation-loop",
            title="Governed execution missing enterprise context",
            trigger="A high-risk action was requested.",
            requested_risk_tier="R1",
            plan=plan(),
        )

        with self.assertRaisesRegex(Conflict, "enterprise_context"):
            self.store.create_run(self.operator, high_risk_request, "create-missing-enterprise-context")

    def test_rejection_blocks_the_exact_payload_and_is_audited(self) -> None:
        run = self.store.create_run(self.operator, request("loop-069-tool-execution-validation-loop"), "create-rejected")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))

        with self.assertRaises(Conflict):
            self.store.reject(self.approver, run.run_id, ApprovalRequest(payload_hash="0" * 64, decision_reason="Wrong payload."))
        self.store.reject(self.approver, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Control evidence is incomplete."))

        rejected = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(rejected.state, "BLOCKED")
        self.assertEqual(rejected.runner_status, "failed")
        event_types = {event["event_type"] for event in self.store.events_after(run.tenant_id, run.run_id)}
        self.assertIn("REJECT_AND_SWAP_DENIED", event_types)
        self.assertIn("APPROVAL_REJECTED", event_types)
        self.assertIn("RUN_RELEASED", event_types)
        with self.assertRaises(Conflict):
            self.store.approve(self.approver, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Cannot reverse terminal history."))

    def test_expired_approval_can_be_renewed_without_overwriting_history(self) -> None:
        run = self.store.create_run(self.operator, request("loop-069-tool-execution-validation-loop"), "create-renewed-approval")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))
        first = self.store.approve(self.approver, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Initial approval."))
        self.store.connection.execute("UPDATE approvals SET expires_at = '2000-01-01T00:00:00+00:00' WHERE approval_id = ?", (first,))

        renewed = self.store.approve(self.approver, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Renewed after expiry."))

        self.assertNotEqual(first, renewed)
        approvals = self.store.connection.execute("SELECT approval_id FROM approvals WHERE run_id = ? ORDER BY created_at", (run.run_id,)).fetchall()
        self.assertEqual(len(approvals), 2)
        self.assertEqual(self.store.consume_approval(run.tenant_id, run.run_id, run.payload_hash), renewed)

    def test_failed_validation_runs_compensation_and_preserves_terminal_history(self) -> None:
        failing = plan(expected="not-applied", rollback=True)
        run = self.store.create_run(self.operator, request(execution_plan=failing), "create-rollback")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))

        rolled_back = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(rolled_back.state, "ROLLED_BACK")
        self.assertEqual(rolled_back.output["action"]["status"], "applied")
        self.assertEqual(rolled_back.output["validation"][0]["passed"], False)
        self.assertEqual(rolled_back.output["rollback"]["status"], "compensated")
        with self.assertRaises(Conflict):
            self.store.claim_run(run.tenant_id, run.run_id)

        recovery = self.store.create_run(
            self.operator,
            CreateRunRequest(
                workspace_id=run.workspace_id,
                loop_id=run.loop_id,
                title="Recovery",
                trigger="Recover rolled-back run",
                requested_risk_tier=run.risk_tier,
                plan=plan(),
            ),
            "recover-rollback",
            recovery_of=run.run_id,
        )
        self.assertNotEqual(recovery.run_id, run.run_id)
        self.assertEqual(recovery.recovery_of, run.run_id)

    def test_audit_rows_cannot_be_modified_or_deleted(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-audit")
        with self.assertRaises(Conflict):
            self.store.transition(run.tenant_id, run.run_id, "EFFECTIVENESS_PROVEN", self.operator.user_id)
        self.assertIn("ILLEGAL_TRANSITION_DENIED", {event["event_type"] for event in self.store.events_after(run.tenant_id, run.run_id)})
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.connection.execute("UPDATE audit_events SET event_type = 'TAMPERED' WHERE run_id = ?", (run.run_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.connection.execute("DELETE FROM audit_events WHERE run_id = ?", (run.run_id,))

    def test_http_tool_retries_retryable_failures_with_one_idempotency_key(self) -> None:
        calls = []

        def handler(request_value: httpx.Request) -> httpx.Response:
            calls.append(request_value)
            if len(calls) < 3:
                return httpx.Response(503, json={"error": "temporary"})
            return httpx.Response(200, json={"change_id": "change-123"})

        retry_settings = Settings(
            repo_root=REPO_ROOT,
            database_path=self.settings.database_path,
            session_secret=self.settings.session_secret,
            allow_dev_auth=True,
            allowed_http_hosts=("localhost",),
            cors_origins=self.settings.cors_origins,
            retry_wait_seconds=0,
        )
        retry_tools = ToolRegistry(retry_settings, self.store, transport=httpx.MockTransport(handler))
        execution_plan = plan(
            rollback=True,
            external=True,
            tool="http_json_action",
            arguments={"endpoint": "http://localhost/change", "method": "POST", "body": {"enabled": True}},
        )
        run = self.store.create_run(self.operator, request(execution_plan=execution_plan), "create-http-retry")
        result = asyncio.run(retry_tools.execute_action(run.tenant_id, run.run_id, execution_plan.action, 3))
        asyncio.run(retry_tools.close())

        self.assertEqual(result["response"]["change_id"], "change-123")
        self.assertEqual(len(calls), 3)
        self.assertEqual({item.headers["idempotency-key"] for item in calls}, {"action-test-key"})

    def test_connected_evidence_and_probes_retry_transient_http_failures(self) -> None:
        attempts = {"evidence": 0, "probe": 0}

        def handler(request_value: httpx.Request) -> httpx.Response:
            key = "evidence" if request_value.url.path == "/evidence" else "probe"
            attempts[key] += 1
            if attempts[key] < 3:
                return httpx.Response(503, json={"error": "temporary"})
            return httpx.Response(200, json={"status": "active", "source": "enterprise"})

        connector_settings = Settings(
            repo_root=REPO_ROOT,
            database_path=self.settings.database_path,
            session_secret=self.settings.session_secret,
            allow_dev_auth=True,
            allowed_http_hosts=("localhost",),
            cors_origins=self.settings.cors_origins,
            retry_wait_seconds=0,
        )
        connector_tools = ToolRegistry(connector_settings, self.store, transport=httpx.MockTransport(handler))
        run = self.store.create_run(self.operator, request(), "create-http-read-retry")
        evidence = asyncio.run(connector_tools.collect_evidence(run.tenant_id, run.run_id, EvidenceRequest(evidence_id="connected", kind="http_json", source_ref="http://localhost/evidence")))
        passed, detail = asyncio.run(connector_tools.run_probe(ProbeSpec(probe_id="connected-status", kind="http_json_equals", path="status", expected="active", endpoint="http://localhost/probe"), {}, []))
        asyncio.run(connector_tools.close())

        self.assertEqual(evidence["content"]["source"], "enterprise")
        self.assertTrue(passed, detail)
        self.assertEqual(attempts, {"evidence": 3, "probe": 3})

    def test_connector_urls_reject_embedded_credentials(self) -> None:
        with self.assertRaisesRegex(Exception, "embedded credentials"):
            asyncio.run(self.tools.collect_evidence(
                "tenant-a",
                "run-never-dispatched",
                EvidenceRequest(evidence_id="credentialed", kind="http_json", source_ref="https://user:password@enterprise.example/evidence"),
            ))

    def test_external_connector_executes_probes_and_compensates_failed_validation(self) -> None:
        calls: list[tuple[str, str, str | None]] = []
        status = {"value": "active"}

        def handler(request_value: httpx.Request) -> httpx.Response:
            calls.append((request_value.method, request_value.url.path, request_value.headers.get("authorization")))
            if request_value.url.path == "/change":
                return httpx.Response(200, json={"change_id": "change-123"})
            if request_value.url.path == "/compensate":
                return httpx.Response(200, json={"compensated": True})
            return httpx.Response(200, json={"status": status["value"]})

        connector_settings = Settings(
            repo_root=REPO_ROOT,
            database_path=self.settings.database_path,
            session_secret=self.settings.session_secret,
            allow_dev_auth=True,
            allowed_http_hosts=("localhost",),
            cors_origins=self.settings.cors_origins,
            connector_bearer_tokens={"localhost": "server-only-token"},
            retry_wait_seconds=0,
        )
        connector_tools = ToolRegistry(connector_settings, self.store, transport=httpx.MockTransport(handler))
        connector_engine = ExecutionEngine(self.corpus, self.store, connector_tools)

        def connector_plan(key: str) -> ExecutionPlan:
            return ExecutionPlan.model_validate({
                "evidence": [{"evidence_id": "workspace", "kind": "workspace_snapshot", "source_ref": "workspace:test", "content": {"owner": "team-a"}}],
                "action": {"tool": "http_json_action", "idempotency_key": f"action-{key}", "external_effect": True, "arguments": {"endpoint": "http://localhost/change", "method": "POST", "body": {"enabled": True}}},
                "validation_probes": [{"probe_id": "validation-status", "kind": "http_json_equals", "path": "status", "expected": "active", "endpoint": "http://localhost/status"}],
                "effectiveness_probes": [{"probe_id": "effectiveness-status", "kind": "http_json_equals", "path": "status", "expected": "active", "endpoint": "http://localhost/status"}],
                "rollback": {"tool": "http_json_action", "idempotency_key": f"rollback-{key}", "external_effect": True, "arguments": {"endpoint": "http://localhost/compensate", "method": "POST", "body": {"enabled": False}}},
                "enterprise_context": enterprise_context(),
                "max_attempts": 3,
            })

        success = self.store.create_run(self.operator, request(execution_plan=connector_plan("success")), "create-http-success")
        asyncio.run(connector_engine.execute(success.tenant_id, success.run_id))
        self.store.approve(self.approver, success.run_id, ApprovalRequest(payload_hash=success.payload_hash, decision_reason="Connector scope and rollback reviewed."))
        asyncio.run(connector_engine.execute(success.tenant_id, success.run_id))
        self.assertEqual(self.store.get_run(success.tenant_id, success.run_id).state, "EFFECTIVENESS_PROVEN")
        self.assertEqual([path for _, path, _ in calls], ["/change", "/status", "/status"])
        self.assertEqual({authorization for _, _, authorization in calls}, {"Bearer server-only-token"})

        calls.clear()
        status["value"] = "pending"
        failed = self.store.create_run(self.operator, request(execution_plan=connector_plan("failed")), "create-http-failed")
        asyncio.run(connector_engine.execute(failed.tenant_id, failed.run_id))
        self.store.approve(self.approver, failed.run_id, ApprovalRequest(payload_hash=failed.payload_hash, decision_reason="Failure-path compensation reviewed."))
        asyncio.run(connector_engine.execute(failed.tenant_id, failed.run_id))
        asyncio.run(connector_tools.close())

        self.assertEqual(self.store.get_run(failed.tenant_id, failed.run_id).state, "ROLLED_BACK")
        self.assertEqual(self.store.get_run(failed.tenant_id, failed.run_id).output["rollback"]["result"]["response"]["compensated"], True)
        self.assertEqual([path for _, path, _ in calls], ["/change", "/status", "/compensate"])

    def test_restart_reconciliation_requeues_incomplete_runs(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-restart")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        self.store.connection.execute("UPDATE runs SET runner_status = 'running' WHERE run_id = ?", (run.run_id,))

        recovered = self.store.requeue_incomplete_runs()

        self.assertEqual(recovered, [(run.tenant_id, run.run_id)])
        self.assertEqual(self.store.get_run(run.tenant_id, run.run_id).runner_status, "queued")
        self.assertIn("RUN_REQUEUED_AFTER_RESTART", {event["event_type"] for event in self.store.events_after(run.tenant_id, run.run_id)})

    def test_effectiveness_probes_resume_from_a_durable_observation_window(self) -> None:
        delayed_plan = plan().model_copy(update={"observation_delay_seconds": 300})
        run = self.store.create_run(self.operator, request(execution_plan=delayed_plan), "create-delayed-effectiveness")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))

        pending = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(pending.state, "EFFECTIVENESS_PENDING")
        self.assertEqual(pending.runner_status, "awaiting_effectiveness")
        self.assertIsNotNone(pending.output["action"])
        released = [event for event in self.store.events_after(run.tenant_id, run.run_id) if event["event_type"] == "RUN_RELEASED"]
        self.assertEqual(released[-1]["payload"]["runner_status"], "awaiting_effectiveness")
        with self.assertRaises(Conflict):
            self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        with self.assertRaises(Conflict):
            self.store.claim_run(run.tenant_id, run.run_id)
        self.store.connection.execute("UPDATE runs SET effectiveness_due_at = '2000-01-01T00:00:00+00:00' WHERE run_id = ?", (run.run_id,))
        self.assertEqual(self.store.queue_due_effectiveness(), [(run.tenant_id, run.run_id)])
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))
        self.assertEqual(self.store.get_run(run.tenant_id, run.run_id).state, "EFFECTIVENESS_PROVEN")


class StorageBackendTests(unittest.TestCase):
    def test_default_storage_backend_is_sqlite(self) -> None:
        with patch.dict("os.environ", {"LOOPOS_REPO_ROOT": str(REPO_ROOT)}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.storage_backend, "sqlite")
        self.assertIsNone(settings.postgres_dsn)

    def test_invalid_storage_backend_is_rejected(self) -> None:
        with patch.dict("os.environ", {"LOOPOS_STORAGE_BACKEND": "browser"}, clear=True):
            with self.assertRaisesRegex(ValueError, "LOOPOS_STORAGE_BACKEND"):
                Settings.from_env()

    def test_postgres_backend_requires_a_dsn(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path("unused.db"),
            session_secret="postgres-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=True,
            allowed_http_hosts=(),
            cors_origins=(),
            storage_backend="postgres",
            postgres_dsn=None,
        )
        corpus = Corpus.load(REPO_ROOT)

        with self.assertRaisesRegex(ValueError, "LOOPOS_POSTGRES_DSN"):
            create_authority_store(settings, corpus)

    def test_supabase_migration_preserves_authority_tables_and_audit_controls(self) -> None:
        migration = (REPO_ROOT / "supabase" / "migrations" / "20260720010000_loopos_authority.sql").read_text(encoding="utf-8")

        for table in ["runs", "approvals", "evidence", "tool_invocations", "probe_results", "action_artifacts", "release_initiatives", "connector_events", "audit_events"]:
            self.assertIn(f"create table if not exists {table}", migration)
            self.assertIn(f"alter table {table} enable row level security", migration)
        self.assertIn("audit_events_no_update", migration)
        self.assertIn("audit_events_no_delete", migration)
        self.assertIn("revoke all on runs, approvals, evidence, tool_invocations, probe_results, action_artifacts, release_initiatives, connector_events, audit_events from anon, authenticated", migration)

    def test_postgres_migration_runner_preserves_dollar_quoted_functions(self) -> None:
        migration = (REPO_ROOT / "supabase" / "migrations" / "20260720010000_loopos_authority.sql").read_text(encoding="utf-8")
        statements = split_postgres_script(migration)

        function_statements = [statement for statement in statements if statement.startswith("create or replace function deny_audit_event_mutation")]
        self.assertEqual(len(function_statements), 1)
        self.assertIn("raise exception 'audit events are append-only';", function_statements[0])


@unittest.skipUnless(os.getenv("LOOPOS_TEST_POSTGRES_DSN"), "Set LOOPOS_TEST_POSTGRES_DSN to run live Supabase/Postgres storage tests.")
class PostgresStorageIntegrationTests(unittest.TestCase):
    def test_postgres_store_executes_a_durable_loop(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path("unused.db"),
            session_secret="postgres-live-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=True,
            allowed_http_hosts=(),
            cors_origins=(),
            storage_backend="postgres",
            postgres_dsn=os.environ["LOOPOS_TEST_POSTGRES_DSN"],
            retry_wait_seconds=0,
        )
        corpus = Corpus.load(REPO_ROOT)
        store = create_authority_store(settings, corpus)
        tools = ToolRegistry(settings, store)
        engine = ExecutionEngine(corpus, store, tools)
        actor = Actor(tenant_id=f"tenant-postgres-{os.getpid()}", user_id="operator", name="Operator", role="Operator")
        try:
            run = store.create_run(actor, request(), f"postgres-create-{os.getpid()}")
            asyncio.run(engine.execute(run.tenant_id, run.run_id))

            completed = store.get_run(run.tenant_id, run.run_id)
            self.assertEqual(completed.state, "EFFECTIVENESS_PROVEN")
            self.assertEqual(completed.runner_status, "completed")
            valid, count, invalid = store.verify_audit_chain(run.tenant_id)
            self.assertTrue(valid)
            self.assertGreater(count, 10)
            self.assertIsNone(invalid)
        finally:
            asyncio.run(tools.close())
            store.close()


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "api.db",
            session_secret="api-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=True,
            allowed_http_hosts=(),
            cors_origins=("http://127.0.0.1:5173",),
            event_poll_seconds=0.001,
            retry_wait_seconds=0,
            webhook_secrets={"tenant-api:github": "github-webhook-secret", "tenant-api:jira": "jira-webhook-secret"},
        )
        self.client_context = TestClient(create_app(settings))
        self.client = self.client_context.__enter__()
        session = self.client.post("/v1/dev/sessions", json={"tenant_id": "tenant-api", "user_id": "operator", "name": "Operator", "role": "Operator"})
        self.token = session.json()["access_token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.tempdir.cleanup()

    def test_api_runs_execution_streams_events_and_isolates_tenants(self) -> None:
        created = self.client.post(
            "/v1/runs",
            headers={**self.headers, "idempotency-key": "api-create-key"},
            json=request().model_dump(mode="json"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.headers["x-content-type-options"], "nosniff")
        run_id = created.json()["run_id"]
        started = self.client.post(f"/v1/runs/{run_id}/start", headers=self.headers)
        self.assertEqual(started.status_code, 202, started.text)
        completed = self.client.get(f"/v1/runs/{run_id}", headers=self.headers)
        self.assertEqual(completed.json()["state"], "EFFECTIVENESS_PROVEN")
        stream = self.client.get(f"/v1/runs/{run_id}/events", headers=self.headers)
        self.assertIn("event: RUN_CREATED", stream.text)
        self.assertIn("event: STATE_TRANSITION", stream.text)
        self.assertIn("EFFECTIVENESS_PROVEN", stream.text)
        self.assertEqual(self.client.get(f"/v1/runs/{run_id}/events", headers={**self.headers, "last-event-id": "invalid"}).status_code, 400)

        other_session = self.client.post("/v1/dev/sessions", json={"tenant_id": "tenant-other", "user_id": "auditor", "name": "Auditor", "role": "Auditor"}).json()
        other_headers = {"authorization": f"Bearer {other_session['access_token']}"}
        self.assertEqual(self.client.get(f"/v1/runs/{run_id}", headers=other_headers).status_code, 404)
        self.assertEqual(self.client.post("/v1/runs", headers={**other_headers, "idempotency-key": "auditor-create-key"}, json=request().model_dump(mode="json")).status_code, 403)

        executive = self.client.post("/v1/dev/sessions", json={"tenant_id": "tenant-api", "user_id": "executive", "name": "Executive", "role": "Executive"}).json()
        audit = self.client.get("/v1/audit/verify", headers={"authorization": f"Bearer {executive['access_token']}"})
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertTrue(audit.json()["valid"])
        self.assertGreater(audit.json()["event_count"], 10)

    def test_recovery_successor_rotates_tool_idempotency_keys(self) -> None:
        failing_request = request(execution_plan=plan(expected="not-applied", rollback=True))
        created = self.client.post(
            "/v1/runs",
            headers={**self.headers, "idempotency-key": "api-create-failed-key"},
            json=failing_request.model_dump(mode="json"),
        )
        run_id = created.json()["run_id"]
        self.assertEqual(self.client.post(f"/v1/runs/{run_id}/start", headers=self.headers).status_code, 202)
        failed = self.client.get(f"/v1/runs/{run_id}", headers=self.headers).json()
        self.assertEqual(failed["state"], "ROLLED_BACK")

        recovery = self.client.post(
            f"/v1/runs/{run_id}/recover",
            headers={**self.headers, "idempotency-key": "api-recovery-key"},
        )

        self.assertEqual(recovery.status_code, 201, recovery.text)
        successor = recovery.json()
        self.assertEqual(successor["recovery_of"], run_id)
        self.assertNotEqual(successor["plan"]["action"]["idempotency_key"], failed["plan"]["action"]["idempotency_key"])
        self.assertNotEqual(successor["plan"]["rollback"]["idempotency_key"], failed["plan"]["rollback"]["idempotency_key"])

    def test_api_records_release_initiative_and_isolates_tenants(self) -> None:
        evidence = self.client.post("/v1/connector-events", headers=self.headers, json=connector_event_request().model_dump(mode="json"))
        self.assertEqual(evidence.status_code, 201, evidence.text)
        event_id = evidence.json()["connector_event_id"]
        event_replay = self.client.post("/v1/connector-events", headers=self.headers, json=connector_event_request().model_dump(mode="json"))
        self.assertEqual(event_replay.json()["connector_event_id"], event_id)

        created = self.client.post(
            "/v1/release-initiatives",
            headers={**self.headers, "idempotency-key": "api-release-create-key"},
            json=release_request([event_id]).model_dump(mode="json"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        initiative = created.json()
        self.assertEqual(initiative["release_name"], "Release 2026.08")
        self.assertEqual(initiative["source_event_ids"], [event_id])
        self.assertEqual(initiative["release_assurance"]["operating_mode"], "shadow_release")

        replay = self.client.post(
            "/v1/release-initiatives",
            headers={**self.headers, "idempotency-key": "api-release-create-key"},
            json=release_request([event_id]).model_dump(mode="json"),
        )
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["initiative_id"], initiative["initiative_id"])

        listed = self.client.get("/v1/release-initiatives?workspace_id=workspace-release", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()), 1)
        events = self.client.get("/v1/connector-events?workspace_id=workspace-release", headers=self.headers)
        self.assertEqual(len(events.json()), 1)
        proof_pack = self.client.get(f"/v1/release-initiatives/{initiative['initiative_id']}/proof-pack", headers=self.headers)
        self.assertEqual(proof_pack.status_code, 200, proof_pack.text)
        self.assertEqual(proof_pack.json()["initiative_id"], initiative["initiative_id"])
        self.assertIn("LoopOS Authority Release Proof Pack", proof_pack.json()["markdown"])
        self.assertEqual(len(proof_pack.json()["markdown_hash"]), 64)

        other_session = self.client.post("/v1/dev/sessions", json={"tenant_id": "tenant-other", "user_id": "operator", "name": "Operator", "role": "Operator"}).json()
        other_headers = {"authorization": f"Bearer {other_session['access_token']}"}
        self.assertEqual(self.client.get("/v1/release-initiatives?workspace_id=workspace-release", headers=other_headers).json(), [])
        self.assertEqual(self.client.get("/v1/connector-events?workspace_id=workspace-release", headers=other_headers).json(), [])
        self.assertEqual(self.client.get(f"/v1/release-initiatives/{initiative['initiative_id']}/proof-pack", headers=other_headers).status_code, 404)

    def test_github_webhook_requires_valid_signature_and_records_verified_event(self) -> None:
        payload = {
            "repository": {"full_name": "acme/payments", "html_url": "https://github.example/acme/payments"},
            "pull_request": {"html_url": "https://github.example/acme/payments/pull/42", "title": "Prepare release gate"},
        }
        body = json_bytes(payload)
        signature = webhook_signature("github-webhook-secret", body)

        created = self.client.post(
            "/v1/webhooks/tenant-api/github?workspace_id=workspace-release",
            content=body,
            headers={"x-hub-signature-256": signature, "x-github-event": "pull_request", "x-github-delivery": "delivery-1", "content-type": "application/json"},
        )

        self.assertEqual(created.status_code, 201, created.text)
        event = created.json()
        self.assertEqual(event["system"], "github")
        self.assertEqual(event["event_kind"], "pull_request")
        self.assertEqual(event["verification_status"], "verified_webhook")
        self.assertEqual(event["delivery_id"], "delivery-1")

        replayed = self.client.post(
            "/v1/webhooks/tenant-api/github?workspace_id=workspace-release",
            content=body,
            headers={"x-hub-signature-256": signature, "x-github-event": "pull_request", "x-github-delivery": "delivery-1", "content-type": "application/json"},
        )
        self.assertEqual(replayed.status_code, 201, replayed.text)
        self.assertEqual(replayed.json()["connector_event_id"], event["connector_event_id"])

        changed_body = json_bytes({**payload, "action": "closed"})
        replay_conflict = self.client.post(
            "/v1/webhooks/tenant-api/github?workspace_id=workspace-release",
            content=changed_body,
            headers={"x-hub-signature-256": webhook_signature("github-webhook-secret", changed_body), "x-github-event": "pull_request", "x-github-delivery": "delivery-1", "content-type": "application/json"},
        )
        self.assertEqual(replay_conflict.status_code, 409)

        rejected = self.client.post(
            "/v1/webhooks/tenant-api/github?workspace_id=workspace-release",
            content=body,
            headers={"x-hub-signature-256": "sha256=bad", "x-github-event": "pull_request", "content-type": "application/json"},
        )
        self.assertEqual(rejected.status_code, 403)

    def test_jira_webhook_requires_configured_secret_and_signature(self) -> None:
        payload = {"webhookEvent": "jira:issue_updated", "issue": {"key": "PAY-42", "fields": {"summary": "Release readiness gate"}}}
        body = json_bytes(payload)
        created = self.client.post(
            "/v1/webhooks/tenant-api/jira?workspace_id=workspace-release",
            content=body,
            headers={"x-loopos-signature-256": webhook_signature("jira-webhook-secret", body), "x-atlassian-webhook-identifier": "jira-delivery-1", "content-type": "application/json"},
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["external_id"], "PAY-42")
        self.assertEqual(created.json()["verification_status"], "verified_webhook")

        missing_secret = self.client.post(
            "/v1/webhooks/tenant-other/jira?workspace_id=workspace-release",
            content=body,
            headers={"x-loopos-signature-256": webhook_signature("jira-webhook-secret", body), "content-type": "application/json"},
        )
        self.assertEqual(missing_secret.status_code, 403)


if __name__ == "__main__":
    unittest.main()
