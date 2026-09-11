from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from loopos_authority.api import create_app
from loopos_authority.audit_anchor import AuditAnchorDispatcher
from loopos_authority.config import Settings, operational_binding_status
from loopos_authority.corpus import Corpus
from loopos_authority.engine import ExecutionEngine
from loopos_authority.models import Actor, ApprovalRequest, ConnectorEventRequest, CreateReleaseInitiativeRequest, CreateRunRequest, ENTERPRISE_SESSION_MAX_SECONDS, EnterpriseSessionResponse, EvidenceRequest, ExecutionPlan, ProbeSpec, RecordReleaseInitiativeRequest, RunCommandResponse, RunRecord, SessionResponse
from loopos_authority.persistence import create_authority_store
from loopos_authority.postgres_store import REQUIRED_AUDIT_TRIGGERS, REQUIRED_POSTGRES_TABLES, PostgresAuthorityStore, PostgresConnection, split_postgres_script
from loopos_authority.store import AuthorityStore, Conflict, Forbidden, NotFound
from loopos_authority.tools import TerminalToolFailure, ToolRegistry
from loopos_authority.worker import ExecutionJobWorker


REPO_ROOT = Path(__file__).resolve().parents[2]


class SessionContractTests(unittest.TestCase):
    def test_session_response_rejects_an_excessive_lifetime(self) -> None:
        with self.assertRaises(ValidationError):
            SessionResponse(
                access_token="enterprise-token",
                expires_in=28_801,
                actor=Actor(
                    tenant_id="tenant-enterprise",
                    user_id="oidc-user-42",
                    name="Operator",
                    role="Operator",
                ),
            )

    def test_enterprise_session_response_rejects_a_lifetime_above_the_authority_contract(self) -> None:
        with self.assertRaises(ValidationError):
            EnterpriseSessionResponse(
                access_token="enterprise-token",
                expires_in=ENTERPRISE_SESSION_MAX_SECONDS + 1,
                actor=Actor(
                    tenant_id="tenant-enterprise",
                    user_id="oidc-user-42",
                    name="Operator",
                    role="Operator",
                ),
            )

    def test_run_command_response_rejects_an_unknown_lifecycle_status(self) -> None:
        with self.assertRaises(ValidationError):
            RunCommandResponse(run_id="run-1", state="UNKNOWN", runner_status="queued")

    def test_run_record_rejects_an_unknown_runner_status(self) -> None:
        with self.assertRaises(ValidationError):
            RunRecord(
                run_id="run-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                loop_id="loop-001-product-discovery-loop",
                title="Run",
                trigger="Trigger",
                state="TRIGGERED",
                runner_status="unknown",
                risk_tier="R1",
                requires_approval=False,
                payload_hash="a" * 64,
                plan={
                    "evidence": [{"evidence_id": "evidence-1", "kind": "workspace_snapshot", "source_ref": "workspace://1", "freshness_seconds": 3600}],
                    "action": {"tool": "record_action", "arguments": {}, "idempotency_key": "action-1", "external_effect": False},
                    "validation_probes": [{"probe_id": "probe-1", "kind": "evidence_present", "target": "evidence", "path": "evidence_id", "expected": "evidence-1"}],
                    "effectiveness_probes": [{"probe_id": "probe-2", "kind": "evidence_present", "target": "evidence", "path": "evidence_id", "expected": "evidence-1"}],
                },
                attempt=0,
                created_by="operator",
                created_at="2026-08-23T12:00:00+00:00",
                updated_at="2026-08-23T12:00:00+00:00",
            )

    def test_release_assurance_requires_sha256_evidence_and_current_decisions(self) -> None:
        valid = release_request()
        weak_hash = json.loads(json.dumps(valid.release_assurance))
        weak_hash["external_refs"][0]["evidence_hash"] = "local-fnv1a-deadbeef"
        with self.assertRaisesRegex(ValidationError, "lowercase SHA-256"):
            CreateReleaseInitiativeRequest.model_validate({**valid.model_dump(mode="json"), "release_assurance": weak_hash})

        missing_decision = json.loads(json.dumps(valid.release_assurance))
        missing_decision["gates"][0].pop("last_decision")
        missing_decision["decisions"] = [missing_decision["decisions"][1]]
        with self.assertRaisesRegex(ValidationError, "current human decision"):
            CreateReleaseInitiativeRequest.model_validate({**valid.model_dump(mode="json"), "release_assurance": missing_decision})


class PostgresConnectionContractTests(unittest.TestCase):
    def test_disables_prepared_statements_for_transaction_poolers(self) -> None:
        with patch("psycopg.connect") as connect:
            PostgresConnection("postgresql://authority.example/loopos")

        self.assertIsNone(connect.call_args.kwargs["prepare_threshold"])

    def test_read_cursors_close_after_fetch(self) -> None:
        class FakeCursor:
            def __init__(self) -> None:
                self.closed = False
                self.sql = ""

            def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
                self.sql = sql

            def fetchone(self) -> dict[str, int]:
                return {"count": 1}

            def close(self) -> None:
                self.closed = True

        class FakeConnection:
            def __init__(self) -> None:
                self.cursor_instance = FakeCursor()

            def cursor(self) -> FakeCursor:
                return self.cursor_instance

        fake_connection = FakeConnection()
        with patch("psycopg.connect", return_value=fake_connection):
            connection = PostgresConnection("postgresql://authority.example/loopos")
            result = connection.execute("SELECT ?", ("value",)).fetchone()

        self.assertEqual(result, {"count": 1})
        self.assertEqual(fake_connection.cursor_instance.sql, "SELECT %s")
        self.assertTrue(fake_connection.cursor_instance.closed)

    def test_postgres_migration_scripts_commit_or_roll_back_as_one_unit(self) -> None:
        class FakeCursor:
            def __init__(self, connection: "FakeConnection") -> None:
                self.connection = connection

            def __enter__(self) -> "FakeCursor":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def execute(self, sql: str) -> None:
                self.connection.statements.append(sql)
                if sql == "BROKEN":
                    raise RuntimeError("migration statement failed")

        class FakeConnection:
            def __init__(self) -> None:
                self.statements: list[str] = []
                self.commits = 0
                self.rollbacks = 0
                self.fail_commit = False

            def cursor(self) -> FakeCursor:
                return FakeCursor(self)

            def commit(self) -> None:
                self.commits += 1
                if self.fail_commit:
                    raise RuntimeError("migration commit failed")

            def rollback(self) -> None:
                self.rollbacks += 1

        fake_connection = FakeConnection()
        with patch("psycopg.connect", return_value=fake_connection):
            connection = PostgresConnection("postgresql://authority.example/loopos")
            connection.executescript("CREATE TABLE one (id integer); CREATE TABLE two (id integer);")
            with self.assertRaisesRegex(RuntimeError, "migration statement failed"):
                connection.executescript("CREATE TABLE three (id integer); BROKEN;")
            fake_connection.fail_commit = True
            with self.assertRaisesRegex(RuntimeError, "migration commit failed"):
                connection.executescript("CREATE TABLE four (id integer);")

        self.assertEqual(fake_connection.commits, 2)
        self.assertEqual(fake_connection.rollbacks, 2)
        self.assertEqual(
            fake_connection.statements,
            [
                "BEGIN",
                "CREATE TABLE one (id integer)",
                "CREATE TABLE two (id integer)",
                "BEGIN",
                "CREATE TABLE three (id integer)",
                "BROKEN",
                "BEGIN",
                "CREATE TABLE four (id integer)",
            ],
        )

    def test_postgres_job_claims_lock_runs_and_skip_locked_scheduler_rows(self) -> None:
        store = object.__new__(PostgresAuthorityStore)

        self.assertIn("FOR UPDATE", store._run_for_update_sql())
        self.assertIn("FOR UPDATE SKIP LOCKED", store._execution_job_claim_sql())
        self.assertIn("FOR UPDATE SKIP LOCKED", store._due_effectiveness_claim_sql())
        self.assertIn("FOR UPDATE SKIP LOCKED", store._incomplete_runs_claim_sql())

    def test_postgres_initialization_rejects_an_empty_migrations_directory(self) -> None:
        store = object.__new__(PostgresAuthorityStore)
        store.lock = threading.RLock()
        store.connection = object()

        with tempfile.TemporaryDirectory() as temporary_directory:
            store.migrations_dir = Path(temporary_directory)
            with self.assertRaisesRegex(RuntimeError, "Postgres authority migrations are missing"):
                store._initialize()

    def test_postgres_schema_verification_rejects_missing_authority_tables(self) -> None:
        class FakeResult:
            def fetchall(self) -> list[dict[str, str]]:
                return []

        class FakeConnection:
            def execute(self, _sql: str, _parameters: tuple[object, ...] = ()) -> FakeResult:
                return FakeResult()

        store = object.__new__(PostgresAuthorityStore)
        store.lock = threading.RLock()
        store.connection = FakeConnection()

        with self.assertRaisesRegex(RuntimeError, "missing required tables"):
            store.verify_schema()

    def test_postgres_schema_verification_rejects_missing_row_level_security(self) -> None:
        class FakeResult:
            def __init__(self, rows: list[dict[str, str]]) -> None:
                self.rows = rows

            def fetchall(self) -> list[dict[str, str]]:
                return self.rows

        class FakeConnection:
            def execute(self, sql: str, _parameters: tuple[object, ...] = ()) -> FakeResult:
                if "information_schema.tables" in sql:
                    return FakeResult([{"table_name": table} for table in REQUIRED_POSTGRES_TABLES])
                if "pg_class" in sql:
                    return FakeResult([{"relname": table} for table in REQUIRED_POSTGRES_TABLES if table != "runs"])
                return FakeResult([])

        store = object.__new__(PostgresAuthorityStore)
        store.lock = threading.RLock()
        store.connection = FakeConnection()

        with self.assertRaisesRegex(RuntimeError, "row-level security.*runs"):
            store.verify_schema()

    def test_postgres_schema_verification_rejects_missing_append_only_audit_triggers(self) -> None:
        class FakeResult:
            def __init__(self, rows: list[dict[str, str]]) -> None:
                self.rows = rows

            def fetchall(self) -> list[dict[str, str]]:
                return self.rows

        class FakeConnection:
            def execute(self, sql: str, _parameters: tuple[object, ...] = ()) -> FakeResult:
                if "information_schema.tables" in sql or "pg_class" in sql:
                    key = "table_name" if "information_schema.tables" in sql else "relname"
                    return FakeResult([{key: table} for table in REQUIRED_POSTGRES_TABLES])
                if "pg_trigger" in sql:
                    return FakeResult([{"tgname": next(iter(REQUIRED_AUDIT_TRIGGERS - {"audit_events_no_update"}))}])
                return FakeResult([])

        store = object.__new__(PostgresAuthorityStore)
        store.lock = threading.RLock()
        store.connection = FakeConnection()

        with self.assertRaisesRegex(RuntimeError, "append-only audit triggers.*audit_events_no_update"):
            store.verify_schema()

    def test_postgres_audit_appends_lock_the_tenant_chain_before_reading_previous_hash(self) -> None:
        store = object.__new__(PostgresAuthorityStore)
        cursor = Mock()

        with patch.object(AuthorityStore, "_append_event_cursor", return_value={"event_id": "event-1"}) as append:
            result = store._append_event_cursor(
                cursor,
                "tenant-a",
                None,
                "TEST_EVENT",
                None,
                "actor-a",
                {},
            )

        self.assertEqual(result, {"event_id": "event-1"})
        cursor.execute.assert_called_once_with(
            "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
            ("tenant-a",),
        )
        append.assert_called_once()


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
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def complete_production_settings(self, database_name: str) -> Settings:
        verified_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        return replace(
            self.settings,
            database_path=Path(self.tempdir.name) / database_name,
            allowed_http_hosts=("api.example.com",),
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
            retention_policy_url="https://policy.example.com/loopos-retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="allowlist",
            backup_restore_evidence_url="https://evidence.example.com/loopos/restore-test",
            backup_restore_evidence_sha256="a" * 64,
            backup_restore_verified_at=verified_at,
            operational_evidence_url="https://evidence.example.com/loopos/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=verified_at,
            worker_token="execution-worker-token-that-is-at-least-thirty-two-bytes",
            execution_worker_mode="external",
        )

    def test_request_rate_limit_is_durable_and_returns_retry_metadata(self) -> None:
        store = AuthorityStore(Path(self.tempdir.name) / "rate-limit-store.db", Corpus.load(REPO_ROOT))
        try:
            first = store.consume_request_rate_limit("client-a", 2, 60, now_epoch=120)
            second = store.consume_request_rate_limit("client-a", 2, 60, now_epoch=121)
            third = store.consume_request_rate_limit("client-a", 2, 60, now_epoch=122)
            next_window = store.consume_request_rate_limit("client-a", 2, 60, now_epoch=180)
        finally:
            store.close()

        self.assertTrue(first["allowed"])
        self.assertTrue(second["allowed"])
        self.assertFalse(third["allowed"])
        self.assertEqual(third["remaining"], 0)
        self.assertEqual(third["retry_after"], 58)
        self.assertTrue(next_window["allowed"])

    def test_api_rate_limit_returns_429_and_retry_after(self) -> None:
        settings = replace(
            self.settings,
            allow_dev_auth=True,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
            database_path=Path(self.tempdir.name) / "rate-limit-api.db",
        )
        with TestClient(create_app(settings)) as client:
            first = client.get("/v1/session")
            second = client.get("/v1/session")

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertIn(int(second.headers["retry-after"]), range(1, 61))
        self.assertEqual(second.headers["x-ratelimit-remaining"], "0")

    def test_api_rate_limit_fails_closed_when_counter_storage_is_unavailable(self) -> None:
        settings = replace(
            self.settings,
            allow_dev_auth=True,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
            database_path=Path(self.tempdir.name) / "rate-limit-storage-failure.db",
        )
        app = create_app(settings)
        with patch.object(app.state.store, "consume_request_rate_limit", side_effect=RuntimeError("counter unavailable")):
            with TestClient(app) as client:
                response = client.get("/v1/session")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Request rate limiting is temporarily unavailable.")

    def prove_external_production_readiness(self, client: TestClient, settings: Settings) -> None:
        drain = client.post(
            "/v1/operations/jobs/drain",
            headers={"x-loopos-worker-token": settings.worker_token},
        )
        self.assertEqual(drain.status_code, 200, drain.text)
        ready = client.get("/health/ready")
        self.assertEqual(ready.status_code, 200, ready.text)

    def test_exchanges_a_verified_gateway_identity_for_a_short_lived_session(self) -> None:
        settings = self.complete_production_settings("identity-ready.db")
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                self.prove_external_production_readiness(client, settings)
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

    def test_enterprise_session_rejects_a_disallowed_origin(self) -> None:
        settings = self.complete_production_settings("identity-origin-rejected.db")
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                self.prove_external_production_readiness(client, settings)
                response = client.post(
                    "/v1/sessions",
                    headers={
                        "origin": "https://evil.example",
                        "x-loopos-identity-token": "verified-identity-assertion",
                    },
                )

        self.assertEqual(response.status_code, 403, response.text)

    def test_enterprise_session_allows_same_origin_and_configured_ui_origin(self) -> None:
        settings = self.complete_production_settings("identity-same-origin.db")
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                self.prove_external_production_readiness(client, settings)
                same_origin = client.post(
                    "/v1/sessions",
                    headers={
                        "origin": "http://testserver",
                        "x-loopos-identity-token": "verified-identity-assertion",
                    },
                )
        self.assertEqual(same_origin.status_code, 200, same_origin.text)

        configured_settings = replace(
            self.complete_production_settings("identity-configured-origin.db"),
            cors_origins=("https://ui.example",),
        )
        configured_store = AuthorityStore(configured_settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=configured_store):
            with TestClient(create_app(configured_settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                self.prove_external_production_readiness(client, configured_settings)
                configured_origin = client.post(
                    "/v1/sessions",
                    headers={
                        "origin": "https://ui.example",
                        "x-loopos-identity-token": "verified-identity-assertion",
                    },
                )
        self.assertEqual(configured_origin.status_code, 200, configured_origin.text)

    def test_enterprise_identity_header_is_allowed_by_configured_ui_cors(self) -> None:
        settings = replace(
            self.complete_production_settings("identity-preflight.db"),
            cors_origins=("https://ui.example",),
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                preflight = client.options(
                    "/v1/sessions",
                    headers={
                        "origin": "https://ui.example",
                        "access-control-request-method": "POST",
                        "access-control-request-headers": "x-loopos-identity-token",
                    },
                )

        self.assertEqual(preflight.status_code, 200, preflight.text)
        self.assertEqual(preflight.headers["access-control-allow-origin"], "https://ui.example")
        self.assertIn("x-loopos-identity-token", preflight.headers["access-control-allow-headers"].lower())

    def test_production_exception_routes_have_explicit_fail_closed_contracts(self) -> None:
        with TestClient(create_app(self.settings, identity_verifier=self.IdentityVerifier())) as client:
            live = client.get("/health/live")
            ready = client.get("/health/ready")
            development_session = client.post("/v1/dev/sessions", json={})
            protected = client.get("/v1/session")
            audit_drain = client.post("/v1/audit/anchors/drain")
            worker_drain = client.post("/v1/operations/jobs/drain")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(development_session.status_code, 404)
        self.assertEqual(protected.status_code, 503)
        self.assertEqual(audit_drain.status_code, 401)
        self.assertEqual(worker_drain.status_code, 401)

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

    def test_enterprise_session_requires_production_readiness(self) -> None:
        with TestClient(create_app(self.settings, identity_verifier=self.IdentityVerifier())) as client:
            response = client.post(
                "/v1/sessions",
                headers={"x-loopos-identity-token": "verified-identity-assertion"},
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Production persistence must use Postgres.")

    def test_production_rejects_external_worker_drain_when_internal_mode_is_configured(self) -> None:
        settings = replace(
            self.settings,
            worker_token="production-worker-token-that-is-at-least-thirty-two-bytes",
            execution_worker_mode="internal",
        )
        with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier())) as client:
            response = client.post(
                "/v1/operations/jobs/drain",
                headers={"x-loopos-worker-token": settings.worker_token},
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "External worker dispatch is not configured.")

    def test_production_blocks_protected_operations_until_readiness_is_proven(self) -> None:
        with TestClient(create_app(self.settings, identity_verifier=self.IdentityVerifier())) as client:
            session = client.post(
                "/v1/sessions",
                headers={"x-loopos-identity-token": "verified-identity-assertion"},
            )
            response = client.put(
                "/v1/workspaces/workspace-before-readiness",
                headers={
                    "authorization": "Bearer not-issued",
                    "if-none-match": "*",
                },
                json={"document": workspace_document("workspace-before-readiness")},
            )

        self.assertEqual(session.status_code, 503, session.text)
        self.assertEqual(session.json()["detail"], "Production persistence must use Postgres.")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Production persistence must use Postgres.")

    def test_production_connector_events_require_a_tenant_owned_workspace(self) -> None:
        settings = self.complete_production_settings("tenant-isolation.db")
        foreign_workspace = workspace_document(workspace_id="workspace-foreign")
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        store.put_workspace(
            Actor(tenant_id="tenant-other", user_id="other-operator", name="Other Operator", role="Operator"),
            "workspace-foreign",
            foreign_workspace,
            expected_revision=None,
            create_only=True,
        )
        event = connector_event_request().model_copy(update={"workspace_id": "workspace-foreign"})
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                drain = client.post(
                    "/v1/operations/jobs/drain",
                    headers={"x-loopos-worker-token": settings.worker_token},
                )
                self.assertEqual(drain.status_code, 200, drain.text)
                self.assertEqual(client.get("/health/ready").status_code, 200)
                session = client.post(
                    "/v1/sessions",
                    headers={"x-loopos-identity-token": "verified-identity-assertion"},
                )
                self.assertEqual(session.status_code, 200, session.text)
                headers = {"authorization": f"Bearer {session.json()['access_token']}"}
                response = client.post(
                    "/v1/connector-events",
                    headers=headers,
                    json=event.model_dump(mode="json"),
                )
                run_response = client.post(
                    "/v1/runs",
                    headers={**headers, "idempotency-key": "foreign-run-key"},
                    json=request().model_copy(update={"workspace_id": "workspace-foreign"}).model_dump(mode="json"),
                )
                release_response = client.post(
                    "/v1/release-initiatives",
                    headers={**headers, "idempotency-key": "foreign-release-key"},
                    json=release_request().model_copy(update={"workspace_id": "workspace-foreign"}).model_dump(mode="json"),
                )

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(run_response.status_code, 404, run_response.text)
        self.assertEqual(release_response.status_code, 404, release_response.text)

    def test_production_readiness_requires_server_side_operational_bindings(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=(),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=httpx.MockTransport(lambda _request: httpx.Response(202)))) as client:
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertIn("retention_policy", detail)
        self.assertIn("support_contact", detail)
        self.assertIn("outbound_policy", detail)
        self.assertIn("backup_restore", detail)
        self.assertIn("worker_dispatch", detail)

    def test_production_readiness_rejects_pending_execution_jobs(self) -> None:
        settings = self.complete_production_settings("operations-backlog.db")
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        store.put_workspace(
            Actor(tenant_id="tenant-enterprise", user_id="oidc-user-42", name="Enterprise Approver", role="Approver"),
            "operations-backlog-workspace",
            workspace_document("operations-backlog-workspace"),
            expected_revision=None,
            create_only=True,
        )
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                drain = client.post(
                    "/v1/operations/jobs/drain",
                    headers={"x-loopos-worker-token": settings.worker_token},
                )
                self.assertEqual(drain.status_code, 200, drain.text)
                with patch.object(store, "execution_job_backlog", return_value=1):
                    response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Production execution job backlog contains 1 job(s).")

    def test_production_readiness_accepts_complete_recent_operational_evidence(self) -> None:
        restore_verified_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-ready.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=("api.example.com",),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
            retention_policy_url="https://policy.example.com/loopos-retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="allowlist",
            backup_restore_evidence_url="https://evidence.example.com/loopos/restore-test",
            backup_restore_evidence_sha256="a" * 64,
            backup_restore_verified_at=restore_verified_at,
            operational_evidence_url="https://evidence.example.com/loopos/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=restore_verified_at,
            worker_token="execution-worker-token-that-is-at-least-thirty-two-bytes",
            execution_worker_mode="external",
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                drain = client.post(
                    "/v1/operations/jobs/drain",
                    headers={"x-loopos-worker-token": settings.worker_token},
                )
                self.assertEqual(drain.status_code, 200, drain.text)
                self.assertTrue(drain.json()["dispatch"]["verified"])
                self.assertEqual(drain.json()["dispatch"]["source"], "external")
                self.assertEqual(client.get("/health/ready").status_code, 200)
                session = client.post(
                    "/v1/sessions",
                    headers={"x-loopos-identity-token": "verified-identity-assertion"},
                )
                self.assertEqual(session.status_code, 200, session.text)
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["audit_anchor_delivery_verified"])
        self.assertIsNotNone(response.json()["audit_anchor_last_delivered_at"])
        self.assertTrue(response.json()["execution_worker_dispatch"]["verified"])
        self.assertEqual(response.json()["execution_worker_dispatch"]["source"], "external")
        self.assertEqual(response.json()["operational_bindings"], {
            "retention_verified": True,
            "support_verified": True,
            "outbound_policy_verified": True,
            "backup_restore_verified": True,
            "worker_dispatch_verified": True,
        })
        self.assertTrue(response.json()["rate_limit_configured"])
        self.assertFalse(response.json()["credential_injection_broker_verified"])
        self.assertEqual(response.json()["configuration_contract"], {
            "allowed_http_hosts": ["api.example.com"],
            "outbound_policy_mode": "allowlist",
            "retention_policy_url": "https://policy.example.com/loopos-retention",
            "support_contact": "loopos-operations@example.com",
            "backup_restore_evidence_url": "https://evidence.example.com/loopos/restore-test",
        })
        self.assertEqual(response.json()["backup_restore_evidence"], {
            "url": "https://evidence.example.com/loopos/restore-test",
            "sha256": "a" * 64,
            "verified_at": restore_verified_at,
        })
        self.assertEqual(
            response.json()["operational_evidence"]["url"],
            "https://evidence.example.com/loopos/operational-controls.json",
        )
        self.assertRegex(response.json()["operational_evidence"]["binding_fingerprint"], r"^[0-9a-f]{64}$")

    def test_production_readiness_rejects_stale_audit_delivery(self) -> None:
        verified_at = datetime.now(timezone.utc).isoformat()
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-stale-audit.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=("api.example.com",),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            retention_policy_url="https://policy.example.com/loopos-retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="allowlist",
            backup_restore_evidence_url="https://evidence.example.com/loopos/restore-test",
            backup_restore_evidence_sha256="a" * 64,
            backup_restore_verified_at=verified_at,
            operational_evidence_url="https://evidence.example.com/loopos/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=verified_at,
            worker_token="execution-worker-token-that-is-at-least-thirty-two-bytes",
            execution_worker_mode="external",
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=httpx.MockTransport(lambda _request: httpx.Response(202)))) as client:
                drain = client.post(
                    "/v1/operations/jobs/drain",
                    headers={"x-loopos-worker-token": settings.worker_token},
                )
                self.assertEqual(drain.status_code, 200, drain.text)
                store.connection.execute(
                    "UPDATE audit_anchor_outbox SET delivered_at = ? WHERE delivered_at IS NOT NULL",
                    ((datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),),
                )
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Production audit anchoring has not completed a recent verified delivery.",
        )

    def test_production_readiness_rejects_insecure_cors_origins(self) -> None:
        restore_verified_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-insecure-cors.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=("api.example.com",),
            cors_origins=("http://untrusted.example.com",),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
            retention_policy_url="https://policy.example.com/loopos-retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="allowlist",
            backup_restore_evidence_url="https://evidence.example.com/loopos/restore-test",
            backup_restore_evidence_sha256="a" * 64,
            backup_restore_verified_at=restore_verified_at,
            operational_evidence_url="https://evidence.example.com/loopos/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=restore_verified_at,
            worker_token="execution-worker-token-that-is-at-least-thirty-two-bytes",
            execution_worker_mode="external",
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=httpx.MockTransport(lambda _request: httpx.Response(202)))) as client:
                drain = client.post(
                    "/v1/operations/jobs/drain",
                    headers={"x-loopos-worker-token": settings.worker_token},
                )
                self.assertEqual(drain.status_code, 200, drain.text)
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Production CORS origins must use credential-free HTTPS or be empty.",
        )

    def test_production_readiness_rejects_unallowlisted_connector_credentials(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-unallowlisted-connector.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=("api.example.com",),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            connector_bearer_tokens={"rogue.example.com": "connector-token"},
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=httpx.MockTransport(lambda _request: httpx.Response(202)))) as client:
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Production connector credentials must belong to the outbound host allowlist.",
        )

    def test_production_readiness_rejects_malformed_outbound_policy(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-malformed-outbound-policy.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=("api.example.com/path",),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            outbound_policy_mode="allowlist",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=httpx.MockTransport(lambda _request: httpx.Response(202)))) as client:
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Production outbound policy must be deny_all with no hosts or allowlist with valid hosts.",
        )

    def test_production_readiness_rejects_an_audit_sink_that_cannot_verify_delivery(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-unproven-audit.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=(),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
            retention_policy_url="https://policy.example.com/loopos-retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="deny_all",
            backup_restore_evidence_url="https://evidence.example.com/loopos/restore-test",
            backup_restore_evidence_sha256="a" * 64,
            backup_restore_verified_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            operational_evidence_url="https://evidence.example.com/loopos/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            worker_token="execution-worker-token-that-is-at-least-thirty-two-bytes",
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=httpx.MockTransport(lambda _request: httpx.Response(503)))) as client:
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Production audit anchor backlog contains 1 event(s).",
        )

    def test_production_readiness_rejects_a_worker_token_without_a_dispatch_heartbeat(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "operations-unproven-worker.db",
            session_secret="identity-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=(),
            cors_origins=(),
            rate_limit_requests=120,
            rate_limit_window_seconds=60,
            storage_backend="postgres",
            postgres_dsn="postgresql://unused.example/loopos",
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
            retention_policy_url="https://policy.example.com/loopos-retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="deny_all",
            backup_restore_evidence_url="https://evidence.example.com/loopos/restore-test",
            backup_restore_evidence_sha256="a" * 64,
            backup_restore_verified_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            operational_evidence_url="https://evidence.example.com/loopos/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            worker_token="execution-worker-token-that-is-at-least-thirty-two-bytes",
        )
        store = AuthorityStore(settings.database_path, Corpus.load(REPO_ROOT))
        transport = httpx.MockTransport(lambda _request: httpx.Response(202))
        with patch("loopos_authority.api.create_authority_store", return_value=store):
            with patch("loopos_authority.api.ExecutionJobWorker.run_once", new=AsyncMock(return_value=0)):
                with TestClient(create_app(settings, identity_verifier=self.IdentityVerifier(), transport=transport)) as client:
                    response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertIn("worker_dispatch", response.json()["detail"])


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


def workspace_document(workspace_id: str = "workspace-authoritative", name: str = "Authoritative workspace") -> dict:
    return {
        "workspace_id": workspace_id,
        "name": name,
        "created_at": "2026-07-30T12:00:00+00:00",
        "updated_at": "2026-07-30T12:00:00+00:00",
        "owner_user_id": "operator",
        "use_case": {
            "title": "Claims governance",
            "description": "Govern a real claims workflow.",
            "environment": "production",
            "aiScope": "Workflow governance",
            "dataSensitivity": "sensitive",
            "businessOutcome": "Reduce claims review risk.",
            "maturity": "pilot",
            "constraints": "Preserve audit evidence and approval boundaries.",
        },
        "selected_loop_ids": [],
        "action_plan_markdown": "",
        "owner_evidence_edits": [],
        "approvals": [],
        "execution_records": [],
        "initiatives": [],
        "question_suggestions": [],
        "input_sources": [],
    }


def release_gate(gate_id: str, status: str, source_ref: str, loop_id: str = "loop-036-release-readiness-loop") -> dict:
    decision = {
        "decision_id": f"decision-{gate_id}",
        "gate_id": gate_id,
        "status": status,
        "decided_by": "approver-a",
        "decided_at": "2026-07-23T12:00:00+00:00",
        "basis": f"Decision basis for {gate_id}.",
        "source_ref_ids": [source_ref],
    }
    return {
        "gate_id": gate_id,
        "label": gate_id.replace("-", " ").title(),
        "loop_id": loop_id,
        "control_ids": [f"control-{gate_id}"],
        "required_evidence": [f"Evidence for {gate_id}"],
        "status": status,
        "blocker": f"Current status for {gate_id}.",
        "last_decision": decision,
    }


def release_request(source_event_ids: list[str] | None = None) -> CreateReleaseInitiativeRequest:
    external_refs = [
        {
            "ref_id": "jira-release-scope",
            "system": "jira",
            "object_type": "release",
            "label": "Release scope",
            "observed_at": "2026-07-23T12:00:00+00:00",
            "evidence_hash": "a" * 64,
        },
        {
            "ref_id": "github-change-set",
            "system": "github",
            "object_type": "pull_request",
            "label": "Change set",
            "observed_at": "2026-07-23T12:00:00+00:00",
            "evidence_hash": "b" * 64,
        },
        {
            "ref_id": "manual-release-attestation",
            "system": "manual",
            "object_type": "manual_note",
            "label": "Manual attestation",
            "observed_at": "2026-07-23T12:00:00+00:00",
            "evidence_hash": "c" * 64,
        },
    ]
    gates = [
        {
            "gate_id": "gate-release-readiness",
            "label": "Release readiness",
            "loop_id": "loop-036-release-readiness-loop",
            "control_ids": ["control-release-readiness"],
            "required_evidence": ["Release readiness evidence"],
            "status": "blocked",
            "blocker": "Release evidence is incomplete.",
            "last_decision": {
                "decision_id": "decision-release-readiness",
                "gate_id": "gate-release-readiness",
                "status": "blocked",
                "decided_by": "approver-a",
                "decided_at": "2026-07-23T12:00:00+00:00",
                "basis": "Release evidence is incomplete.",
                "source_ref_ids": ["jira-release-scope"],
            },
        },
        {
            "gate_id": "gate-deployment-validation",
            "label": "Deployment validation",
            "loop_id": "loop-038-deployment-validation-loop",
            "control_ids": ["control-deployment-validation"],
            "required_evidence": ["Deployment validation evidence"],
            "status": "blocked",
            "blocker": "Deployment validation evidence is incomplete.",
            "last_decision": {
                "decision_id": "decision-deployment-validation",
                "gate_id": "gate-deployment-validation",
                "status": "blocked",
                "decided_by": "approver-a",
                "decided_at": "2026-07-23T12:00:00+00:00",
                "basis": "Deployment validation evidence is incomplete.",
                "source_ref_ids": ["github-change-set"],
            },
        },
    ]
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
            "profile_id": "release-profile-test",
            "initiative_id": "initiative-client-test",
            "release_name": "Release 2026.08",
            "operating_mode": "shadow_release",
            "connectors": [
                {
                    "connector_id": "connector-jira",
                    "system": "jira",
                    "mode": "shadow_read",
                    "label": "Jira release evidence",
                    "required_for": ["release scope"],
                    "write_scope": "comment",
                    "trust_boundary": "Read-only until approval.",
                },
                {
                    "connector_id": "connector-github",
                    "system": "github",
                    "mode": "shadow_read",
                    "label": "GitHub change evidence",
                    "required_for": ["pull requests"],
                    "write_scope": "status_check",
                    "trust_boundary": "Read-only until approval.",
                },
            ],
            "external_refs": external_refs,
            "gates": gates,
            "evidence_artifacts": [
                {
                    "artifact_id": "artifact-release-readiness",
                    "gate_id": "gate-release-readiness",
                    "loop_id": "loop-036-release-readiness-loop",
                    "source_ref": "jira-release-scope",
                    "label": "Release scope evidence",
                    "freshness": "fresh",
                    "required": True,
                    "observed_at": "2026-07-23T12:00:00+00:00",
                },
            ],
            "decisions": [gate["last_decision"] for gate in gates],
            "exceptions": [],
            "metric_observations": [],
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
        self.executive = Actor(tenant_id="tenant-a", user_id="executive-a", name="Executive", role="Executive")

    def tearDown(self) -> None:
        asyncio.run(self.tools.close())
        self.store.close()
        self.tempdir.cleanup()


class StoreAndEngineTests(AuthorityHarness):
    def test_run_mutations_remain_tenant_scoped(self) -> None:
        run = self.store.create_run(self.operator, request(), "tenant-scope-run")
        foreign_tenant = "tenant-b"

        with self.assertRaises(NotFound):
            self.store.claim_run(foreign_tenant, run.run_id)
        with self.assertRaises(NotFound):
            self.store.release_run(foreign_tenant, run.run_id)
        with self.assertRaises(NotFound):
            self.store.transition(foreign_tenant, run.run_id, "DIAGNOSED", "foreign-operator")
        with self.assertRaises(NotFound):
            self.store.set_output(foreign_tenant, run.run_id, {"unexpected": True})

        unchanged = self.store.get_run(self.operator.tenant_id, run.run_id)
        self.assertEqual(unchanged.state, "TRIGGERED")
        self.assertEqual(unchanged.runner_status, "idle")
        self.assertIsNone(unchanged.output)

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

    def test_atomic_release_record_rolls_back_evidence_and_replays_as_one_unit(self) -> None:
        event = connector_event_request().model_copy(update={"external_id": "atomic-release-event"})
        invalid = RecordReleaseInitiativeRequest(
            initiative=release_request().model_copy(update={"loop_bundle_ids": ["loop-does-not-exist"]}),
            connector_events=[event],
        )
        with self.assertRaisesRegex(NotFound, "Unknown loop ID"):
            self.store.record_release_initiative(self.operator, invalid, "atomic-release-key")
        self.assertEqual(self.store.list_connector_events(self.operator.tenant_id, "workspace-release"), [])
        self.assertEqual(self.store.list_release_initiatives(self.operator.tenant_id, "workspace-release"), [])

        request_value = RecordReleaseInitiativeRequest(initiative=release_request(), connector_events=[event])
        initiative, events = self.store.record_release_initiative(self.operator, request_value, "atomic-release-key")
        replay, replay_events = self.store.record_release_initiative(self.operator, request_value, "atomic-release-key")
        self.assertEqual(len(events), 1)
        self.assertEqual(replay.initiative_id, initiative.initiative_id)
        self.assertEqual(replay.source_event_ids, [events[0].connector_event_id])
        self.assertEqual(replay_events[0].connector_event_id, events[0].connector_event_id)
        self.assertEqual(len(self.store.list_connector_events(self.operator.tenant_id, "workspace-release")), 1)
        self.assertEqual(len(self.store.list_release_initiatives(self.operator.tenant_id, "workspace-release")), 1)

    def test_release_initiative_cannot_attach_same_tenant_evidence_from_another_workspace(self) -> None:
        foreign_event = self.store.record_connector_event(
            self.operator,
            connector_event_request().model_copy(update={"workspace_id": "workspace-other"}),
        )

        with self.assertRaisesRegex(NotFound, "Unknown connector event IDs"):
            self.store.create_release_initiative(
                self.operator,
                release_request([foreign_event.connector_event_id]),
                "release-cross-workspace-event-key",
            )

    def test_release_initiative_rejects_duplicate_source_event_ids(self) -> None:
        connector = self.store.record_connector_event(
            self.operator,
            connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()),
        )

        with self.assertRaisesRegex(ValidationError, "Source connector event IDs must be unique"):
            release_request([connector.connector_event_id, connector.connector_event_id])

    def test_store_rejects_duplicate_source_event_ids_if_model_validation_is_bypassed(self) -> None:
        connector = connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()).model_copy(
            update={"verification_status": "verified_webhook", "delivery_id": "release-duplicate-delivery"}
        )
        connector_record = self.store.record_connector_event(self.operator, connector)
        duplicate_request = release_request([connector_record.connector_event_id]).model_copy(update={
            "release_assurance": {
                **release_request([connector_record.connector_event_id]).release_assurance,
                "gates": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope"),
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop"),
                ],
                "decisions": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope")["last_decision"],
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop")["last_decision"],
                ],
            }
        })
        duplicate_request.source_event_ids = [connector_record.connector_event_id, connector_record.connector_event_id]

        with self.assertRaisesRegex(ValueError, "Source connector event IDs must be unique"):
            self.store.create_release_initiative(
                self.operator,
                duplicate_request,
                "release-no-duplicate-go-key",
            )

    def test_release_initiative_marks_old_connector_evidence_stale(self) -> None:
        stale = self.store.record_connector_event(self.operator, connector_event_request(observed_at="2000-01-01T00:00:00+00:00"))
        initiative = self.store.create_release_initiative(self.operator, release_request([stale.connector_event_id]), "release-stale-evidence-key")

        self.assertEqual(initiative.freshness_summary["status"], "stale")
        self.assertEqual(initiative.freshness_summary["stale_event_ids"], [stale.connector_event_id])
        self.assertEqual(initiative.freshness_summary["max_age_seconds"], 86400)
        self.assertEqual(initiative.readiness_verdict["verdict"], "NO_GO")
        self.assertIn("connector evidence freshness is stale", initiative.readiness_verdict["failing_reasons"])

    def test_release_initiative_requires_provider_verified_evidence_for_go(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        ready_request = release_request([connector.connector_event_id])
        ready_request = ready_request.model_copy(update={
            "release_assurance": {
                **ready_request.release_assurance,
                "gates": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope"),
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop"),
                ],
                "decisions": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope")["last_decision"],
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop")["last_decision"],
                ],
            }
        })
        initiative = self.store.create_release_initiative(self.operator, ready_request, "release-ready-key")

        self.assertEqual(initiative.readiness_verdict["verdict"], "REVIEW_REQUIRED")
        self.assertEqual(initiative.readiness_verdict["failing_reasons"], [])
        self.assertTrue(any("not provider-verified" in reason for reason in initiative.readiness_verdict["review_reasons"]))

    def test_release_initiative_marks_all_passed_fresh_provider_verified_gates_go(self) -> None:
        connector = connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()).model_copy(
            update={"verification_status": "verified_webhook", "delivery_id": "release-ready-delivery"}
        )
        connector_record = self.store.record_connector_event(self.operator, connector)
        ready_request = release_request([connector_record.connector_event_id]).model_copy(update={
            "release_assurance": {
                **release_request([connector_record.connector_event_id]).release_assurance,
                "gates": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope"),
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop"),
                ],
                "decisions": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope")["last_decision"],
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop")["last_decision"],
                ],
            }
        })
        initiative = self.store.create_release_initiative(self.operator, ready_request, "release-provider-ready-key")

        self.assertEqual(initiative.freshness_summary["verified_webhook_count"], 1)
        self.assertEqual(initiative.readiness_verdict["verdict"], "GO")
        self.assertEqual(initiative.readiness_verdict["failing_reasons"], [])
        self.assertEqual(initiative.readiness_verdict["review_reasons"], [])

    def test_release_readiness_rejects_gate_records_without_unique_ids(self) -> None:
        connector = connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()).model_copy(
            update={"verification_status": "verified_webhook", "delivery_id": "release-gate-identity"}
        )
        connector_record = self.store.record_connector_event(self.operator, connector)
        cases = (
            [{"status": "passed", "source_ref_ids": ["github-change-set"]}],
            [
                {"gate_id": "gate-release-readiness", "status": "passed"},
                {"gate_id": "gate-release-readiness", "status": "passed"},
            ],
        )
        for index, gates in enumerate(cases):
            with self.subTest(case=index):
                request = release_request([connector_record.connector_event_id]).model_copy(update={
                    "release_assurance": {
                        **release_request([connector_record.connector_event_id]).release_assurance,
                        "gates": gates,
                    }
                })
                with self.assertRaises(ValueError):
                    self.store.create_release_initiative(
                        self.operator,
                        request,
                        f"release-gate-identity-key-{index}",
                    )

    def test_release_readiness_rechecks_connector_freshness_when_read(self) -> None:
        connector = connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()).model_copy(
            update={"verification_status": "verified_webhook", "delivery_id": "release-aging-delivery"}
        )
        connector_record = self.store.record_connector_event(self.operator, connector)
        ready_request = release_request([connector_record.connector_event_id]).model_copy(update={
            "release_assurance": {
                **release_request([connector_record.connector_event_id]).release_assurance,
                "gates": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope"),
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop"),
                ],
                "decisions": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope")["last_decision"],
                    release_gate("gate-deployment-validation", "passed", "github-change-set", "loop-038-deployment-validation-loop")["last_decision"],
                ],
            }
        })
        initiative = self.store.create_release_initiative(self.operator, ready_request, "release-aging-key")
        self.assertEqual(initiative.readiness_verdict["verdict"], "GO")

        self.store.connection.execute(
            "UPDATE connector_events SET observed_at = ? WHERE connector_event_id = ?",
            ("2000-01-01T00:00:00+00:00", connector_record.connector_event_id),
        )

        refreshed = self.store.get_release_initiative(self.operator.tenant_id, initiative.initiative_id)
        proof_pack = self.store.build_release_proof_pack(self.operator.tenant_id, initiative.initiative_id, self.operator.user_id)
        self.assertEqual(refreshed.freshness_summary["status"], "stale")
        self.assertEqual(refreshed.readiness_verdict["verdict"], "NO_GO")
        self.assertEqual(proof_pack.freshness_summary["status"], "stale")
        self.assertEqual(proof_pack.readiness_verdict["verdict"], "NO_GO")

        self.store.connection.execute(
            "DELETE FROM connector_events WHERE connector_event_id = ?",
            (connector_record.connector_event_id,),
        )
        missing = self.store.get_release_initiative(self.operator.tenant_id, initiative.initiative_id)
        self.assertEqual(missing.freshness_summary["status"], "missing")
        self.assertEqual(missing.freshness_summary["missing_event_ids"], [connector_record.connector_event_id])
        self.assertEqual(missing.readiness_verdict["verdict"], "NO_GO")

    def test_release_freshness_rejects_future_connector_timestamps(self) -> None:
        future = connector_event_request(
            observed_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        ).model_copy(update={"verification_status": "verified_webhook", "delivery_id": "release-future-delivery"})
        record = self.store.record_connector_event(self.operator, future)
        ready_request = release_request([record.connector_event_id]).model_copy(update={
            "release_assurance": {
                **release_request([record.connector_event_id]).release_assurance,
                "gates": [
                    release_gate("gate-release-readiness", "passed", "jira-release-scope"),
                ],
                "decisions": [release_gate("gate-release-readiness", "passed", "jira-release-scope")["last_decision"]],
            }
        })

        initiative = self.store.create_release_initiative(self.operator, ready_request, "release-future-key")

        self.assertEqual(initiative.freshness_summary["status"], "stale")
        self.assertEqual(initiative.freshness_summary["future_observed_at_event_ids"], [record.connector_event_id])
        self.assertEqual(initiative.readiness_verdict["verdict"], "NO_GO")

    def test_release_initiative_marks_review_gates_review_required(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        review_request = release_request([connector.connector_event_id])
        review_request = review_request.model_copy(update={
            "release_assurance": {
                **review_request.release_assurance,
                "gates": [release_gate("gate-rollback", "review_required", "manual-release-attestation", "loop-040-rollback-backup-and-recovery-loop")],
                "decisions": [release_gate("gate-rollback", "review_required", "manual-release-attestation", "loop-040-rollback-backup-and-recovery-loop")["last_decision"]],
                "evidence_artifacts": [{
                    "artifact_id": "artifact-rollback",
                    "gate_id": "gate-rollback",
                    "loop_id": "loop-040-rollback-backup-and-recovery-loop",
                    "source_ref": "manual-release-attestation",
                    "label": "Rollback evidence",
                    "freshness": "fresh",
                    "required": True,
                    "observed_at": "2026-07-23T12:00:00+00:00",
                }],
            }
        })
        initiative = self.store.create_release_initiative(self.operator, review_request, "release-review-key")

        self.assertEqual(initiative.readiness_verdict["verdict"], "REVIEW_REQUIRED")
        self.assertEqual(initiative.readiness_verdict["failing_reasons"], [])
        self.assertTrue(initiative.readiness_verdict["review_reasons"])

    def test_release_initiative_fails_closed_for_an_unknown_gate_status(self) -> None:
        connector = self.store.record_connector_event(self.operator, connector_event_request(observed_at=datetime.now(timezone.utc).isoformat()))
        malformed_request = release_request([connector.connector_event_id]).model_copy(update={
            "release_assurance": {
                **release_request([connector.connector_event_id]).release_assurance,
                "gates": [{"gate_id": "gate-malformed", "status": "mystery", "source_ref_ids": ["manual"]}],
            }
        })

        with self.assertRaisesRegex(ValueError, "must be a string|allowed value"):
            self.store.create_release_initiative(self.operator, malformed_request, "release-malformed-gate-key")

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
        transitions = [
            event for event in self.store.events_after(run.tenant_id, run.run_id)
            if event["event_type"] == "STATE_TRANSITION"
        ]
        self.assertTrue(transitions)
        observability = transitions[0]["payload"]["observability"]
        self.assertEqual(observability["loop_id"], run.loop_id)
        self.assertEqual(observability["execution_id"], run.run_id)
        self.assertEqual(observability["correlation_id"], run.run_id)
        self.assertEqual(observability["proof_state"], "unverified")
        valid, count, invalid = self.store.verify_audit_chain(run.tenant_id)
        self.assertTrue(valid)
        self.assertGreater(count, 10)
        self.assertIsNone(invalid)

    def test_tenant_kill_switch_blocks_queued_work_and_requires_executive_authority(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-kill-switch-queued")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)

        with self.assertRaises(Forbidden):
            self.store.activate_kill_switch(self.approver, "Approver cannot activate the tenant stop.")

        status = self.store.activate_kill_switch(self.executive, "Stop after unsafe execution signal.")
        self.assertTrue(status["active"])
        self.assertEqual(status["scope"], "tenant")
        blocked = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(blocked.state, "BLOCKED")
        self.assertEqual(blocked.runner_status, "failed")
        job = self.store.connection.execute("SELECT status, last_error FROM execution_jobs WHERE run_id = ?", (run.run_id,)).fetchone()
        self.assertEqual(job["status"], "failed")
        self.assertIn("kill switch", job["last_error"].lower())
        self.assertEqual(self.store.claim_execution_jobs("worker", 30), [])
        event_types = {
            event["event_type"]
            for event in [
                *self.store.events_after(run.tenant_id, None),
                *self.store.events_after(run.tenant_id, run.run_id),
            ]
        }
        self.assertIn("KILL_SWITCH_ACTIVATED", event_types)
        self.assertIn("KILL_SWITCH_ENFORCED", event_types)
        self.assertIn("EXECUTION_JOB_FAILED", event_types)
        valid, _, invalid = self.store.verify_audit_chain(run.tenant_id)
        self.assertTrue(valid)
        self.assertIsNone(invalid)

    def test_kill_switch_deactivation_does_not_resume_blocked_runs(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-kill-switch-restart")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        self.store.activate_kill_switch(self.executive, "Pause tenant while investigating.")

        with self.assertRaises(Conflict):
            self.store.create_run(self.operator, request(), "create-kill-switch-rejected")

        status = self.store.deactivate_kill_switch(self.executive, "Investigation complete; restart under fresh approval.")
        self.assertFalse(status["active"])
        blocked = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(blocked.state, "BLOCKED")
        self.assertEqual(blocked.runner_status, "failed")
        new_run = self.store.create_run(self.operator, request(), "create-kill-switch-after-deactivation")
        self.assertNotEqual(new_run.run_id, run.run_id)
        event_types = {event["event_type"] for event in self.store.events_after(run.tenant_id, None)}
        self.assertIn("KILL_SWITCH_DEACTIVATED", event_types)

    def test_kill_switch_interrupt_preserves_external_action_uncertainty(self) -> None:
        run = self.store.create_run(self.operator, request("loop-069-tool-execution-validation-loop"), "create-kill-switch-in-flight")
        self.store.claim_run(run.tenant_id, run.run_id)
        self.store.transition(run.tenant_id, run.run_id, "QUALIFIED", "authority-engine")
        self.store.transition(run.tenant_id, run.run_id, "OBSERVED", "authority-engine")
        self.store.transition(run.tenant_id, run.run_id, "DIAGNOSED", "authority-engine")
        self.store.transition(run.tenant_id, run.run_id, "PRIORITIZED", "authority-engine")
        self.store.transition(run.tenant_id, run.run_id, "PLANNED", "authority-engine")
        self.store.transition(run.tenant_id, run.run_id, "AUTHORIZED", "authority-engine")
        self.store.transition(run.tenant_id, run.run_id, "ACTION_IN_PROGRESS", "authority-engine")
        self.store.activate_kill_switch(self.executive, "Stop before the connector response is trusted.")

        interrupted = self.store.interrupt_run_for_kill_switch(
            run.tenant_id,
            run.run_id,
            "after_action_dispatch",
            action_output={"change_id": "change-uncertain"},
            action_external_effect=True,
        )
        self.assertEqual(interrupted.state, "BLOCKED")
        self.assertEqual(interrupted.runner_status, "failed")
        self.assertTrue(interrupted.output["kill_switch"]["remote_action_may_have_completed"])
        self.assertFalse(interrupted.output["kill_switch"]["remote_cancellation_requested"])
        self.assertEqual(interrupted.output["kill_switch"]["credential_revocation"], "not_available_to_authority")

    def test_effectiveness_state_cannot_outrun_durable_proof_output(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-effectiveness-output-failure")
        original_set_output = self.store.set_output

        def fail_effectiveness_output(tenant_id: str, run_id: str, output: dict[str, object]) -> None:
            if "effectiveness" in output:
                raise RuntimeError("effectiveness output persistence failed")
            original_set_output(tenant_id, run_id, output)

        with patch.object(self.store, "set_output", side_effect=fail_effectiveness_output):
            asyncio.run(self.engine.execute(run.tenant_id, run.run_id))

        failed = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(failed.state, "EFFECTIVENESS_FAILED")
        self.assertNotIn("effectiveness", failed.output or {})

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

    def test_requester_cannot_approve_or_reject_own_high_risk_run(self) -> None:
        run = self.store.create_run(self.operator, request("loop-069-tool-execution-validation-loop"), "create-separation-of-duties")
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))
        same_identity_approver = Actor(
            tenant_id=self.operator.tenant_id,
            user_id=self.operator.user_id,
            name=self.operator.name,
            role="Approver",
        )
        approval_request = ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Requester cannot self-approve.")

        with self.assertRaisesRegex(Forbidden, "separation of duties"):
            self.store.approve(same_identity_approver, run.run_id, approval_request)
        with self.assertRaisesRegex(Forbidden, "separation of duties"):
            self.store.reject(same_identity_approver, run.run_id, approval_request)

        event_types = {event["event_type"] for event in self.store.events_after(run.tenant_id, run.run_id)}
        self.assertIn("APPROVAL_DENIED", event_types)
        self.assertIn("REJECTION_DENIED", event_types)

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

    def test_audit_events_atomically_enqueue_external_anchor_envelopes(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-anchor-outbox")

        events = self.store.events_after(self.operator.tenant_id, run.run_id)
        pending = self.store.pending_audit_anchors(limit=100)

        self.assertEqual(len(pending), len(events))
        self.assertEqual(
            {record["envelope"]["event_id"] for record in pending},
            {event["event_id"] for event in events},
        )
        self.assertTrue(all(record["envelope"]["event_hash"] for record in pending))
        self.assertTrue(all(record["attempts"] == 0 for record in pending))

    def test_audit_anchor_dispatcher_signs_exact_bytes_and_tracks_delivery(self) -> None:
        self.store.create_run(self.operator, request(), "create-anchor-delivery")
        secret = "audit-anchor-secret-that-is-at-least-thirty-two-bytes"
        requests: list[httpx.Request] = []

        def handler(request_value: httpx.Request) -> httpx.Response:
            requests.append(request_value)
            expected = hmac.new(secret.encode("utf-8"), request_value.content, hashlib.sha256).hexdigest()
            self.assertEqual(request_value.headers["x-loopos-signature-256"], f"sha256={expected}")
            self.assertEqual(request_value.headers["x-loopos-event-id"], json.loads(request_value.content)["event_id"])
            return httpx.Response(202)

        dispatcher = AuditAnchorDispatcher(
            self.store,
            "https://audit.example.com/loopos/events",
            secret,
            transport=httpx.MockTransport(handler),
        )
        try:
            delivered = asyncio.run(dispatcher.drain(limit=100))
        finally:
            asyncio.run(dispatcher.close())

        self.assertEqual(delivered, len(requests))
        self.assertGreater(delivered, 0)
        self.assertEqual(self.store.audit_anchor_backlog(), 0)

    def test_audit_anchor_dispatcher_does_not_buffer_a_success_response_body(self) -> None:
        self.store.append_event(self.operator.tenant_id, None, "AUDIT_ANCHOR_LARGE_RESPONSE", None, self.operator.user_id, {})

        class TrackingStream(httpx.AsyncByteStream):
            def __init__(self) -> None:
                self.consumed = False

            async def __aiter__(self):
                self.consumed = True
                yield b"x" * 2_000_000

            async def aclose(self) -> None:
                return None

        response_body = TrackingStream()
        dispatcher = AuditAnchorDispatcher(
            self.store,
            "https://audit.example.com/loopos/events",
            "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            transport=httpx.MockTransport(lambda _request: httpx.Response(202, stream=response_body)),
        )
        try:
            delivered = asyncio.run(dispatcher.drain(limit=1))
        finally:
            asyncio.run(dispatcher.close())

        self.assertEqual(delivered, 1)
        self.assertFalse(response_body.consumed)

    def test_audit_anchor_dispatcher_filters_tenant_scoped_retry(self) -> None:
        self.store.append_event(self.operator.tenant_id, None, "PRIMARY_RETRY", None, self.operator.user_id, {})
        secondary_actor = Actor(tenant_id="tenant-other", user_id="operator", name="Other Operator", role="Operator")
        self.store.append_event(secondary_actor.tenant_id, None, "SECONDARY_RETRY", None, secondary_actor.user_id, {})
        dispatcher = AuditAnchorDispatcher(
            self.store,
            "https://audit.example.com/loopos/events",
            "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            transport=httpx.MockTransport(lambda _request: httpx.Response(202)),
        )
        try:
            delivered = asyncio.run(dispatcher.drain(limit=100, tenant_id=self.operator.tenant_id))
        finally:
            asyncio.run(dispatcher.close())

        self.assertGreater(delivered, 0)
        self.assertEqual(self.store.audit_anchor_backlog(self.operator.tenant_id), 0)
        self.assertGreater(self.store.audit_anchor_backlog(secondary_actor.tenant_id), 0)

    def test_audit_anchor_dispatcher_retains_failures_for_retry(self) -> None:
        self.store.create_run(self.operator, request(), "create-anchor-retry")
        dispatcher = AuditAnchorDispatcher(
            self.store,
            "https://audit.example.com/loopos/events",
            "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            transport=httpx.MockTransport(lambda _request: httpx.Response(503, json={"detail": "unavailable"})),
        )
        try:
            delivered = asyncio.run(dispatcher.drain(limit=100))
        finally:
            asyncio.run(dispatcher.close())

        self.assertEqual(delivered, 0)
        pending = self.store.pending_audit_anchors(limit=100, include_deferred=True)
        self.assertGreater(len(pending), 0)
        self.assertTrue(all(record["attempts"] == 1 for record in pending))
        self.assertTrue(all("503" in record["last_error"] for record in pending))

    def test_audit_anchor_delivery_status_rejects_stale_delivery(self) -> None:
        envelope = self.store.append_event(
            self.operator.tenant_id,
            None,
            "AUDIT_ANCHOR_PROBE",
            None,
            self.operator.user_id,
            {"probe": True},
        )
        self.store.mark_audit_anchor_delivered(envelope["event_id"])
        self.store.connection.execute(
            "UPDATE audit_anchor_outbox SET delivered_at = ? WHERE event_id = ?",
            ((datetime.now(timezone.utc) - timedelta(days=365)).isoformat(), envelope["event_id"]),
        )

        status = self.store.audit_anchor_delivery_status(max_age_seconds=300)

        self.assertFalse(status["verified"])
        self.assertFalse(status["fresh"])
        self.assertEqual(status["delivered_count"], 1)

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
        self.assertEqual({item.headers["x-loopos-run-id"] for item in calls}, {run.run_id})
        self.assertEqual(len({item.headers["x-loopos-invocation-id"] for item in calls}), 1)
        self.assertTrue(next(iter(calls)).headers["x-loopos-invocation-id"].startswith("invoke-"))
        succeeded = [
            event for event in self.store.events_after(run.tenant_id, run.run_id)
            if event["event_type"] == "TOOL_SUCCEEDED"
        ]
        self.assertEqual(len(succeeded), 1)
        observability = succeeded[0]["payload"]["observability"]
        self.assertGreaterEqual(observability["latency_ms"], 0)
        self.assertEqual(observability["retry_count"], 2)

    def test_failed_tool_invocation_records_failure_observability(self) -> None:
        execution_plan = plan(tool="record_action", arguments={"operation": "unsupported"})
        run = self.store.create_run(self.operator, request(execution_plan=execution_plan), "create-invalid-tool-input")

        with self.assertRaises(TerminalToolFailure):
            asyncio.run(self.tools.execute_action(run.tenant_id, run.run_id, execution_plan.action, 3))

        failed = [
            event for event in self.store.events_after(run.tenant_id, run.run_id)
            if event["event_type"] == "TOOL_FAILED"
        ]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["payload"]["code"], "invalid_tool_input")
        observability = failed[0]["payload"]["observability"]
        self.assertGreaterEqual(observability["latency_ms"], 0)
        self.assertEqual(observability["retry_count"], 0)

    def test_connector_response_limit_is_enforced_while_streaming(self) -> None:
        class OversizedStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{"status":"'
                yield b"x" * 100

        bounded_settings = replace(self.settings, allowed_http_hosts=("localhost",), http_max_response_bytes=100)
        bounded_tools = ToolRegistry(
            bounded_settings,
            self.store,
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, stream=OversizedStream())),
        )
        try:
            with self.assertRaisesRegex(TerminalToolFailure, "size limit"):
                asyncio.run(bounded_tools._get_json("http://localhost/oversized"))
        finally:
            asyncio.run(bounded_tools.close())

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

    def test_connector_urls_reject_query_strings_and_fragments(self) -> None:
        for suffix in ("?token=secret", "#fragment"):
            with self.subTest(suffix=suffix):
                with self.assertRaisesRegex(Exception, "query strings or fragments"):
                    self.tools._validate_endpoint(f"https://enterprise.example/evidence{suffix}")

    def test_production_connector_credentials_fail_closed_without_a_credential_broker(self) -> None:
        connector_settings = replace(
            self.settings,
            allow_dev_auth=False,
            allowed_http_hosts=("enterprise.example",),
            connector_bearer_tokens={"enterprise.example": "static-token"},
        )
        connector_tools = ToolRegistry(connector_settings, self.store, transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"ok": True})))
        try:
            with self.assertRaisesRegex(TerminalToolFailure, "short-lived credential injection broker"):
                connector_tools._connector_headers("https://enterprise.example/action")
        finally:
            asyncio.run(connector_tools.close())

    def test_connector_dns_rejects_non_global_addresses(self) -> None:
        with patch(
            "loopos_authority.tools.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("100.64.0.1", 443))],
        ):
            with self.assertRaisesRegex(Exception, "non-global"):
                self.tools._validate_endpoint("https://enterprise.example/evidence")

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

    def test_restart_reconciliation_keeps_kill_switch_tenant_blocked(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-restart-kill-switch")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        self.store.activate_kill_switch(self.executive, "Keep tenant stopped during restart.")
        self.store.connection.execute(
            "UPDATE runs SET runner_status = 'running' WHERE tenant_id = ? AND run_id = ?",
            (run.tenant_id, run.run_id),
        )
        self.store.connection.execute(
            "UPDATE execution_jobs SET status = 'running', lease_owner = 'dead-worker', lease_expires_at = NULL WHERE run_id = ?",
            (run.run_id,),
        )

        recovered = self.store.requeue_incomplete_runs()

        self.assertEqual(recovered, [])
        blocked = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(blocked.state, "BLOCKED")
        self.assertEqual(blocked.runner_status, "failed")
        job = self.store.connection.execute("SELECT status, last_error FROM execution_jobs WHERE run_id = ?", (run.run_id,)).fetchone()
        self.assertEqual(job["status"], "failed")
        self.assertIn("kill switch", job["last_error"].lower())

    def test_execution_jobs_are_durable_and_exclusively_leased(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-durable-job")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)

        first_claim = self.store.claim_execution_jobs("worker-a", lease_seconds=60, limit=10)
        competing_claim = self.store.claim_execution_jobs("worker-b", lease_seconds=60, limit=10)

        self.assertEqual(len(first_claim), 1)
        self.assertEqual(first_claim[0]["run_id"], run.run_id)
        self.assertEqual(first_claim[0]["command"], "execute")
        self.assertEqual(first_claim[0]["attempts"], 1)
        self.assertEqual(competing_claim, [])
        self.assertEqual(self.store.execution_job_backlog(), 1)

        self.store.connection.execute(
            "UPDATE execution_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
            (first_claim[0]["job_id"],),
        )
        reclaimed = self.store.claim_execution_jobs("worker-b", lease_seconds=60, limit=10)

        self.assertEqual(len(reclaimed), 1)
        self.assertEqual(reclaimed[0]["job_id"], first_claim[0]["job_id"])
        self.assertEqual(reclaimed[0]["attempts"], 2)
        self.store.complete_execution_job(reclaimed[0]["job_id"], "worker-b")
        self.assertEqual(self.store.execution_job_backlog(), 0)

    def test_execution_job_lease_can_only_be_renewed_by_its_owner(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-renewable-job")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        job = self.store.claim_execution_jobs("worker-a", lease_seconds=30, limit=1)[0]

        with self.assertRaises(Conflict):
            self.store.renew_execution_job(job["job_id"], "worker-b", lease_seconds=60)

        renewed = self.store.renew_execution_job(job["job_id"], "worker-a", lease_seconds=60)
        self.assertGreater(renewed, job["lease_expires_at"])

    def test_expired_execution_jobs_stop_at_the_retry_budget(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-worker-retry-budget")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)

        first = self.store.claim_execution_jobs("worker-a", lease_seconds=30, limit=1, max_attempts=2)[0]
        self.store.connection.execute(
            "UPDATE execution_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
            (first["job_id"],),
        )
        second = self.store.claim_execution_jobs("worker-b", lease_seconds=30, limit=1, max_attempts=2)[0]
        self.assertEqual(second["attempts"], 2)
        self.store.connection.execute(
            "UPDATE execution_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
            (second["job_id"],),
        )

        exhausted = self.store.claim_execution_jobs("worker-c", lease_seconds=30, limit=1, max_attempts=2)

        self.assertEqual(exhausted, [])
        job = self.store.connection.execute(
            "SELECT status, attempts, last_error FROM execution_jobs WHERE job_id = ?",
            (second["job_id"],),
        ).fetchone()
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["attempts"], 2)
        self.assertIn("maximum retry attempts", job["last_error"])
        failed_run = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(failed_run.runner_status, "failed")
        self.assertEqual(self.store.execution_job_backlog(), 0)

    def test_execution_worker_stops_when_lease_renewal_has_a_storage_error(self) -> None:
        class OwnerTask:
            cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        owner_task = OwnerTask()
        worker = ExecutionJobWorker(self.store, self.engine, worker_id="heartbeat-fail-closed", lease_seconds=30)
        with patch.object(self.store, "renew_execution_job", side_effect=RuntimeError("database unavailable")):
            with patch("loopos_authority.worker.asyncio.sleep", new=AsyncMock()):
                asyncio.run(worker._heartbeat("job-missing", owner_task))  # type: ignore[arg-type]

        self.assertTrue(owner_task.cancelled)

    def test_exhausted_execution_job_releases_the_run_as_failed(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-terminal-job")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        job = self.store.claim_execution_jobs("worker-a", lease_seconds=30, limit=1)[0]
        self.store.claim_run(run.tenant_id, run.run_id)

        self.store.fail_execution_job(job["job_id"], "worker-a", "Worker infrastructure failed.", max_attempts=1)

        failed_run = self.store.get_run(run.tenant_id, run.run_id)
        failed_job = self.store.connection.execute(
            "SELECT * FROM execution_jobs WHERE job_id = ?",
            (job["job_id"],),
        ).fetchone()
        self.assertEqual(failed_job["status"], "failed")
        self.assertEqual(failed_run.runner_status, "failed")
        self.assertEqual(failed_run.last_error, "Worker infrastructure failed.")
        self.assertEqual(self.store.execution_job_backlog(), 0)

    def test_execution_worker_completes_and_acknowledges_a_durable_job(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-worker-job")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        worker = ExecutionJobWorker(self.store, self.engine, worker_id="worker-a", lease_seconds=30)

        processed = asyncio.run(worker.run_once(dispatch_source="external"))

        self.assertEqual(processed, 1)
        self.assertEqual(self.store.execution_job_backlog(), 0)
        dispatch = self.store.operational_signal_status(
            "execution_worker_dispatch",
            max_age_seconds=180,
            required_source="external",
        )
        self.assertTrue(dispatch["verified"])
        self.assertEqual(dispatch["detail"]["claimed_jobs"], 1)
        completed = self.store.get_run(run.tenant_id, run.run_id)
        self.assertEqual(completed.state, "EFFECTIVENESS_PROVEN")
        self.assertEqual(completed.runner_status, "completed")

    def test_execution_worker_dispatch_heartbeat_expires_and_is_mode_specific(self) -> None:
        worker = ExecutionJobWorker(self.store, self.engine, worker_id="heartbeat-worker", lease_seconds=30)
        asyncio.run(worker.run_once(dispatch_source="external"))

        self.assertTrue(
            self.store.operational_signal_status(
                "execution_worker_dispatch",
                max_age_seconds=180,
                required_source="external",
            )["verified"]
        )
        self.assertFalse(
            self.store.operational_signal_status(
                "execution_worker_dispatch",
                max_age_seconds=180,
                required_source="internal",
            )["verified"]
        )
        self.store.connection.execute(
            """
            UPDATE operational_signals
            SET observed_at = '2000-01-01T00:00:00+00:00'
            WHERE signal_name = 'execution_worker_dispatch' AND source = 'external'
            """
        )
        self.assertFalse(
            self.store.operational_signal_status(
                "execution_worker_dispatch",
                max_age_seconds=180,
                required_source="external",
            )["verified"]
        )

    def test_execution_worker_reclaims_a_run_after_the_previous_worker_dies(self) -> None:
        run = self.store.create_run(self.operator, request(), "create-worker-recovery")
        self.store.queue_run(run.tenant_id, run.run_id, self.operator.user_id)
        abandoned = self.store.claim_execution_jobs("dead-worker", lease_seconds=30, limit=1)[0]
        self.store.claim_run(run.tenant_id, run.run_id)
        self.store.connection.execute(
            "UPDATE execution_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
            (abandoned["job_id"],),
        )
        worker = ExecutionJobWorker(self.store, self.engine, worker_id="recovery-worker", lease_seconds=30)

        processed = asyncio.run(worker.run_once())

        self.assertEqual(processed, 1)
        self.assertEqual(self.store.execution_job_backlog(), 0)
        self.assertEqual(self.store.get_run(run.tenant_id, run.run_id).state, "EFFECTIVENESS_PROVEN")
        claimed_events = [
            event for event in self.store.events_after(run.tenant_id, run.run_id)
            if event["event_type"] == "RUN_CLAIMED"
        ]
        self.assertTrue(claimed_events[-1]["payload"]["reclaimed"])

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
        self.assertEqual(self.store.execution_job_backlog(), 1)
        asyncio.run(self.engine.execute(run.tenant_id, run.run_id))
        self.assertEqual(self.store.get_run(run.tenant_id, run.run_id).state, "EFFECTIVENESS_PROVEN")


class StorageBackendTests(unittest.TestCase):
    def test_default_storage_backend_is_sqlite(self) -> None:
        with patch.dict("os.environ", {"LOOPOS_REPO_ROOT": str(REPO_ROOT)}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.storage_backend, "sqlite")
        self.assertIsNone(settings.postgres_dsn)

    def test_vercel_defaults_to_external_worker_dispatch_and_production_auth(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LOOPOS_REPO_ROOT": str(REPO_ROOT),
                "LOOPOS_SESSION_HMAC_SECRET": "vercel-session-secret-that-is-at-least-thirty-two-bytes",
                "LOOPOS_RATE_LIMIT_REQUESTS": "120",
                "LOOPOS_RATE_LIMIT_WINDOW_SECONDS": "60",
                "VERCEL": "1",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.execution_worker_mode, "external")
        self.assertFalse(settings.allow_dev_auth)

        with patch.dict("os.environ", {"VERCEL": "1"}, clear=True):
            with self.assertRaisesRegex(ValueError, "LOOPOS_SESSION_HMAC_SECRET"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {
                "LOOPOS_ALLOW_DEV_AUTH": "true",
                "LOOPOS_SESSION_HMAC_SECRET": "vercel-session-secret-that-is-at-least-thirty-two-bytes",
                "VERCEL": "1",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "cannot be enabled on Vercel"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {
                "LOOPOS_SESSION_HMAC_SECRET": "vercel-session-secret-that-is-at-least-thirty-two-bytes",
                "LOOPOS_EXECUTION_WORKER_MODE": "internal",
                "VERCEL": "1",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "external.*on Vercel"):
                Settings.from_env()

    def test_invalid_storage_backend_is_rejected(self) -> None:
        with patch.dict("os.environ", {"LOOPOS_STORAGE_BACKEND": "browser"}, clear=True):
            with self.assertRaisesRegex(ValueError, "LOOPOS_STORAGE_BACKEND"):
                Settings.from_env()

    def test_non_finite_runtime_windows_are_rejected(self) -> None:
        for value in ("Infinity", "NaN", "-Infinity"):
            with self.subTest(value=value):
                with patch.dict(
                    "os.environ",
                    {
                        "LOOPOS_REPO_ROOT": str(REPO_ROOT),
                        "LOOPOS_EXECUTION_WORKER_HEARTBEAT_MAX_AGE_SECONDS": value,
                    },
                    clear=True,
                ):
                    with self.assertRaisesRegex(ValueError, "positive finite number"):
                        Settings.from_env()

    def test_worker_integer_windows_require_positive_integers(self) -> None:
        for variable in (
            "LOOPOS_EXECUTION_JOB_LEASE_SECONDS",
            "LOOPOS_EXECUTION_JOB_MAX_ATTEMPTS",
        ):
            for value in ("0", "-1", "0.5", "1.5", "Infinity", "NaN"):
                with self.subTest(variable=variable, value=value):
                    with patch.dict(
                        "os.environ",
                        {
                            "LOOPOS_REPO_ROOT": str(REPO_ROOT),
                            variable: value,
                        },
                        clear=True,
                    ):
                        with self.assertRaisesRegex(ValueError, "positive integer"):
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

    def test_audit_anchor_configuration_requires_a_secure_complete_binding(self) -> None:
        with patch.dict("os.environ", {"LOOPOS_AUDIT_ANCHOR_URL": "https://audit.example.com/events"}, clear=True):
            with self.assertRaisesRegex(ValueError, "LOOPOS_AUDIT_ANCHOR"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {
                "LOOPOS_AUDIT_ANCHOR_URL": "http://audit.example.com/events",
                "LOOPOS_AUDIT_ANCHOR_HMAC_SECRET": "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {
                "LOOPOS_AUDIT_ANCHOR_URL": "https://audit.example.com/events",
                "LOOPOS_AUDIT_ANCHOR_HMAC_SECRET": "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.audit_anchor_url, "https://audit.example.com/events")

        with patch.dict(
            "os.environ",
            {
                "LOOPOS_AUDIT_ANCHOR_URL": "http://localhost:9000/events",
                "LOOPOS_AUDIT_ANCHOR_HMAC_SECRET": "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
                "LOOPOS_ALLOW_DEV_AUTH": "true",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.audit_anchor_url, "http://localhost:9000/events")

    def test_production_app_rejects_a_local_http_audit_anchor(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path("unused.db"),
            session_secret="production-anchor-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=(),
            cors_origins=(),
            audit_anchor_url="http://localhost:9000/events",
            audit_anchor_hmac_secret="audit-anchor-secret-that-is-at-least-thirty-two-bytes",
        )

        with self.assertRaisesRegex(ValueError, "HTTPS"):
            create_app(settings)

        with patch.dict(
            "os.environ",
            {"LOOPOS_BACKUP_RESTORE_EVIDENCE_SHA256": "NOT-A-SHA256"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {"LOOPOS_BACKUP_RESTORE_EVIDENCE_URL": "https://evidence.example.com/restore.json?token=secret"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "credential-free HTTPS"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {"LOOPOS_OPERATIONAL_EVIDENCE_SHA256": "NOT-A-SHA256"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
                Settings.from_env()

        with patch.dict(
            "os.environ",
            {"LOOPOS_RETENTION_POLICY_URL": "https://policy.example.com/retention?token=secret"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "credential-free HTTPS"):
                Settings.from_env()

    def test_operational_bindings_require_a_digest_and_reject_stale_restore_evidence(self) -> None:
        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path("unused.db"),
            session_secret="operations-test-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=False,
            allowed_http_hosts=(),
            cors_origins=(),
            retention_policy_url="https://policy.example.com/retention",
            support_contact="loopos-operations@example.com",
            outbound_policy_mode="deny_all",
            backup_restore_evidence_url="https://evidence.example.com/restore-test",
            backup_restore_verified_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        )

        bindings = operational_binding_status(settings)

        self.assertFalse(bindings["retention_verified"])
        self.assertFalse(bindings["support_verified"])
        self.assertFalse(bindings["outbound_policy_verified"])
        self.assertFalse(bindings["backup_restore_verified"])
        operational_verified_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        proven_settings = replace(
            settings,
            operational_evidence_url="https://evidence.example.com/operational-controls.json",
            operational_evidence_sha256="b" * 64,
            operational_evidence_verified_at=operational_verified_at,
        )
        proven_bindings = operational_binding_status(proven_settings)
        self.assertTrue(proven_bindings["retention_verified"])
        self.assertTrue(proven_bindings["support_verified"])
        self.assertTrue(proven_bindings["outbound_policy_verified"])
        stale_operational = replace(
            proven_settings,
            operational_evidence_verified_at=(datetime.now(timezone.utc) - timedelta(days=91)).isoformat(),
        )
        self.assertFalse(operational_binding_status(stale_operational)["retention_verified"])
        self.assertFalse(operational_binding_status(stale_operational)["support_verified"])
        self.assertFalse(operational_binding_status(stale_operational)["outbound_policy_verified"])
        self.assertTrue(
            operational_binding_status(replace(proven_settings, backup_restore_evidence_sha256="a" * 64))[
                "backup_restore_verified"
            ]
        )
        self.assertFalse(
            operational_binding_status(
                replace(
                    settings,
                    backup_restore_evidence_sha256="a" * 64,
                    backup_restore_verified_at=(datetime.now(timezone.utc) - timedelta(days=91)).isoformat(),
                )
            )["backup_restore_verified"]
        )

    def test_supabase_migration_preserves_authority_tables_and_audit_controls(self) -> None:
        migration = (REPO_ROOT / "supabase" / "migrations" / "20260720010000_loopos_authority.sql").read_text(encoding="utf-8")

        for table in ["runs", "execution_jobs", "kill_switches", "operational_signals", "approvals", "evidence", "tool_invocations", "probe_results", "action_artifacts", "workspaces", "release_initiatives", "connector_events", "audit_events", "audit_anchor_outbox"]:
            self.assertIn(f"create table if not exists {table}", migration)
            self.assertIn(f"alter table {table} enable row level security", migration)
        self.assertIn("audit_events_no_update", migration)
        self.assertIn("audit_events_no_delete", migration)
        self.assertIn("select rolname from pg_roles where rolname in ('anon', 'authenticated')", migration)
        self.assertIn("execute format('revoke all on runs, execution_jobs", migration)

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
            worker_token="api-worker-token-that-is-at-least-thirty-two-bytes",
            execution_worker_poll_seconds=0.01,
        )
        self.app = create_app(settings)
        self.store = self.app.state.store
        self.operator = Actor(tenant_id="tenant-api", user_id="operator", name="Operator", role="Operator")
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        session = self.client.post("/v1/dev/sessions", json={"tenant_id": "tenant-api", "user_id": "operator", "name": "Operator", "role": "Operator"})
        self.token = session.json()["access_token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.tempdir.cleanup()

    def wait_for_run_state(self, run_id: str, expected_state: str, timeout_seconds: float = 5.0) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        last_run: dict[str, object] | None = None
        while time.monotonic() < deadline:
            response = self.client.get(f"/v1/runs/{run_id}", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            last_run = response.json()
            if last_run["state"] == expected_state:
                return last_run
            time.sleep(0.01)
        self.fail(f"Run {run_id} did not reach {expected_state}; last observed record: {last_run}")

    def test_kill_switch_api_is_executive_only_and_fail_closed_for_new_runs(self) -> None:
        status = self.client.get("/v1/controls/kill-switch", headers=self.headers)
        self.assertEqual(status.status_code, 200, status.text)
        self.assertFalse(status.json()["active"])

        operator_activation = self.client.post(
            "/v1/controls/kill-switch",
            headers=self.headers,
            json={"reason": "Operator must not stop the tenant."},
        )
        self.assertEqual(operator_activation.status_code, 403, operator_activation.text)

        executive_session = self.client.post(
            "/v1/dev/sessions",
            json={"tenant_id": "tenant-api", "user_id": "executive", "name": "Executive", "role": "Executive"},
        ).json()
        executive_headers = {"authorization": f"Bearer {executive_session['access_token']}"}
        activated = self.client.post(
            "/v1/controls/kill-switch",
            headers=executive_headers,
            json={"reason": "Stop tenant after the live control drill."},
        )
        self.assertEqual(activated.status_code, 200, activated.text)
        self.assertTrue(activated.json()["active"])
        self.assertEqual(activated.json()["scope"], "tenant")

        blocked_create = self.client.post(
            "/v1/runs",
            headers={**self.headers, "idempotency-key": "kill-switch-create"},
            json=request().model_dump(mode="json"),
        )
        self.assertEqual(blocked_create.status_code, 409, blocked_create.text)

        deactivated = self.client.post(
            "/v1/controls/kill-switch/deactivate",
            headers=executive_headers,
            json={"reason": "Control drill complete; new runs require normal approval."},
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertFalse(deactivated.json()["active"])

        created = self.client.post(
            "/v1/runs",
            headers={**self.headers, "idempotency-key": "kill-switch-create-after"},
            json=request().model_dump(mode="json"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        audit = self.client.get("/v1/audit/verify", headers=executive_headers)
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertTrue(audit.json()["valid"])

    def test_workspace_api_is_tenant_scoped_and_uses_optimistic_concurrency(self) -> None:
        created = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**self.headers, "if-none-match": "*"},
            json={"document": workspace_document()},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.headers["etag"], '"1"')
        self.assertEqual(created.json()["revision"], 1)

        listed = self.client.get("/v1/workspaces", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["workspace_id"] for item in listed.json()], ["workspace-authoritative"])

        updated = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**self.headers, "if-match": '"1"'},
            json={"document": workspace_document(name="Authoritative workspace v2")},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.headers["etag"], '"2"')
        self.assertEqual(updated.json()["document"]["name"], "Authoritative workspace v2")

        stale = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**self.headers, "if-match": '"1"'},
            json={"document": workspace_document(name="Stale overwrite")},
        )
        self.assertEqual(stale.status_code, 409)

        other_session = self.client.post(
            "/v1/dev/sessions",
            json={"tenant_id": "tenant-other", "user_id": "operator", "name": "Other Operator", "role": "Operator"},
        ).json()
        other_headers = {"authorization": f"Bearer {other_session['access_token']}"}
        self.assertEqual(self.client.get("/v1/workspaces", headers=other_headers).json(), [])
        self.assertEqual(
            self.client.get("/v1/workspaces/workspace-authoritative", headers=other_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                "/v1/workspaces/workspace-authoritative",
                headers={**other_headers, "if-match": '"2"'},
                json={"document": workspace_document(name="Foreign overwrite")},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                "/v1/workspaces/workspace-authoritative",
                headers={**other_headers, "if-match": '"2"'},
            ).status_code,
            404,
        )
        owner_read = self.client.get("/v1/workspaces/workspace-authoritative", headers=self.headers)
        self.assertEqual(owner_read.status_code, 200)
        self.assertEqual(owner_read.json()["revision"], 2)

    def test_workspace_api_rejects_mismatched_ids_and_auditor_writes(self) -> None:
        mismatch = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**self.headers, "if-none-match": "*"},
            json={"document": workspace_document(workspace_id="workspace-other")},
        )
        self.assertEqual(mismatch.status_code, 400)

        auditor = self.client.post(
            "/v1/dev/sessions",
            json={"tenant_id": "tenant-api", "user_id": "auditor", "name": "Auditor", "role": "Auditor"},
        ).json()
        denied = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={"authorization": f"Bearer {auditor['access_token']}", "if-none-match": "*"},
            json={"document": workspace_document()},
        )
        self.assertEqual(denied.status_code, 403)

    def test_workspace_api_rejects_malformed_nested_documents(self) -> None:
        malformed_approval = workspace_document()
        malformed_approval["approvals"] = [{"approval_id": "incomplete"}]
        rejected_approval = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**self.headers, "if-none-match": "*"},
            json={"document": malformed_approval},
        )
        self.assertEqual(rejected_approval.status_code, 422, rejected_approval.text)

        malformed_initiative = workspace_document()
        malformed_initiative["initiatives"] = [{"id": "incomplete"}]
        rejected_initiative = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**self.headers, "if-none-match": "*"},
            json={"document": malformed_initiative},
        )
        self.assertEqual(rejected_initiative.status_code, 422, rejected_initiative.text)

    def test_release_api_rejects_weak_evidence_hashes_and_missing_decisions(self) -> None:
        weak_hash = release_request().model_dump(mode="json")
        weak_hash["release_assurance"]["external_refs"][0]["evidence_hash"] = "local-fnv1a-deadbeef"
        rejected_hash = self.client.post(
            "/v1/release-initiatives",
            headers={**self.headers, "idempotency-key": "release-weak-hash-key"},
            json=weak_hash,
        )
        self.assertEqual(rejected_hash.status_code, 422, rejected_hash.text)

        missing_decision = release_request().model_dump(mode="json")
        missing_decision["release_assurance"]["gates"][0].pop("last_decision")
        missing_decision["release_assurance"]["decisions"] = [missing_decision["release_assurance"]["decisions"][1]]
        rejected_decision = self.client.post(
            "/v1/release-initiatives",
            headers={**self.headers, "idempotency-key": "release-missing-decision-key"},
            json=missing_decision,
        )
        self.assertEqual(rejected_decision.status_code, 422, rejected_decision.text)

    def test_workspace_delete_requires_current_revision_and_preserves_audit_proof(self) -> None:
        executive = self.client.post(
            "/v1/dev/sessions",
            json={"tenant_id": "tenant-api", "user_id": "executive", "name": "Executive", "role": "Executive"},
        ).json()
        executive_headers = {"authorization": f"Bearer {executive['access_token']}"}
        created = self.client.put(
            "/v1/workspaces/workspace-authoritative",
            headers={**executive_headers, "if-none-match": "*"},
            json={"document": workspace_document()},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            self.client.delete(
                "/v1/workspaces/workspace-authoritative",
                headers={**executive_headers, "if-match": '"0"'},
            ).status_code,
            409,
        )
        deleted = self.client.delete(
            "/v1/workspaces/workspace-authoritative",
            headers={**executive_headers, "if-match": '"1"'},
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)
        self.assertEqual(
            self.client.get("/v1/workspaces/workspace-authoritative", headers=executive_headers).status_code,
            404,
        )
        audit = self.client.get("/v1/audit/verify", headers=executive_headers)
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertTrue(audit.json()["valid"])
        events = self.client.get("/v1/events", headers=executive_headers).json()
        self.assertIn("WORKSPACE_CREATED", [event["event_type"] for event in events])
        self.assertIn("WORKSPACE_DELETED", [event["event_type"] for event in events])

    def test_workspace_write_preflight_allows_revision_headers(self) -> None:
        preflight = self.client.options(
            "/v1/workspaces/workspace-authoritative",
            headers={
                "origin": "http://127.0.0.1:5173",
                "access-control-request-method": "PUT",
                "access-control-request-headers": "authorization,content-type,if-match,if-none-match",
            },
        )

        self.assertEqual(preflight.status_code, 200, preflight.text)
        self.assertIn("PUT", preflight.headers["access-control-allow-methods"])
        self.assertEqual(preflight.headers["access-control-allow-credentials"], "true")
        allowed_headers = preflight.headers["access-control-allow-headers"].lower()
        self.assertIn("if-match", allowed_headers)
        self.assertIn("if-none-match", allowed_headers)

    def test_request_id_is_propagated_and_invalid_values_are_replaced(self) -> None:
        supplied = self.client.get("/health/live", headers={"x-request-id": "ui-trace-123"})
        self.assertEqual(supplied.status_code, 200)
        self.assertEqual(supplied.headers["x-request-id"], "ui-trace-123")

        invalid = self.client.get("/health/live", headers={"x-request-id": "bad value"})
        self.assertEqual(invalid.status_code, 200)
        self.assertRegex(invalid.headers["x-request-id"], r"^request-[0-9a-f-]+$")

    def test_audit_anchor_operations_are_role_restricted_and_fail_when_unconfigured(self) -> None:
        operator_status = self.client.get("/v1/audit/anchors/status", headers=self.headers)
        self.assertEqual(operator_status.status_code, 403)

        primary_event = self.store.append_event("tenant-api", None, "STATUS_PRIMARY", None, "operator", {})
        primary_pending_event = self.store.append_event("tenant-api", None, "STATUS_PRIMARY_PENDING", None, "operator", {})
        secondary_event = self.store.append_event("tenant-other", None, "STATUS_SECONDARY", None, "operator", {})
        self.store.mark_audit_anchor_delivered(primary_event["event_id"])

        executive = self.client.post(
            "/v1/dev/sessions",
            json={"tenant_id": "tenant-api", "user_id": "executive", "name": "Executive", "role": "Executive"},
        ).json()
        executive_headers = {"authorization": f"Bearer {executive['access_token']}"}
        status_response = self.client.get("/v1/audit/anchors/status", headers=executive_headers)
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertFalse(status_response.json()["configured"])
        self.assertEqual(status_response.json()["backlog"], 1)
        self.assertEqual(status_response.json()["delivery"]["delivered_count"], 1)
        self.assertNotEqual(primary_event["event_id"], primary_pending_event["event_id"])
        self.assertNotEqual(primary_event["event_id"], secondary_event["event_id"])
        self.assertEqual(self.client.post("/v1/audit/anchors/drain", headers=executive_headers).status_code, 503)

    def test_audit_anchor_retry_is_tenant_scoped_for_executive(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        async def fake_drain(*args: object, **kwargs: object) -> int:
            calls.append((args, kwargs))
            return 1

        settings = Settings(
            repo_root=REPO_ROOT,
            database_path=Path(self.tempdir.name) / "tenant-audit-drain.db",
            session_secret="tenant-audit-drain-secret-that-is-at-least-thirty-two-bytes",
            allow_dev_auth=True,
            allowed_http_hosts=(),
            cors_origins=("http://127.0.0.1:5173",),
            audit_anchor_url="https://audit.example.com/loopos/events",
            audit_anchor_hmac_secret="tenant-audit-anchor-secret-that-is-at-least-thirty-two-bytes",
            audit_anchor_poll_seconds=3600,
            execution_worker_mode="external",
        )
        with patch.object(AuditAnchorDispatcher, "drain", new=fake_drain):
            app = create_app(settings)
            client = TestClient(app)
            try:
                executive = client.post(
                    "/v1/dev/sessions",
                    json={"tenant_id": "tenant-api", "user_id": "executive", "name": "Executive", "role": "Executive"},
                ).json()
                response = client.post(
                    "/v1/audit/anchors/drain",
                    headers={"authorization": f"Bearer {executive['access_token']}"},
                )
            finally:
                client.close()
                app.state.store.close()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["delivered"], 1)
        self.assertEqual(response.json()["backlog"], 0)
        self.assertTrue(any(kwargs == {"tenant_id": "tenant-api"} for _args, kwargs in calls))

    def test_execution_job_operations_require_worker_authority(self) -> None:
        self.assertEqual(self.client.get("/v1/operations/jobs/status", headers=self.headers).status_code, 403)
        self.assertEqual(self.client.post("/v1/operations/jobs/drain").status_code, 401)
        self.assertEqual(
            self.client.post("/v1/operations/jobs/drain", headers={"x-loopos-worker-token": "wrong-token"}).status_code,
            401,
        )
        # Freeze both jobs before the internal worker can claim the first one.
        with self.store.lock:
            primary_run = self.store.create_run(self.operator, request(), "status-primary-run")
            self.store.queue_run(primary_run.tenant_id, primary_run.run_id, self.operator.user_id)
            secondary_actor = Actor(tenant_id="tenant-other", user_id="operator", name="Other Operator", role="Operator")
            secondary_run = self.store.create_run(secondary_actor, request(), "status-secondary-run")
            self.store.queue_run(secondary_run.tenant_id, secondary_run.run_id, secondary_actor.user_id)
            self.store.connection.execute(
                "UPDATE execution_jobs SET available_at = '2099-01-01T00:00:00+00:00' WHERE run_id IN (?, ?)",
                (primary_run.run_id, secondary_run.run_id),
            )
        executive = self.client.post(
            "/v1/dev/sessions",
            json={"tenant_id": "tenant-api", "user_id": "executive", "name": "Executive", "role": "Executive"},
        ).json()
        status_response = self.client.get(
            "/v1/operations/jobs/status",
            headers={"authorization": f"Bearer {executive['access_token']}"},
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertEqual(status_response.json()["backlog"], 1)
        executive_drain = self.client.post(
            "/v1/operations/jobs/drain",
            headers={"authorization": f"Bearer {executive['access_token']}"},
        )
        self.assertEqual(executive_drain.status_code, 401, executive_drain.text)
        authorized = self.client.post(
            "/v1/operations/jobs/drain",
            headers={"x-loopos-worker-token": "api-worker-token-that-is-at-least-thirty-two-bytes"},
        )
        self.assertEqual(authorized.status_code, 200, authorized.text)
        cron_authorized = self.client.post(
            "/v1/operations/jobs/drain",
            headers={"authorization": "Bearer api-worker-token-that-is-at-least-thirty-two-bytes"},
        )
        self.assertEqual(cron_authorized.status_code, 200, cron_authorized.text)

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
        completed = self.wait_for_run_state(run_id, "EFFECTIVENESS_PROVEN")
        self.assertEqual(completed["runner_status"], "completed")
        stream = self.client.get(f"/v1/runs/{run_id}/events", headers=self.headers)
        self.assertTrue(stream.headers["content-type"].startswith("text/event-stream"), stream.headers)
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
        failed = self.wait_for_run_state(run_id, "ROLLED_BACK")

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

    def test_api_records_release_evidence_and_initiative_atomically(self) -> None:
        evidence = connector_event_request().model_copy(update={"external_id": "api-atomic-release-event"})
        payload = {
            "initiative": release_request().model_dump(mode="json"),
            "connector_events": [evidence.model_dump(mode="json")],
        }
        created = self.client.post(
            "/v1/release-initiatives/record",
            headers={**self.headers, "idempotency-key": "api-atomic-release-key"},
            json=payload,
        )
        self.assertEqual(created.status_code, 201, created.text)
        response = created.json()
        self.assertEqual(len(response["connector_events"]), 1)
        self.assertEqual(response["initiative"]["source_event_ids"], [response["connector_events"][0]["connector_event_id"]])

        replay = self.client.post(
            "/v1/release-initiatives/record",
            headers={**self.headers, "idempotency-key": "api-atomic-release-key"},
            json=payload,
        )
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["initiative"]["initiative_id"], response["initiative"]["initiative_id"])
        self.assertEqual(len(self.client.get("/v1/connector-events?workspace_id=workspace-release", headers=self.headers).json()), 1)
        self.assertEqual(len(self.client.get("/v1/release-initiatives?workspace_id=workspace-release", headers=self.headers).json()), 1)

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

    def test_authenticated_connector_events_cannot_claim_provider_verification(self) -> None:
        payload = connector_event_request().model_dump(mode="json")
        payload.update({"verification_status": "verified_webhook", "delivery_id": "forged-direct-delivery"})

        response = self.client.post("/v1/connector-events", headers=self.headers, json=payload)

        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["detail"], "Provider-verified connector events must arrive through signed webhook ingestion.")

        payload.pop("delivery_id")
        missing_delivery = self.client.post("/v1/connector-events", headers=self.headers, json=payload)
        self.assertEqual(missing_delivery.status_code, 422, missing_delivery.text)

    def test_webhooks_require_provider_delivery_identifiers(self) -> None:
        github_body = json_bytes({
            "repository": {"full_name": "acme/payments"},
            "pull_request": {"html_url": "https://github.example/acme/payments/pull/43", "title": "Require delivery identity"},
        })
        jira_body = json_bytes({"webhookEvent": "jira:issue_updated", "issue": {"key": "PAY-43", "fields": {"summary": "Require delivery identity"}}})

        with self.subTest(system="github"):
            response = self.client.post(
                "/v1/webhooks/tenant-api/github?workspace_id=workspace-release",
                content=github_body,
                headers={"x-hub-signature-256": webhook_signature("github-webhook-secret", github_body), "x-github-event": "pull_request", "content-type": "application/json"},
            )
            self.assertEqual(response.status_code, 400, response.text)

        with self.subTest(system="jira"):
            response = self.client.post(
                "/v1/webhooks/tenant-api/jira?workspace_id=workspace-release",
                content=jira_body,
                headers={"x-loopos-signature-256": webhook_signature("jira-webhook-secret", jira_body), "content-type": "application/json"},
            )
            self.assertEqual(response.status_code, 400, response.text)

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
