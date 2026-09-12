from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol

from .corpus import Corpus, RISK_ORDER
from .models import Actor, ApprovalRequest, ConnectorEventRecord, ConnectorEventRequest, CreateReleaseInitiativeRequest, CreateRunRequest, ExecutionPlan, RecordReleaseInitiativeRequest, ReleaseInitiativeRecord, ReleaseProofPack, RunRecord, WorkspaceRecord, validate_release_assurance


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class StoreError(RuntimeError):
    pass


class NotFound(StoreError):
    pass


class Conflict(StoreError):
    pass


class Forbidden(StoreError):
    pass


class StoreCursor(Protocol):
    lastrowid: int | None

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> "StoreCursor":
        ...

    def fetchone(self) -> Any:
        ...

    def fetchall(self) -> list[Any]:
        ...

    def close(self) -> None:
        ...


class AuthorityStore:
    def __init__(self, database_path: Path, corpus: Corpus):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.corpus = corpus
        self.connection = sqlite3.connect(database_path, check_same_thread=False, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._initialize()

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def verify_schema(self) -> None:
        """Confirm that storage initialization completed successfully."""
        return None

    @contextmanager
    def transaction(self) -> Iterator[StoreCursor]:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                yield cursor
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
            finally:
                cursor.close()

    def _initialize(self) -> None:
        with self.lock:
            self.connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                PRAGMA busy_timeout=5000;

                CREATE TABLE IF NOT EXISTS runs (
                  run_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  loop_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  trigger_text TEXT NOT NULL,
                  state TEXT NOT NULL,
                  runner_status TEXT NOT NULL,
                  risk_tier TEXT NOT NULL,
                  requires_approval INTEGER NOT NULL,
                  payload_hash TEXT NOT NULL,
                  plan_json TEXT NOT NULL,
                  attempt INTEGER NOT NULL DEFAULT 0,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  last_error TEXT,
                  output_json TEXT,
                  request_key TEXT NOT NULL,
                  recovery_of TEXT,
                  effectiveness_due_at TEXT,
                  UNIQUE(tenant_id, request_key)
                );

                CREATE INDEX IF NOT EXISTS idx_runs_tenant_updated ON runs(tenant_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS execution_jobs (
                  job_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  command TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  available_at TEXT NOT NULL,
                  lease_owner TEXT,
                  lease_expires_at TEXT,
                  last_error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_execution_jobs_claim
                  ON execution_jobs(status, available_at, lease_expires_at, created_at);
                CREATE INDEX IF NOT EXISTS idx_execution_jobs_run
                  ON execution_jobs(tenant_id, run_id, created_at);

                CREATE TABLE IF NOT EXISTS kill_switches (
                  tenant_id TEXT PRIMARY KEY,
                  active INTEGER NOT NULL DEFAULT 0,
                  activation_id TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  actor_id TEXT NOT NULL,
                  actor_role TEXT NOT NULL,
                  activated_at TEXT NOT NULL,
                  deactivated_at TEXT,
                  deactivated_by TEXT,
                  deactivation_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS operational_signals (
                  signal_name TEXT NOT NULL,
                  source TEXT NOT NULL,
                  detail_json TEXT NOT NULL,
                  observed_at TEXT NOT NULL,
                  PRIMARY KEY(signal_name, source)
                );

                CREATE TABLE IF NOT EXISTS request_rate_limits (
                  bucket_key TEXT PRIMARY KEY,
                  window_started_at INTEGER NOT NULL,
                  request_count INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_request_rate_limits_window
                  ON request_rate_limits(window_started_at);

                CREATE TABLE IF NOT EXISTS approvals (
                  approval_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  payload_hash TEXT NOT NULL,
                  render_hash TEXT NOT NULL,
                  render_json TEXT NOT NULL,
                  decision TEXT NOT NULL,
                  decision_reason TEXT NOT NULL,
                  actor_id TEXT NOT NULL,
                  actor_role TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  consumed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_approvals_run_payload ON approvals(tenant_id, run_id, payload_hash, decision, created_at DESC);

                CREATE TABLE IF NOT EXISTS evidence (
                  evidence_record_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  evidence_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  source_ref TEXT NOT NULL,
                  content_json TEXT NOT NULL,
                  content_hash TEXT NOT NULL,
                  collected_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  UNIQUE(tenant_id, run_id, evidence_id)
                );

                CREATE TABLE IF NOT EXISTS tool_invocations (
                  invocation_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  tool_name TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  request_json TEXT NOT NULL,
                  request_hash TEXT NOT NULL,
                  status TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  result_json TEXT,
                  error_code TEXT,
                  error_message TEXT,
                  started_at TEXT NOT NULL,
                  completed_at TEXT,
                  UNIQUE(tenant_id, tool_name, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS probe_results (
                  probe_result_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  phase TEXT NOT NULL,
                  probe_id TEXT NOT NULL,
                  passed INTEGER NOT NULL,
                  detail_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS action_artifacts (
                  artifact_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  idempotency_key TEXT NOT NULL,
                  artifact_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  compensated_at TEXT,
                  UNIQUE(tenant_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS workspaces (
                  tenant_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  revision INTEGER NOT NULL,
                  document_json TEXT NOT NULL,
                  document_hash TEXT NOT NULL,
                  created_by TEXT NOT NULL,
                  updated_by TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY(tenant_id, workspace_id)
                );

                CREATE INDEX IF NOT EXISTS idx_workspaces_tenant_updated ON workspaces(tenant_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS audit_events (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT NOT NULL UNIQUE,
                  tenant_id TEXT NOT NULL,
                  run_id TEXT,
                  event_type TEXT NOT NULL,
                  state TEXT,
                  actor_id TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  previous_hash TEXT NOT NULL,
                  event_hash TEXT NOT NULL UNIQUE
                );

                CREATE INDEX IF NOT EXISTS idx_audit_tenant_sequence ON audit_events(tenant_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_audit_run_sequence ON audit_events(run_id, sequence);

                CREATE TABLE IF NOT EXISTS audit_anchor_outbox (
                  event_id TEXT PRIMARY KEY REFERENCES audit_events(event_id),
                  tenant_id TEXT NOT NULL,
                  envelope_json TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  next_attempt_at TEXT NOT NULL,
                  last_error TEXT,
                  delivered_at TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_anchor_pending
                  ON audit_anchor_outbox(delivered_at, next_attempt_at, created_at);

                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;

                CREATE TABLE IF NOT EXISTS release_initiatives (
                  initiative_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  description TEXT NOT NULL,
                  workflow_type TEXT NOT NULL,
                  business_outcome TEXT NOT NULL,
                  maturity TEXT NOT NULL,
                  risk_tier TEXT NOT NULL,
                  status TEXT NOT NULL,
                  release_name TEXT NOT NULL,
                  loop_bundle_json TEXT NOT NULL,
                  source_event_ids_json TEXT NOT NULL DEFAULT '[]',
                  release_assurance_json TEXT NOT NULL,
                  freshness_summary_json TEXT NOT NULL DEFAULT '{}',
                  readiness_verdict_json TEXT NOT NULL DEFAULT '{}',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  request_key TEXT NOT NULL,
                  UNIQUE(tenant_id, request_key)
                );

                CREATE INDEX IF NOT EXISTS idx_release_initiatives_tenant_workspace ON release_initiatives(tenant_id, workspace_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS connector_events (
                  connector_event_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  system TEXT NOT NULL,
                  event_kind TEXT NOT NULL,
                  external_id TEXT NOT NULL,
                  label TEXT NOT NULL,
                  url TEXT,
                  observed_at TEXT NOT NULL,
                  payload_hash TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  verification_status TEXT NOT NULL DEFAULT 'session_authenticated',
                  delivery_id TEXT,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE(tenant_id, system, external_id, payload_hash)
                );

                CREATE INDEX IF NOT EXISTS idx_connector_events_tenant_workspace ON connector_events(tenant_id, workspace_id, observed_at DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_connector_events_delivery ON connector_events(tenant_id, system, delivery_id) WHERE delivery_id IS NOT NULL;
                """
            )
            columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(runs)").fetchall()}
            if "effectiveness_due_at" not in columns:
                self.connection.execute("ALTER TABLE runs ADD COLUMN effectiveness_due_at TEXT")
            approvals_sql = str(self.connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'approvals'").fetchone()["sql"])
            if "UNIQUE(tenant_id, run_id, payload_hash, decision)" in approvals_sql:
                self.connection.execute("DROP INDEX IF EXISTS idx_approvals_run_payload")
                self.connection.execute("PRAGMA foreign_keys=OFF")
                try:
                    self.connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        ALTER TABLE approvals RENAME TO approvals_legacy;
                        CREATE TABLE approvals (
                          approval_id TEXT PRIMARY KEY,
                          tenant_id TEXT NOT NULL,
                          run_id TEXT NOT NULL REFERENCES runs(run_id),
                          payload_hash TEXT NOT NULL,
                          render_hash TEXT NOT NULL,
                          render_json TEXT NOT NULL,
                          decision TEXT NOT NULL,
                          decision_reason TEXT NOT NULL,
                          actor_id TEXT NOT NULL,
                          actor_role TEXT NOT NULL,
                          created_at TEXT NOT NULL,
                          expires_at TEXT NOT NULL,
                          consumed_at TEXT
                        );
                        INSERT INTO approvals SELECT * FROM approvals_legacy;
                        DROP TABLE approvals_legacy;
                        CREATE INDEX idx_approvals_run_payload ON approvals(tenant_id, run_id, payload_hash, decision, created_at DESC);
                        COMMIT;
                        """
                    )
                finally:
                    self.connection.execute("PRAGMA foreign_keys=ON")
            initiative_columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(release_initiatives)").fetchall()}
            if "source_event_ids_json" not in initiative_columns:
                self.connection.execute("ALTER TABLE release_initiatives ADD COLUMN source_event_ids_json TEXT NOT NULL DEFAULT '[]'")
            if "freshness_summary_json" not in initiative_columns:
                self.connection.execute("ALTER TABLE release_initiatives ADD COLUMN freshness_summary_json TEXT NOT NULL DEFAULT '{}'")
            if "readiness_verdict_json" not in initiative_columns:
                self.connection.execute("ALTER TABLE release_initiatives ADD COLUMN readiness_verdict_json TEXT NOT NULL DEFAULT '{}'")
            connector_columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(connector_events)").fetchall()}
            if "verification_status" not in connector_columns:
                self.connection.execute("ALTER TABLE connector_events ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'session_authenticated'")
            if "delivery_id" not in connector_columns:
                self.connection.execute("ALTER TABLE connector_events ADD COLUMN delivery_id TEXT")

    def list_workspaces(self, tenant_id: str, limit: int = 100) -> list[WorkspaceRecord]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM workspaces WHERE tenant_id = ? ORDER BY updated_at DESC LIMIT ?",
                (tenant_id, min(limit, 200)),
            ).fetchall()
        return [self._row_to_workspace(row) for row in rows]

    def get_workspace(self, tenant_id: str, workspace_id: str) -> WorkspaceRecord:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM workspaces WHERE tenant_id = ? AND workspace_id = ?",
                (tenant_id, workspace_id),
            ).fetchone()
        if not row:
            raise NotFound("Workspace not found.")
        return self._row_to_workspace(row)

    def put_workspace(
        self,
        actor: Actor,
        workspace_id: str,
        document: dict[str, Any],
        *,
        expected_revision: int | None,
        create_only: bool,
    ) -> tuple[WorkspaceRecord, bool]:
        document_json = canonical_json(document)
        document_hash = hashlib.sha256(document_json.encode("utf-8")).hexdigest()
        timestamp = utc_now()
        created = False
        with self.transaction() as cursor:
            existing = cursor.execute(
                "SELECT * FROM workspaces WHERE tenant_id = ? AND workspace_id = ?",
                (actor.tenant_id, workspace_id),
            ).fetchone()
            if existing:
                if create_only:
                    raise Conflict("Workspace already exists.")
                if expected_revision != int(existing["revision"]):
                    raise Conflict("Workspace revision does not match the current authoritative record.")
                revision = int(existing["revision"]) + 1
                cursor.execute(
                    """
                    UPDATE workspaces
                    SET revision = ?, document_json = ?, document_hash = ?, updated_by = ?, updated_at = ?
                    WHERE tenant_id = ? AND workspace_id = ?
                    """,
                    (revision, document_json, document_hash, actor.user_id, timestamp, actor.tenant_id, workspace_id),
                )
                event_type = "WORKSPACE_UPDATED"
            else:
                if not create_only:
                    raise NotFound("Workspace not found.")
                revision = 1
                cursor.execute(
                    """
                    INSERT INTO workspaces(tenant_id, workspace_id, revision, document_json, document_hash,
                      created_by, updated_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (actor.tenant_id, workspace_id, revision, document_json, document_hash, actor.user_id, actor.user_id, timestamp, timestamp),
                )
                event_type = "WORKSPACE_CREATED"
                created = True
            self._append_event_cursor(
                cursor,
                actor.tenant_id,
                None,
                event_type,
                None,
                actor.user_id,
                {"workspace_id": workspace_id, "revision": revision, "document_hash": document_hash},
            )
            row = cursor.execute(
                "SELECT * FROM workspaces WHERE tenant_id = ? AND workspace_id = ?",
                (actor.tenant_id, workspace_id),
            ).fetchone()
        return self._row_to_workspace(row), created

    def delete_workspace(self, actor: Actor, workspace_id: str, expected_revision: int) -> None:
        with self.transaction() as cursor:
            existing = cursor.execute(
                "SELECT * FROM workspaces WHERE tenant_id = ? AND workspace_id = ?",
                (actor.tenant_id, workspace_id),
            ).fetchone()
            if not existing:
                raise NotFound("Workspace not found.")
            if expected_revision != int(existing["revision"]):
                raise Conflict("Workspace revision does not match the current authoritative record.")
            self._append_event_cursor(
                cursor,
                actor.tenant_id,
                None,
                "WORKSPACE_DELETED",
                None,
                actor.user_id,
                {
                    "workspace_id": workspace_id,
                    "revision": int(existing["revision"]),
                    "document_hash": str(existing["document_hash"]),
                },
            )
            cursor.execute(
                "DELETE FROM workspaces WHERE tenant_id = ? AND workspace_id = ?",
                (actor.tenant_id, workspace_id),
            )

    def record_connector_event(self, actor: Actor, request: ConnectorEventRequest) -> ConnectorEventRecord:
        payload_hash = sha256_json(request.payload)
        timestamp = utc_now()
        event_id = f"connector-event-{uuid.uuid4()}"
        with self.transaction() as cursor:
            if request.delivery_id and request.verification_status == "verified_webhook":
                replay = cursor.execute(
                    "SELECT * FROM connector_events WHERE tenant_id = ? AND system = ? AND delivery_id = ?",
                    (actor.tenant_id, request.system, request.delivery_id),
                ).fetchone()
                if replay:
                    if replay["payload_hash"] != payload_hash:
                        self._append_event_cursor(cursor, actor.tenant_id, None, "CONNECTOR_EVENT_REPLAY_CONFLICT", None, actor.user_id, {"system": request.system, "delivery_id": request.delivery_id, "submitted_payload_hash": payload_hash, "stored_payload_hash": replay["payload_hash"]})
                        raise Conflict("Webhook delivery ID was replayed with a different payload.")
                    return self._row_to_connector_event(replay)
            existing = cursor.execute(
                "SELECT * FROM connector_events WHERE tenant_id = ? AND system = ? AND external_id = ? AND payload_hash = ?",
                (actor.tenant_id, request.system, request.external_id, payload_hash),
            ).fetchone()
            if existing:
                return self._row_to_connector_event(existing)
            cursor.execute(
                """
                INSERT INTO connector_events(connector_event_id, tenant_id, workspace_id, system, event_kind, external_id,
                  label, url, observed_at, payload_hash, payload_json, verification_status, delivery_id, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    actor.tenant_id,
                    request.workspace_id,
                    request.system,
                    request.event_kind,
                    request.external_id,
                    request.label,
                    request.url,
                    request.observed_at,
                    payload_hash,
                    canonical_json(request.payload),
                    request.verification_status,
                    request.delivery_id,
                    actor.user_id,
                    timestamp,
                ),
            )
            self._append_event_cursor(cursor, actor.tenant_id, None, "CONNECTOR_EVENT_RECORDED", None, actor.user_id, {"connector_event_id": event_id, "workspace_id": request.workspace_id, "system": request.system, "event_kind": request.event_kind, "external_id": request.external_id, "payload_hash": payload_hash, "verification_status": request.verification_status, "delivery_id": request.delivery_id})
            row = cursor.execute("SELECT * FROM connector_events WHERE connector_event_id = ?", (event_id,)).fetchone()
        return self._row_to_connector_event(row)

    def _record_connector_event_cursor(self, cursor: StoreCursor, actor: Actor, request: ConnectorEventRequest) -> ConnectorEventRecord:
        """Record evidence on an already-open transaction for atomic release writes."""
        payload_hash = sha256_json(request.payload)
        timestamp = utc_now()
        event_id = f"connector-event-{uuid.uuid4()}"
        if request.delivery_id and request.verification_status == "verified_webhook":
            replay = cursor.execute(
                "SELECT * FROM connector_events WHERE tenant_id = ? AND system = ? AND delivery_id = ?",
                (actor.tenant_id, request.system, request.delivery_id),
            ).fetchone()
            if replay:
                if replay["payload_hash"] != payload_hash:
                    self._append_event_cursor(cursor, actor.tenant_id, None, "CONNECTOR_EVENT_REPLAY_CONFLICT", None, actor.user_id, {"system": request.system, "delivery_id": request.delivery_id, "submitted_payload_hash": payload_hash, "stored_payload_hash": replay["payload_hash"]})
                    raise Conflict("Webhook delivery ID was replayed with a different payload.")
                return self._row_to_connector_event(replay)
        existing = cursor.execute(
            "SELECT * FROM connector_events WHERE tenant_id = ? AND system = ? AND external_id = ? AND payload_hash = ?",
            (actor.tenant_id, request.system, request.external_id, payload_hash),
        ).fetchone()
        if existing:
            return self._row_to_connector_event(existing)
        cursor.execute(
            """
            INSERT INTO connector_events(connector_event_id, tenant_id, workspace_id, system, event_kind, external_id,
              label, url, observed_at, payload_hash, payload_json, verification_status, delivery_id, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                actor.tenant_id,
                request.workspace_id,
                request.system,
                request.event_kind,
                request.external_id,
                request.label,
                request.url,
                request.observed_at,
                payload_hash,
                canonical_json(request.payload),
                request.verification_status,
                request.delivery_id,
                actor.user_id,
                timestamp,
            ),
        )
        self._append_event_cursor(cursor, actor.tenant_id, None, "CONNECTOR_EVENT_RECORDED", None, actor.user_id, {"connector_event_id": event_id, "workspace_id": request.workspace_id, "system": request.system, "event_kind": request.event_kind, "external_id": request.external_id, "payload_hash": payload_hash, "verification_status": request.verification_status, "delivery_id": request.delivery_id})
        row = cursor.execute("SELECT * FROM connector_events WHERE connector_event_id = ?", (event_id,)).fetchone()
        return self._row_to_connector_event(row)

    def list_connector_events(self, tenant_id: str, workspace_id: str | None = None, limit: int = 100) -> list[ConnectorEventRecord]:
        query = "SELECT * FROM connector_events WHERE tenant_id = ?"
        parameters: list[Any] = [tenant_id]
        if workspace_id:
            query += " AND workspace_id = ?"
            parameters.append(workspace_id)
        query += " ORDER BY observed_at DESC, created_at DESC LIMIT ?"
        parameters.append(min(limit, 200))
        with self.lock:
            rows = self.connection.execute(query, parameters).fetchall()
        return [self._row_to_connector_event(row) for row in rows]

    def create_release_initiative(self, actor: Actor, request: CreateReleaseInitiativeRequest, request_key: str) -> ReleaseInitiativeRecord:
        validate_release_assurance(request.release_assurance)
        if len(set(request.source_event_ids)) != len(request.source_event_ids):
            raise ValueError("Source connector event IDs must be unique.")
        for loop_id in request.loop_bundle_ids:
            if loop_id not in self.corpus.loop_descriptors:
                raise NotFound(f"Unknown loop ID: {loop_id}")
        known_event_rows = self._connector_event_rows(
            actor.tenant_id,
            request.source_event_ids,
            workspace_id=request.workspace_id,
        )
        known_events = set(known_event_rows)
        missing_events = sorted(set(request.source_event_ids) - known_events)
        if missing_events:
            raise NotFound(f"Unknown connector event IDs: {', '.join(missing_events)}")
        timestamp = utc_now()
        freshness_summary = self._release_freshness_summary(request.source_event_ids, known_event_rows, timestamp)
        readiness_verdict = self._release_readiness_verdict(request.release_assurance, freshness_summary, timestamp)
        payload = {
            "tenant_id": actor.tenant_id,
            "workspace_id": request.workspace_id,
            "title": request.title,
            "description": request.description,
            "workflow_type": request.workflow_type,
            "business_outcome": request.business_outcome,
            "maturity": request.maturity,
            "risk_tier": request.risk_tier,
            "status": request.status,
            "release_name": request.release_name,
            "loop_bundle_ids": request.loop_bundle_ids,
            "source_event_ids": request.source_event_ids,
            "release_assurance": request.release_assurance,
        }
        payload_hash = sha256_json(payload)
        initiative_id = f"initiative-{uuid.uuid4()}"
        request_key_conflict = False
        with self.transaction() as cursor:
            existing = cursor.execute(
                "SELECT * FROM release_initiatives WHERE tenant_id = ? AND request_key = ?",
                (actor.tenant_id, request_key),
            ).fetchone()
            if existing:
                existing_payload = self._release_initiative_payload(existing)
                if sha256_json(existing_payload) != payload_hash:
                    request_key_conflict = True
                    self._append_event_cursor(cursor, actor.tenant_id, None, "RELEASE_INITIATIVE_IDEMPOTENCY_CONFLICT", None, actor.user_id, {"request_key": request_key, "submitted_payload_hash": payload_hash})
                row = existing
            else:
                cursor.execute(
                    """
                    INSERT INTO release_initiatives(initiative_id, tenant_id, workspace_id, title, description, workflow_type,
                      business_outcome, maturity, risk_tier, status, release_name, loop_bundle_json, source_event_ids_json, release_assurance_json, freshness_summary_json, readiness_verdict_json,
                      created_by, created_at, updated_at, request_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        initiative_id,
                        actor.tenant_id,
                        request.workspace_id,
                        request.title,
                        request.description,
                        request.workflow_type,
                        request.business_outcome,
                        request.maturity,
                        request.risk_tier,
                        request.status,
                        request.release_name,
                        canonical_json(request.loop_bundle_ids),
                        canonical_json(request.source_event_ids),
                        canonical_json(request.release_assurance),
                        canonical_json(freshness_summary),
                        canonical_json(readiness_verdict),
                        actor.user_id,
                        timestamp,
                        timestamp,
                        request_key,
                    ),
                )
                self._append_event_cursor(cursor, actor.tenant_id, None, "RELEASE_INITIATIVE_RECORDED", None, actor.user_id, {"initiative_id": initiative_id, "payload_hash": payload_hash, "release_name": request.release_name, "status": request.status, "source_event_ids": request.source_event_ids, "freshness_summary": freshness_summary, "readiness_verdict": readiness_verdict})
                row = cursor.execute("SELECT * FROM release_initiatives WHERE initiative_id = ?", (initiative_id,)).fetchone()
        if request_key_conflict:
            raise Conflict("Idempotency key was reused with a different release initiative payload.")
        return self._refresh_release_readiness(self._row_to_release_initiative(row))

    def record_release_initiative(self, actor: Actor, request: RecordReleaseInitiativeRequest, request_key: str) -> tuple[ReleaseInitiativeRecord, list[ConnectorEventRecord]]:
        """Persist release evidence and its initiative as one durable transaction."""
        with self.transaction() as cursor:
            events = [self._record_connector_event_cursor(cursor, actor, event) for event in request.connector_events]
            initiative_request = request.initiative.model_copy(
                update={"source_event_ids": [event.connector_event_id for event in events]}
            )
            initiative = self._create_release_initiative_cursor(cursor, actor, initiative_request, request_key)
        return self._refresh_release_readiness(initiative), events

    def _create_release_initiative_cursor(self, cursor: StoreCursor, actor: Actor, request: CreateReleaseInitiativeRequest, request_key: str) -> ReleaseInitiativeRecord:
        validate_release_assurance(request.release_assurance)
        if len(set(request.source_event_ids)) != len(request.source_event_ids):
            raise ValueError("Source connector event IDs must be unique.")
        for loop_id in request.loop_bundle_ids:
            if loop_id not in self.corpus.loop_descriptors:
                raise NotFound(f"Unknown loop ID: {loop_id}")
        placeholders = ",".join("?" for _ in request.source_event_ids)
        known_event_rows = {
            str(row["connector_event_id"]): row
            for row in cursor.execute(
                f"SELECT * FROM connector_events WHERE tenant_id = ? AND connector_event_id IN ({placeholders}) AND workspace_id = ?",
                (actor.tenant_id, *request.source_event_ids, request.workspace_id),
            ).fetchall()
        } if request.source_event_ids else {}
        missing_events = sorted(set(request.source_event_ids) - set(known_event_rows))
        if missing_events:
            raise NotFound(f"Unknown connector event IDs: {', '.join(missing_events)}")
        timestamp = utc_now()
        freshness_summary = self._release_freshness_summary(request.source_event_ids, known_event_rows, timestamp)
        readiness_verdict = self._release_readiness_verdict(request.release_assurance, freshness_summary, timestamp)
        payload = {
            "tenant_id": actor.tenant_id,
            "workspace_id": request.workspace_id,
            "title": request.title,
            "description": request.description,
            "workflow_type": request.workflow_type,
            "business_outcome": request.business_outcome,
            "maturity": request.maturity,
            "risk_tier": request.risk_tier,
            "status": request.status,
            "release_name": request.release_name,
            "loop_bundle_ids": request.loop_bundle_ids,
            "source_event_ids": request.source_event_ids,
            "release_assurance": request.release_assurance,
        }
        payload_hash = sha256_json(payload)
        initiative_id = f"initiative-{uuid.uuid4()}"
        existing = cursor.execute(
            "SELECT * FROM release_initiatives WHERE tenant_id = ? AND request_key = ?",
            (actor.tenant_id, request_key),
        ).fetchone()
        if existing:
            if sha256_json(self._release_initiative_payload(existing)) != payload_hash:
                self._append_event_cursor(cursor, actor.tenant_id, None, "RELEASE_INITIATIVE_IDEMPOTENCY_CONFLICT", None, actor.user_id, {"request_key": request_key, "submitted_payload_hash": payload_hash})
                raise Conflict("Idempotency key was reused with a different release initiative payload.")
            return self._row_to_release_initiative(existing)
        cursor.execute(
            """
            INSERT INTO release_initiatives(initiative_id, tenant_id, workspace_id, title, description, workflow_type,
              business_outcome, maturity, risk_tier, status, release_name, loop_bundle_json, source_event_ids_json, release_assurance_json, freshness_summary_json, readiness_verdict_json,
              created_by, created_at, updated_at, request_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                initiative_id, actor.tenant_id, request.workspace_id, request.title, request.description,
                request.workflow_type, request.business_outcome, request.maturity, request.risk_tier,
                request.status, request.release_name, canonical_json(request.loop_bundle_ids),
                canonical_json(request.source_event_ids), canonical_json(request.release_assurance),
                canonical_json(freshness_summary), canonical_json(readiness_verdict), actor.user_id,
                timestamp, timestamp, request_key,
            ),
        )
        self._append_event_cursor(cursor, actor.tenant_id, None, "RELEASE_INITIATIVE_RECORDED", None, actor.user_id, {"initiative_id": initiative_id, "payload_hash": payload_hash, "release_name": request.release_name, "status": request.status, "source_event_ids": request.source_event_ids, "freshness_summary": freshness_summary, "readiness_verdict": readiness_verdict})
        row = cursor.execute("SELECT * FROM release_initiatives WHERE initiative_id = ?", (initiative_id,)).fetchone()
        return self._row_to_release_initiative(row)

    def list_release_initiatives(self, tenant_id: str, workspace_id: str | None = None, limit: int = 100) -> list[ReleaseInitiativeRecord]:
        query = "SELECT * FROM release_initiatives WHERE tenant_id = ?"
        parameters: list[Any] = [tenant_id]
        if workspace_id:
            query += " AND workspace_id = ?"
            parameters.append(workspace_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(min(limit, 200))
        with self.lock:
            rows = self.connection.execute(query, parameters).fetchall()
        return [self._refresh_release_readiness(self._row_to_release_initiative(row)) for row in rows]

    def get_release_initiative(self, tenant_id: str, initiative_id: str) -> ReleaseInitiativeRecord:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM release_initiatives WHERE tenant_id = ? AND initiative_id = ?",
                (tenant_id, initiative_id),
            ).fetchone()
        if not row:
            raise NotFound("Release initiative not found.")
        return self._refresh_release_readiness(self._row_to_release_initiative(row))

    def build_release_proof_pack(self, tenant_id: str, initiative_id: str, actor_id: str = "authority-reader") -> ReleaseProofPack:
        initiative = self.get_release_initiative(tenant_id, initiative_id)
        source_events = self._connector_event_rows(
            tenant_id,
            initiative.source_event_ids,
            workspace_id=initiative.workspace_id,
        )
        generated_at = utc_now()
        markdown = self._release_proof_pack_markdown(initiative, source_events)
        markdown_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        self.append_event(
            tenant_id,
            None,
            "PROOF_PACK_GENERATED",
            None,
            actor_id,
            {
                "initiative_id": initiative.initiative_id,
                "workspace_id": initiative.workspace_id,
                "release_name": initiative.release_name,
                "markdown_hash": markdown_hash,
                "source_event_ids": initiative.source_event_ids,
                "readiness_verdict": initiative.readiness_verdict.get("verdict", "NOT_EVALUATED"),
                "freshness_status": initiative.freshness_summary.get("status", "not evaluated"),
            },
        )
        return ReleaseProofPack(
            initiative_id=initiative.initiative_id,
            tenant_id=initiative.tenant_id,
            workspace_id=initiative.workspace_id,
            release_name=initiative.release_name,
            readiness_verdict=initiative.readiness_verdict,
            freshness_summary=initiative.freshness_summary,
            source_event_ids=initiative.source_event_ids,
            markdown=markdown,
            markdown_hash=markdown_hash,
            generated_at=generated_at,
        )

    def _connector_event_rows(
        self,
        tenant_id: str,
        event_ids: list[str],
        *,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        if not event_ids:
            return {}
        placeholders = ",".join("?" for _ in event_ids)
        query = f"SELECT * FROM connector_events WHERE tenant_id = ? AND connector_event_id IN ({placeholders})"
        parameters: list[Any] = [tenant_id, *event_ids]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            parameters.append(workspace_id)
        with self.lock:
            rows = self.connection.execute(query, parameters).fetchall()
        return {str(row["connector_event_id"]): row for row in rows}

    def _refresh_release_readiness(self, initiative: ReleaseInitiativeRecord) -> ReleaseInitiativeRecord:
        evaluated_at = utc_now()
        source_events = self._connector_event_rows(
            initiative.tenant_id,
            initiative.source_event_ids,
            workspace_id=initiative.workspace_id,
        )
        freshness_summary = self._release_freshness_summary(
            initiative.source_event_ids,
            source_events,
            evaluated_at,
        )
        readiness_verdict = self._release_readiness_verdict(
            initiative.release_assurance,
            freshness_summary,
            evaluated_at,
        )
        return initiative.model_copy(
            update={
                "freshness_summary": freshness_summary,
                "readiness_verdict": readiness_verdict,
            }
        )

    @staticmethod
    def _release_freshness_summary(source_event_ids: list[str], event_rows: dict[str, Any], evaluated_at: str) -> dict[str, Any]:
        max_age_seconds = 86_400
        evaluated = parse_iso_datetime(evaluated_at) or datetime.now(timezone.utc)
        stale_event_ids: list[str] = []
        missing_event_ids: list[str] = []
        invalid_observed_at_event_ids: list[str] = []
        future_observed_at_event_ids: list[str] = []
        observed_times: list[datetime] = []
        verification_counts = {"session_authenticated": 0, "verified_webhook": 0}
        for event_id in source_event_ids:
            row = event_rows.get(event_id)
            if row is None:
                missing_event_ids.append(event_id)
                continue
            verification_status = str(row["verification_status"])
            if verification_status in verification_counts:
                verification_counts[verification_status] += 1
            observed = parse_iso_datetime(str(row["observed_at"]))
            if observed is None:
                invalid_observed_at_event_ids.append(event_id)
                continue
            observed_times.append(observed)
            if (evaluated - observed).total_seconds() > max_age_seconds:
                stale_event_ids.append(event_id)
            elif (observed - evaluated).total_seconds() > 300:
                future_observed_at_event_ids.append(event_id)
        status = "missing" if not source_event_ids or missing_event_ids else "fresh"
        if stale_event_ids or invalid_observed_at_event_ids or future_observed_at_event_ids:
            status = "stale"
        return {
            "status": status,
            "policy": "release connector evidence must be observed within 24 hours of the authority release record",
            "max_age_seconds": max_age_seconds,
            "evaluated_at": evaluated_at,
            "source_event_count": len(source_event_ids),
            "missing_event_ids": missing_event_ids,
            "verified_webhook_count": verification_counts["verified_webhook"],
            "session_authenticated_count": verification_counts["session_authenticated"],
            "stale_event_ids": stale_event_ids,
            "invalid_observed_at_event_ids": invalid_observed_at_event_ids,
            "future_observed_at_event_ids": future_observed_at_event_ids,
            "oldest_observed_at": min(observed_times).isoformat() if observed_times else None,
            "newest_observed_at": max(observed_times).isoformat() if observed_times else None,
        }

    @staticmethod
    def _release_readiness_verdict(release_assurance: dict[str, Any], freshness_summary: dict[str, Any], evaluated_at: str) -> dict[str, Any]:
        gates = release_assurance.get("gates") if isinstance(release_assurance.get("gates"), list) else []
        gate_statuses = [str(gate.get("status", "missing")) if isinstance(gate, dict) else "missing" for gate in gates]
        gate_identity_failures: list[str] = []
        gate_ids: set[str] = set()
        for gate in gates:
            if not isinstance(gate, dict):
                gate_identity_failures.append("non-object gate")
                continue
            gate_id = gate.get("gate_id")
            if not isinstance(gate_id, str) or not gate_id.strip():
                gate_identity_failures.append("missing gate_id")
                continue
            normalized_gate_id = gate_id.strip()
            if normalized_gate_id in gate_ids:
                gate_identity_failures.append("duplicate gate_id")
            gate_ids.add(normalized_gate_id)
        failing_reasons: list[str] = []
        review_reasons: list[str] = []
        recognized_statuses = {"passed", "gap", "review_required", "exception_active", "blocked", "missing"}
        unrecognized_statuses = sorted({status for status in gate_statuses if status not in recognized_statuses})
        if gate_identity_failures:
            failing_reasons.append(
                f"{len(gate_identity_failures)} release assurance gate record(s) must have unique, non-empty gate IDs"
            )
        if freshness_summary.get("status") != "fresh":
            failing_reasons.append(f"connector evidence freshness is {freshness_summary.get('status', 'missing')}")
        if not gate_statuses:
            failing_reasons.append("no release assurance gates were recorded")
        if unrecognized_statuses:
            failing_reasons.append(
                f"{len(unrecognized_statuses)} release gates have unrecognized statuses: {', '.join(unrecognized_statuses)}"
            )
        blocked_or_gap = [status for status in gate_statuses if status in {"blocked", "gap", "missing"}]
        if blocked_or_gap:
            failing_reasons.append(f"{len(blocked_or_gap)} release gates are blocked, missing, or have evidence gaps")
        review_required = [status for status in gate_statuses if status in {"review_required", "exception_active"}]
        if review_required:
            review_reasons.append(f"{len(review_required)} release gates require review or active exception approval")
        source_event_count = int(freshness_summary.get("source_event_count", 0) or 0)
        verified_webhook_count = int(freshness_summary.get("verified_webhook_count", 0) or 0)
        if source_event_count and verified_webhook_count < source_event_count:
            review_reasons.append(
                f"{source_event_count - verified_webhook_count} linked connector evidence event(s) are not provider-verified; external verification is required before GO"
            )
        verdict = "GO"
        if failing_reasons:
            verdict = "NO_GO"
        elif review_reasons:
            verdict = "REVIEW_REQUIRED"
        return {
            "verdict": verdict,
            "evaluated_at": evaluated_at,
            "policy": "GO only when connector evidence is fresh, every linked event is provider-verified, and every release assurance gate is passed; session-authenticated snapshots require review",
            "gate_status_counts": {status: gate_statuses.count(status) for status in sorted(set(gate_statuses))},
            "failing_reasons": failing_reasons,
            "review_reasons": review_reasons,
        }

    def _release_proof_pack_markdown(self, initiative: ReleaseInitiativeRecord, source_events: dict[str, Any]) -> str:
        gates = initiative.release_assurance.get("gates") if isinstance(initiative.release_assurance.get("gates"), list) else []
        proof_scope = initiative.release_assurance.get("proof_pack_scope") if isinstance(initiative.release_assurance.get("proof_pack_scope"), list) else []
        lines = [
            f"# LoopOS Authority Release Proof Pack: {initiative.release_name}",
            "",
            f"Record updated at: {initiative.updated_at}",
            f"Initiative: {initiative.initiative_id}",
            f"Workspace: {initiative.workspace_id}",
            f"Status: {initiative.status}",
            f"Risk tier: {initiative.risk_tier}",
            f"Readiness verdict: {initiative.readiness_verdict.get('verdict', 'NOT_EVALUATED')}",
            f"Freshness status: {initiative.freshness_summary.get('status', 'not evaluated')}",
            "",
            "## Decision Boundary",
            "",
            "This proof pack records release readiness evidence only. It does not execute a deployment or bypass payload-bound approval, rollback, validation, or effectiveness controls.",
            "",
            "## Business Outcome",
            "",
            initiative.business_outcome,
            "",
            "## Loop Bundle",
            "",
        ]
        for loop_id in initiative.loop_bundle_ids:
            descriptor = self.corpus.loop_descriptors.get(loop_id, {})
            loop_name = descriptor.get("name") or loop_id
            outcome = descriptor.get("outcome") or "Outcome metadata unavailable."
            lines.append(f"- {loop_id}: {loop_name} - {outcome}")
        lines.extend(["", "## Readiness Verdict", ""])
        lines.append(str(initiative.readiness_verdict.get("policy", "No readiness policy recorded.")))
        for reason in initiative.readiness_verdict.get("failing_reasons", []):
            lines.append(f"- Fail-closed reason: {reason}")
        for reason in initiative.readiness_verdict.get("review_reasons", []):
            lines.append(f"- Review reason: {reason}")
        if not initiative.readiness_verdict.get("failing_reasons") and not initiative.readiness_verdict.get("review_reasons"):
            lines.append("- No fail-closed or review reasons recorded.")
        lines.extend(["", "## Freshness Summary", ""])
        lines.append(str(initiative.freshness_summary.get("policy", "No freshness policy recorded.")))
        lines.append(f"- Source events: {initiative.freshness_summary.get('source_event_count', 0)}")
        lines.append(f"- Webhook verified: {initiative.freshness_summary.get('verified_webhook_count', 0)}")
        lines.append(f"- Session snapshots: {initiative.freshness_summary.get('session_authenticated_count', 0)}")
        stale_ids = initiative.freshness_summary.get("stale_event_ids", [])
        if stale_ids:
            lines.append(f"- Stale event IDs: {', '.join(map(str, stale_ids))}")
        lines.extend(["", "## Release Gates", ""])
        if gates:
            for gate in gates:
                if isinstance(gate, dict):
                    lines.append(f"- {gate.get('gate_id', 'gate')}: {str(gate.get('status', 'missing')).upper()}")
        else:
            lines.append("- No release assurance gates recorded.")
        lines.extend(["", "## Connector Evidence", ""])
        if initiative.source_event_ids:
            for event_id in initiative.source_event_ids:
                row = source_events.get(event_id)
                if not row:
                    lines.append(f"- {event_id}: missing from tenant connector evidence store")
                    continue
                lines.append(f"- {event_id}: {row['system']} {row['event_kind']} / {row['label']} / {row['verification_status']} / {row['payload_hash']}")
        else:
            lines.append("- No connector evidence event IDs linked.")
        lines.extend(["", "## Proof Pack Scope", ""])
        if proof_scope:
            lines.extend(f"- {item}" for item in proof_scope)
        else:
            lines.append("- No proof-pack scope recorded.")
        return "\n".join(lines)

    def create_run(
        self,
        actor: Actor,
        request: CreateRunRequest,
        request_key: str,
        recovery_of: str | None = None,
    ) -> RunRecord:
        if request.loop_id not in self.corpus.loop_descriptors:
            raise NotFound(f"Unknown loop ID: {request.loop_id}")
        if request.plan.action.tool not in self.corpus.tool_contracts:
            raise NotFound(f"No approved tool contract exists for {request.plan.action.tool}.")
        if request.plan.rollback and request.plan.rollback.tool not in self.corpus.tool_contracts:
            raise NotFound(f"No approved rollback contract exists for {request.plan.rollback.tool}.")
        risk = self.corpus.effective_risk(request.loop_id, request.requested_risk_tier)
        self._validate_enterprise_plan_context(request.plan, risk)
        plan_document = request.plan.model_dump(mode="json")
        payload = {
            "tenant_id": actor.tenant_id,
            "workspace_id": request.workspace_id,
            "loop_id": request.loop_id,
            "title": request.title,
            "trigger": request.trigger,
            "risk_tier": risk,
            "plan": plan_document,
            "recovery_of": recovery_of,
            "standard_hash": self.corpus.standard_hash,
            "descriptor_hash": self.corpus.descriptor_hash(request.loop_id),
        }
        payload_hash = sha256_json(payload)
        requires_approval = RISK_ORDER[risk] >= RISK_ORDER["R3"] or request.plan.action.external_effect
        run_id = f"run-{uuid.uuid4()}"
        timestamp = utc_now()
        request_key_conflict = False
        with self.transaction() as cursor:
            if self._kill_switch_active_cursor(cursor, actor.tenant_id):
                raise Conflict("The tenant kill switch is active; new execution runs are blocked until an Executive deactivates it.")
            existing = cursor.execute(
                "SELECT * FROM runs WHERE tenant_id = ? AND request_key = ?",
                (actor.tenant_id, request_key),
            ).fetchone()
            if existing:
                row = existing
                if existing["payload_hash"] != payload_hash:
                    request_key_conflict = True
                    self._append_event_cursor(cursor, actor.tenant_id, existing["run_id"], "IDEMPOTENCY_KEY_CONFLICT", existing["state"], actor.user_id, {"request_key": request_key, "submitted_payload_hash": payload_hash})
            else:
                cursor.execute(
                    """
                    INSERT INTO runs(run_id, tenant_id, workspace_id, loop_id, title, trigger_text, state, runner_status,
                      risk_tier, requires_approval, payload_hash, plan_json, created_by, created_at, updated_at, request_key, recovery_of)
                    VALUES (?, ?, ?, ?, ?, ?, 'TRIGGERED', 'idle', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        actor.tenant_id,
                        request.workspace_id,
                        request.loop_id,
                        request.title,
                        request.trigger,
                        risk,
                        int(requires_approval),
                        payload_hash,
                        canonical_json(plan_document),
                        actor.user_id,
                        timestamp,
                        timestamp,
                        request_key,
                        recovery_of,
                    ),
                )
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "RUN_CREATED", "TRIGGERED", actor.user_id, payload)
                row = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (actor.tenant_id, run_id)).fetchone()
        if request_key_conflict:
            raise Conflict("Idempotency key was reused with a different run payload.")
        return self._row_to_run(row)

    def kill_switch_status(self, tenant_id: str) -> dict[str, Any]:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM kill_switches WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        return self._kill_switch_status_from_row(tenant_id, row)

    def is_kill_switch_active(self, tenant_id: str) -> bool:
        with self.lock:
            return self._kill_switch_active_cursor(self.connection, tenant_id)

    @staticmethod
    def _kill_switch_active_cursor(cursor: StoreCursor, tenant_id: str) -> bool:
        row = cursor.execute(
            "SELECT active FROM kill_switches WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        return bool(row and int(row["active"]) == 1)

    @staticmethod
    def _kill_switch_status_from_row(tenant_id: str, row: Any) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "scope": "tenant",
            "active": bool(row and int(row["active"]) == 1),
            "activation_id": row["activation_id"] if row else None,
            "reason": row["reason"] if row else None,
            "actor_id": row["actor_id"] if row else None,
            "activated_at": row["activated_at"] if row else None,
            "deactivated_at": row["deactivated_at"] if row else None,
            "deactivated_by": row["deactivated_by"] if row else None,
            "deactivation_reason": row["deactivation_reason"] if row else None,
            "semantics": "pre_dispatch_block_and_in_flight_interrupt",
        }

    def activate_kill_switch(self, actor: Actor, reason: str) -> dict[str, Any]:
        if actor.role != "Executive":
            raise Forbidden("Kill switch activation requires Executive authority.")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 3:
            raise Conflict("Kill switch activation requires a reason of at least 3 characters.")
        timestamp = utc_now()
        with self.transaction() as cursor:
            existing = cursor.execute(
                "SELECT * FROM kill_switches WHERE tenant_id = ?",
                (actor.tenant_id,),
            ).fetchone()
            if existing and int(existing["active"]) == 1:
                self._append_event_cursor(
                    cursor,
                    actor.tenant_id,
                    None,
                    "KILL_SWITCH_ALREADY_ACTIVE",
                    None,
                    actor.user_id,
                    {"activation_id": existing["activation_id"], "reason": normalized_reason, "scope": "tenant"},
                )
                return self._kill_switch_status_from_row(actor.tenant_id, existing)

            activation_id = f"kill-switch-{uuid.uuid4()}"
            cursor.execute(
                """
                INSERT INTO kill_switches(
                  tenant_id, active, activation_id, reason, actor_id, actor_role, activated_at,
                  deactivated_at, deactivated_by, deactivation_reason
                ) VALUES (?, 1, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                ON CONFLICT(tenant_id) DO UPDATE SET
                  active = 1,
                  activation_id = excluded.activation_id,
                  reason = excluded.reason,
                  actor_id = excluded.actor_id,
                  actor_role = excluded.actor_role,
                  activated_at = excluded.activated_at,
                  deactivated_at = NULL,
                  deactivated_by = NULL,
                  deactivation_reason = NULL
                """,
                (actor.tenant_id, activation_id, normalized_reason, actor.user_id, actor.role, timestamp),
            )
            self._append_event_cursor(
                cursor,
                actor.tenant_id,
                None,
                "KILL_SWITCH_ACTIVATED",
                None,
                actor.user_id,
                {
                    "activation_id": activation_id,
                    "scope": "tenant",
                    "reason": normalized_reason,
                    "pre_dispatch_blocked": True,
                    "in_flight_interrupt_requested": True,
                    "remote_cancellation_requested": False,
                    "credential_revocation": "not_available_to_authority",
                },
            )

            processed_runs: set[str] = set()
            queued_jobs = cursor.execute(
                "SELECT * FROM execution_jobs WHERE tenant_id = ? AND status = 'queued' ORDER BY created_at",
                (actor.tenant_id,),
            ).fetchall()
            for job in queued_jobs:
                cursor.execute(
                    """
                    UPDATE execution_jobs
                    SET status = 'failed', lease_owner = NULL, lease_expires_at = NULL,
                      last_error = ?, updated_at = ?
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    ("Tenant kill switch activated before dispatch.", timestamp, job["job_id"]),
                )
                self._interrupt_run_cursor(
                    cursor,
                    actor.tenant_id,
                    job["run_id"],
                    actor.user_id,
                    "queued_before_dispatch",
                )
                processed_runs.add(str(job["run_id"]))
                current = cursor.execute(
                    "SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?",
                    (actor.tenant_id, job["run_id"]),
                ).fetchone()
                self._append_event_cursor(
                    cursor,
                    actor.tenant_id,
                    job["run_id"],
                    "EXECUTION_JOB_FAILED",
                    current["state"] if current else None,
                    actor.user_id,
                    {"job_id": job["job_id"], "error": "Tenant kill switch activated before dispatch."},
                )

            active_runs = cursor.execute(
                """
                SELECT run_id FROM runs
                WHERE tenant_id = ? AND runner_status IN ('running', 'awaiting_effectiveness')
                ORDER BY updated_at
                """,
                (actor.tenant_id,),
            ).fetchall()
            for run in active_runs:
                run_id = str(run["run_id"])
                if run_id in processed_runs:
                    continue
                self._interrupt_run_cursor(cursor, actor.tenant_id, run_id, actor.user_id, "in_flight_or_observation")

            row = cursor.execute(
                "SELECT * FROM kill_switches WHERE tenant_id = ?",
                (actor.tenant_id,),
            ).fetchone()
        return self._kill_switch_status_from_row(actor.tenant_id, row)

    def deactivate_kill_switch(self, actor: Actor, reason: str) -> dict[str, Any]:
        if actor.role != "Executive":
            raise Forbidden("Kill switch deactivation requires Executive authority.")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 3:
            raise Conflict("Kill switch deactivation requires a reason of at least 3 characters.")
        timestamp = utc_now()
        with self.transaction() as cursor:
            row = cursor.execute(
                "SELECT * FROM kill_switches WHERE tenant_id = ?",
                (actor.tenant_id,),
            ).fetchone()
            if not row or int(row["active"]) == 0:
                self._append_event_cursor(
                    cursor,
                    actor.tenant_id,
                    None,
                    "KILL_SWITCH_DEACTIVATION_NOOP",
                    None,
                    actor.user_id,
                    {"reason": normalized_reason, "scope": "tenant"},
                )
                return self._kill_switch_status_from_row(actor.tenant_id, row)
            cursor.execute(
                """
                UPDATE kill_switches
                SET active = 0, deactivated_at = ?, deactivated_by = ?, deactivation_reason = ?
                WHERE tenant_id = ?
                """,
                (timestamp, actor.user_id, normalized_reason, actor.tenant_id),
            )
            self._append_event_cursor(
                cursor,
                actor.tenant_id,
                None,
                "KILL_SWITCH_DEACTIVATED",
                None,
                actor.user_id,
                {
                    "activation_id": row["activation_id"],
                    "scope": "tenant",
                    "reason": normalized_reason,
                    "restart_requires_new_approval": True,
                },
            )
            updated = cursor.execute(
                "SELECT * FROM kill_switches WHERE tenant_id = ?",
                (actor.tenant_id,),
            ).fetchone()
        return self._kill_switch_status_from_row(actor.tenant_id, updated)

    def interrupt_run_for_kill_switch(
        self,
        tenant_id: str,
        run_id: str,
        phase: str,
        action_output: dict[str, Any] | None = None,
        action_external_effect: bool = False,
    ) -> RunRecord:
        with self.transaction() as cursor:
            run = cursor.execute(self._run_for_update_sql(), (tenant_id, run_id)).fetchone()
            if not run:
                raise NotFound("Run not found.")
            self._interrupt_run_cursor(
                cursor,
                tenant_id,
                run_id,
                "authority-engine",
                phase,
                action_output,
                action_external_effect,
            )
            updated = cursor.execute(
                "SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
        return self._row_to_run(updated)

    def _interrupt_run_cursor(
        self,
        cursor: StoreCursor,
        tenant_id: str,
        run_id: str,
        actor_id: str,
        phase: str,
        action_output: dict[str, Any] | None = None,
        action_external_effect: bool = False,
    ) -> None:
        row = cursor.execute(
            "SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?",
            (tenant_id, run_id),
        ).fetchone()
        if not row:
            return
        current_state = str(row["state"])
        next_state = current_state
        if not self.corpus.is_terminal(current_state) and self.corpus.allows_transition(current_state, "BLOCKED"):
            timestamp = utc_now()
            cursor.execute(
                "UPDATE runs SET state = ?, updated_at = ? WHERE tenant_id = ? AND run_id = ?",
                ("BLOCKED", timestamp, tenant_id, run_id),
            )
            self._append_event_cursor(
                cursor,
                tenant_id,
                run_id,
                "STATE_TRANSITION",
                "BLOCKED",
                actor_id,
                {"from_state": current_state, "to_state": "BLOCKED", "reason": "tenant_kill_switch"},
            )
            next_state = "BLOCKED"
        output = json.loads(row["output_json"]) if row["output_json"] else {}
        control = {
            "status": "interrupted",
            "phase": phase,
            "remote_cancellation_requested": False,
            "credential_revocation": "not_available_to_authority",
            "remote_action_may_have_completed": bool(action_output is not None and action_external_effect and phase == "after_action_dispatch"),
        }
        if action_output is not None:
            output["action"] = action_output
        output["kill_switch"] = control
        timestamp = utc_now()
        cursor.execute(
            """
            UPDATE runs
            SET runner_status = 'failed', last_error = ?, output_json = ?, updated_at = ?
            WHERE tenant_id = ? AND run_id = ?
            """,
            (
                f"Tenant kill switch interrupted execution during {phase}; remote cancellation and credential revocation are not provided by this authority.",
                canonical_json(output),
                timestamp,
                tenant_id,
                run_id,
            ),
        )
        self._append_event_cursor(
            cursor,
            tenant_id,
            run_id,
            "KILL_SWITCH_ENFORCED",
            next_state,
            actor_id,
            control,
        )

    def _validate_enterprise_plan_context(self, plan: ExecutionPlan, risk: str) -> None:
        requires_context = RISK_ORDER[risk] >= RISK_ORDER["R3"] or plan.action.external_effect
        if not requires_context:
            return
        if plan.enterprise_context is None:
            raise Conflict("High-risk or external-effect runs require enterprise_context with policy decision, sandbox profile, idempotency scope, and evidence refs.")
        if plan.enterprise_context.idempotency_scope != "tenant_workflow_tool_payload":
            raise Conflict("Enterprise idempotency scope must be tenant_workflow_tool_payload.")
        if plan.action.external_effect and plan.rollback is None:
            raise Conflict("External-effect runs require a rollback or compensating action contract.")

    def get_run(self, tenant_id: str, run_id: str) -> RunRecord:
        with self.lock:
            row = self.connection.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
        if not row:
            raise NotFound("Run not found.")
        return self._row_to_run(row)

    def list_runs(self, tenant_id: str, workspace_id: str | None = None, limit: int = 100) -> list[RunRecord]:
        query = "SELECT * FROM runs WHERE tenant_id = ?"
        parameters: list[Any] = [tenant_id]
        if workspace_id:
            query += " AND workspace_id = ?"
            parameters.append(workspace_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(min(limit, 200))
        with self.lock:
            rows = self.connection.execute(query, parameters).fetchall()
        return [self._row_to_run(row) for row in rows]

    def claim_run(self, tenant_id: str, run_id: str, reclaim_running: bool = False) -> RunRecord:
        with self.transaction() as cursor:
            row = cursor.execute(self._run_for_update_sql(), (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            if row["runner_status"] == "running" and not reclaim_running:
                raise Conflict("Run is already running.")
            if self.corpus.is_terminal(row["state"]):
                raise Conflict(f"Terminal run {run_id} cannot be started again.")
            if self._kill_switch_active_cursor(cursor, tenant_id):
                self._interrupt_run_cursor(cursor, tenant_id, run_id, "authority-engine", "claim_blocked")
                raise Conflict("The tenant kill switch is active; execution cannot be claimed.")
            if row["state"] == "EFFECTIVENESS_PENDING" and row["effectiveness_due_at"] and datetime.fromisoformat(row["effectiveness_due_at"]) > datetime.now(timezone.utc):
                raise Conflict("The effectiveness observation window is not due yet.")
            timestamp = utc_now()
            cursor.execute("UPDATE runs SET runner_status = 'running', updated_at = ? WHERE tenant_id = ? AND run_id = ?", (timestamp, tenant_id, run_id))
            self._append_event_cursor(
                cursor,
                tenant_id,
                run_id,
                "RUN_CLAIMED",
                row["state"],
                "authority-engine",
                {"reclaimed": row["runner_status"] == "running"},
            )
            updated = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
        return self._row_to_run(updated)

    def queue_run(
        self,
        tenant_id: str,
        run_id: str,
        actor_id: str,
        command: str = "execute",
        payload: dict[str, Any] | None = None,
    ) -> RunRecord:
        with self.transaction() as cursor:
            row = cursor.execute(self._run_for_update_sql(), (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            if row["runner_status"] in {"queued", "running"}:
                raise Conflict("Run is already queued or running.")
            if self.corpus.is_terminal(row["state"]):
                raise Conflict("Terminal runs cannot accept new commands.")
            if self._kill_switch_active_cursor(cursor, tenant_id):
                self._interrupt_run_cursor(cursor, tenant_id, run_id, actor_id, "queue_blocked")
                raise Conflict("The tenant kill switch is active; execution cannot be queued.")
            if row["state"] == "EFFECTIVENESS_PENDING" and row["effectiveness_due_at"] and datetime.fromisoformat(row["effectiveness_due_at"]) > datetime.now(timezone.utc):
                raise Conflict("The effectiveness observation window is not due yet.")
            timestamp = utc_now()
            cursor.execute("UPDATE runs SET runner_status = 'queued', updated_at = ? WHERE tenant_id = ? AND run_id = ?", (timestamp, tenant_id, run_id))
            self._enqueue_execution_job_cursor(cursor, tenant_id, run_id, command, payload or {}, timestamp)
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_QUEUED", row["state"], actor_id, {"command": command})
            updated = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
        return self._row_to_run(updated)

    def release_run(self, tenant_id: str, run_id: str, status: str = "idle", error: str | None = None) -> None:
        with self.transaction() as cursor:
            row = cursor.execute(self._run_for_update_sql(), (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            cursor.execute(
                "UPDATE runs SET runner_status = ?, last_error = ?, updated_at = ? WHERE tenant_id = ? AND run_id = ?",
                (status, error, utc_now(), tenant_id, run_id),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_RELEASED", row["state"], "authority-engine", {"runner_status": status, "error": error})

    def requeue_incomplete_runs(self) -> list[tuple[str, str]]:
        recovered: list[tuple[str, str]] = []
        with self.transaction() as cursor:
            rows = cursor.execute(self._incomplete_runs_claim_sql()).fetchall()
            for row in rows:
                timestamp = utc_now()
                if self._kill_switch_active_cursor(cursor, row["tenant_id"]):
                    self._interrupt_run_cursor(
                        cursor,
                        row["tenant_id"],
                        row["run_id"],
                        "authority-engine",
                        "restart_reconciliation_blocked",
                    )
                    blocked_jobs = cursor.execute(
                        """
                        SELECT * FROM execution_jobs
                        WHERE tenant_id = ? AND run_id = ? AND status IN ('queued', 'running')
                        ORDER BY created_at
                        """,
                        (row["tenant_id"], row["run_id"]),
                    ).fetchall()
                    for job in blocked_jobs:
                        cursor.execute(
                            """
                            UPDATE execution_jobs
                            SET status = 'failed', lease_owner = NULL, lease_expires_at = NULL,
                              last_error = ?, updated_at = ?
                            WHERE job_id = ? AND status IN ('queued', 'running')
                            """,
                            ("Tenant kill switch remained active during restart reconciliation.", timestamp, job["job_id"]),
                        )
                        self._append_event_cursor(
                            cursor,
                            row["tenant_id"],
                            row["run_id"],
                            "EXECUTION_JOB_FAILED",
                            "BLOCKED",
                            "authority-engine",
                            {
                                "job_id": job["job_id"],
                                "error": "Tenant kill switch remained active during restart reconciliation.",
                            },
                        )
                    continue
                active_job = cursor.execute(
                    """
                    SELECT * FROM execution_jobs
                    WHERE tenant_id = ? AND run_id = ? AND status IN ('queued', 'running')
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (row["tenant_id"], row["run_id"]),
                ).fetchone()
                if active_job and active_job["status"] == "running" and active_job["lease_expires_at"] and active_job["lease_expires_at"] > timestamp:
                    continue
                if active_job:
                    cursor.execute(
                        """
                        UPDATE execution_jobs
                        SET status = 'queued', lease_owner = NULL, lease_expires_at = NULL, available_at = ?, updated_at = ?
                        WHERE job_id = ?
                        """,
                        (timestamp, timestamp, active_job["job_id"]),
                    )
                else:
                    self._enqueue_execution_job_cursor(cursor, row["tenant_id"], row["run_id"], "execute", {}, timestamp)
                cursor.execute("UPDATE runs SET runner_status = 'queued', updated_at = ? WHERE tenant_id = ? AND run_id = ?", (timestamp, row["tenant_id"], row["run_id"]))
                self._append_event_cursor(cursor, row["tenant_id"], row["run_id"], "RUN_REQUEUED_AFTER_RESTART", row["state"], "authority-engine", {"previous_runner_status": row["runner_status"]})
                recovered.append((str(row["tenant_id"]), str(row["run_id"])))
        return recovered

    def schedule_effectiveness(self, tenant_id: str, run_id: str, delay_seconds: int) -> str:
        due_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        with self.transaction() as cursor:
            row = cursor.execute("SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            if row["state"] != "EFFECTIVENESS_PENDING":
                raise Conflict("Effectiveness can be scheduled only from EFFECTIVENESS_PENDING.")
            cursor.execute("UPDATE runs SET effectiveness_due_at = ?, runner_status = 'awaiting_effectiveness', updated_at = ? WHERE tenant_id = ? AND run_id = ?", (due_at, utc_now(), tenant_id, run_id))
            self._append_event_cursor(cursor, tenant_id, run_id, "EFFECTIVENESS_SCHEDULED", row["state"], "authority-engine", {"due_at": due_at, "delay_seconds": delay_seconds})
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_RELEASED", row["state"], "authority-engine", {"runner_status": "awaiting_effectiveness", "error": None})
        return due_at

    def queue_due_effectiveness(self, limit: int = 20) -> list[tuple[str, str]]:
        due: list[tuple[str, str]] = []
        with self.transaction() as cursor:
            rows = cursor.execute(self._due_effectiveness_claim_sql(), (utc_now(), limit)).fetchall()
            for row in rows:
                if self._kill_switch_active_cursor(cursor, row["tenant_id"]):
                    self._interrupt_run_cursor(cursor, row["tenant_id"], row["run_id"], "authority-scheduler", "effectiveness_queue_blocked")
                    continue
                timestamp = utc_now()
                cursor.execute("UPDATE runs SET runner_status = 'queued', updated_at = ? WHERE tenant_id = ? AND run_id = ?", (timestamp, row["tenant_id"], row["run_id"]))
                self._enqueue_execution_job_cursor(cursor, row["tenant_id"], row["run_id"], "execute", {"phase": "effectiveness"}, timestamp)
                self._append_event_cursor(cursor, row["tenant_id"], row["run_id"], "EFFECTIVENESS_QUEUED", row["state"], "authority-scheduler", {"due_at": row["effectiveness_due_at"]})
                due.append((str(row["tenant_id"]), str(row["run_id"])))
        return due

    def claim_execution_jobs(
        self,
        worker_id: str,
        lease_seconds: int,
        limit: int = 10,
        max_attempts: int = 5,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        lease_expires_at = (now + timedelta(seconds=max(lease_seconds, 1))).isoformat()
        attempt_limit = max(max_attempts, 1)
        claimed: list[dict[str, Any]] = []
        with self.transaction() as cursor:
            self._fail_exhausted_execution_jobs_cursor(cursor, attempt_limit, now_iso)
            rows = cursor.execute(
                self._execution_job_claim_sql(attempt_limit),
                (now_iso, now_iso, attempt_limit, min(max(limit, 1), 100)),
            ).fetchall()
            for row in rows:
                if self._kill_switch_active_cursor(cursor, row["tenant_id"]):
                    continue
                cursor.execute(
                    """
                    UPDATE execution_jobs
                    SET status = 'running', attempts = attempts + 1, lease_owner = ?, lease_expires_at = ?,
                      last_error = NULL, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (worker_id, lease_expires_at, now_iso, row["job_id"]),
                )
                updated = cursor.execute("SELECT * FROM execution_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
                claimed.append(self._row_to_execution_job(updated))
        return claimed

    def _fail_exhausted_execution_jobs_cursor(self, cursor: StoreCursor, max_attempts: int, now_iso: str) -> None:
        error = "Execution job exceeded its maximum retry attempts after lease expiry."
        rows = cursor.execute(
            """
            SELECT * FROM execution_jobs
            WHERE attempts >= ?
              AND (
                status = 'queued'
                OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
              )
            """,
            (max_attempts, now_iso),
        ).fetchall()
        for row in rows:
            cursor.execute(
                """
                UPDATE execution_jobs
                SET status = 'failed', lease_owner = NULL, lease_expires_at = NULL,
                  last_error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (error, now_iso, row["job_id"]),
            )
            run = cursor.execute(
                "SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?",
                (row["tenant_id"], row["run_id"]),
            ).fetchone()
            if run and not self.corpus.is_terminal(run["state"]):
                cursor.execute(
                    """
                    UPDATE runs
                    SET runner_status = 'failed', last_error = ?, updated_at = ?
                    WHERE tenant_id = ? AND run_id = ?
                    """,
                    (error, now_iso, row["tenant_id"], row["run_id"]),
                )
            self._append_event_cursor(
                cursor,
                row["tenant_id"],
                row["run_id"],
                "EXECUTION_JOB_FAILED",
                run["state"] if run else None,
                "execution-worker",
                {"job_id": row["job_id"], "attempts": int(row["attempts"]), "error": error},
            )

    def renew_execution_job(self, job_id: str, worker_id: str, lease_seconds: int) -> str:
        lease_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=max(lease_seconds, 1))).isoformat()
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM execution_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row or row["status"] != "running" or row["lease_owner"] != worker_id:
                raise Conflict("Execution job lease is not owned by this worker.")
            cursor.execute(
                "UPDATE execution_jobs SET lease_expires_at = ?, updated_at = ? WHERE job_id = ?",
                (lease_expires_at, utc_now(), job_id),
            )
        return lease_expires_at

    def complete_execution_job(self, job_id: str, worker_id: str) -> None:
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM execution_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row or row["status"] != "running" or row["lease_owner"] != worker_id:
                raise Conflict("Execution job lease is not owned by this worker.")
            cursor.execute(
                """
                UPDATE execution_jobs
                SET status = 'completed', lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                (utc_now(), job_id),
            )

    def fail_execution_job(self, job_id: str, worker_id: str, error: str, max_attempts: int = 5) -> None:
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM execution_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row or row["status"] != "running" or row["lease_owner"] != worker_id:
                raise Conflict("Execution job lease is not owned by this worker.")
            attempts = int(row["attempts"])
            terminal = attempts >= max(max_attempts, 1)
            timestamp = utc_now()
            if terminal:
                cursor.execute(
                    """
                    UPDATE execution_jobs
                    SET status = 'failed', lease_owner = NULL, lease_expires_at = NULL, last_error = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (error[:500], timestamp, job_id),
                )
                run_state = cursor.execute(
                    "SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?",
                    (row["tenant_id"], row["run_id"]),
                ).fetchone()
                if run_state and not self.corpus.is_terminal(run_state["state"]):
                    cursor.execute(
                        "UPDATE runs SET runner_status = 'failed', last_error = ?, updated_at = ? WHERE tenant_id = ? AND run_id = ?",
                        (error[:500], timestamp, row["tenant_id"], row["run_id"]),
                    )
            else:
                available_at = (datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** min(attempts, 8)))).isoformat()
                cursor.execute(
                    """
                    UPDATE execution_jobs
                    SET status = 'queued', lease_owner = NULL, lease_expires_at = NULL, last_error = ?,
                      available_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (error[:500], available_at, timestamp, job_id),
                )
                cursor.execute(
                    "UPDATE runs SET runner_status = 'queued', last_error = ?, updated_at = ? WHERE tenant_id = ? AND run_id = ?",
                    (error[:500], timestamp, row["tenant_id"], row["run_id"]),
                )
            run = cursor.execute(
                "SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?",
                (row["tenant_id"], row["run_id"]),
            ).fetchone()
            self._append_event_cursor(
                cursor,
                row["tenant_id"],
                row["run_id"],
                "EXECUTION_JOB_FAILED" if terminal else "EXECUTION_JOB_RETRY_SCHEDULED",
                run["state"] if run else None,
                worker_id,
                {"job_id": job_id, "attempts": attempts, "error": error[:500]},
            )

    def execution_job_backlog(self, tenant_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS count FROM execution_jobs WHERE status IN ('queued', 'running')"
        parameters: tuple[Any, ...] = ()
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            parameters = (tenant_id,)
        with self.lock:
            row = self.connection.execute(query, parameters).fetchone()
        return int(row["count"]) if row else 0

    def record_operational_signal(self, signal_name: str, source: str, detail: dict[str, Any]) -> dict[str, Any]:
        observed_at = utc_now()
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO operational_signals(signal_name, source, detail_json, observed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(signal_name, source) DO UPDATE SET
                  detail_json = excluded.detail_json,
                  observed_at = excluded.observed_at
                """,
                (signal_name, source, canonical_json(detail), observed_at),
            )
        return {
            "signal_name": signal_name,
            "source": source,
            "detail": detail,
            "observed_at": observed_at,
        }

    def operational_signal_status(
        self,
        signal_name: str,
        max_age_seconds: float,
        required_source: str | None = None,
    ) -> dict[str, Any]:
        query = "SELECT * FROM operational_signals WHERE signal_name = ?"
        parameters: tuple[Any, ...] = (signal_name,)
        if required_source is not None:
            query += " AND source = ?"
            parameters = (signal_name, required_source)
        query += " ORDER BY observed_at DESC LIMIT 1"
        with self.lock:
            row = self.connection.execute(query, parameters).fetchone()
        if not row:
            return {
                "verified": False,
                "source": None,
                "observed_at": None,
                "age_seconds": None,
                "detail": {},
            }
        now = datetime.now(timezone.utc)
        observed_at = parse_iso_datetime(str(row["observed_at"]))
        age_seconds = (now - observed_at).total_seconds() if observed_at else None
        fresh = bool(
            observed_at
            and -300 <= float(age_seconds) <= max_age_seconds
        )
        source = str(row["source"])
        return {
            "verified": fresh and (required_source is None or source == required_source),
            "source": source,
            "observed_at": row["observed_at"],
            "age_seconds": max(0.0, float(age_seconds)) if age_seconds is not None else None,
            "detail": json.loads(row["detail_json"]),
        }

    def _enqueue_execution_job_cursor(
        self,
        cursor: StoreCursor,
        tenant_id: str,
        run_id: str,
        command: str,
        payload: dict[str, Any],
        available_at: str,
    ) -> str:
        job_id = f"job-{uuid.uuid4()}"
        cursor.execute(
            """
            INSERT INTO execution_jobs(
              job_id, tenant_id, run_id, command, payload_json, status, attempts, available_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?)
            """,
            (job_id, tenant_id, run_id, command, canonical_json(payload), available_at, available_at, available_at),
        )
        return job_id

    def _execution_job_claim_sql(self, max_attempts: int = 5) -> str:
        return """
            SELECT * FROM execution_jobs
            WHERE (
                (status = 'queued' AND available_at <= ?)
                OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
            )
              AND attempts < ?
              AND NOT EXISTS (
                SELECT 1 FROM kill_switches
                WHERE kill_switches.tenant_id = execution_jobs.tenant_id
                  AND kill_switches.active = 1
              )
            ORDER BY available_at, created_at
            LIMIT ?
        """

    def _run_for_update_sql(self) -> str:
        return "SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?"

    def _due_effectiveness_claim_sql(self) -> str:
        return """
            SELECT * FROM runs
            WHERE state = 'EFFECTIVENESS_PENDING' AND runner_status = 'awaiting_effectiveness'
              AND effectiveness_due_at IS NOT NULL AND effectiveness_due_at <= ?
            ORDER BY effectiveness_due_at
            LIMIT ?
        """

    def _incomplete_runs_claim_sql(self) -> str:
        return "SELECT * FROM runs WHERE runner_status IN ('queued', 'running') ORDER BY updated_at"

    def transition(self, tenant_id: str, run_id: str, to_state: str, actor_id: str, detail: dict[str, Any] | None = None) -> RunRecord:
        denied_transition: str | None = None
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            from_state = row["state"]
            if not self.corpus.allows_transition(from_state, to_state):
                self._append_event_cursor(cursor, tenant_id, run_id, "ILLEGAL_TRANSITION_DENIED", from_state, actor_id, {"attempted_state": to_state})
                denied_transition = f"Illegal transition: {from_state} -> {to_state}"
            else:
                timestamp = utc_now()
                cursor.execute("UPDATE runs SET state = ?, updated_at = ? WHERE tenant_id = ? AND run_id = ?", (to_state, timestamp, tenant_id, run_id))
                plan = json.loads(row["plan_json"])
                enterprise_context = plan.get("enterprise_context") or {}
                descriptor = self.corpus.loop_descriptors[row["loop_id"]]
                transition_detail = {"from_state": from_state, "to_state": to_state, **(detail or {})}
                transition_detail["observability"] = {
                    "loop_id": row["loop_id"],
                    "loop_version": descriptor.get("version"),
                    "execution_id": run_id,
                    "correlation_id": run_id,
                    "risk_tier": row["risk_tier"],
                    "state_from": from_state,
                    "state_to": to_state,
                    "authority_ref": actor_id,
                    "evidence_refs": enterprise_context.get("evidence_refs", []),
                    "standard_hash": self.corpus.standard_hash,
                    "policy_decision_ref": enterprise_context.get("policy_decision_ref"),
                    "sandbox_profile_ref": enterprise_context.get("sandbox_profile_ref"),
                    "proof_state": "unverified",
                }
                self._append_event_cursor(cursor, tenant_id, run_id, "STATE_TRANSITION", to_state, actor_id, transition_detail)
            updated = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
        if denied_transition:
            raise Conflict(denied_transition)
        return self._row_to_run(updated)

    def approve(self, actor: Actor, run_id: str, request: ApprovalRequest) -> str:
        if actor.role not in {"Approver", "Executive"}:
            try:
                run = self.get_run(actor.tenant_id, run_id)
                self.append_event(actor.tenant_id, run_id, "APPROVAL_DENIED", run.state, actor.user_id, {"reason": "role_not_authorized", "role": actor.role})
            except NotFound:
                pass
            raise Forbidden("Only Approver or Executive roles can authorize a governed action.")
        payload_mismatch = False
        separation_violation = False
        approval_id = ""
        with self.transaction() as cursor:
            run = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (actor.tenant_id, run_id)).fetchone()
            if not run:
                raise NotFound("Run not found.")
            if run["state"] != "PLANNED":
                raise Conflict("Approval is accepted only while a run is PLANNED.")
            if run["created_by"] == actor.user_id:
                self._append_event_cursor(
                    cursor,
                    actor.tenant_id,
                    run_id,
                    "APPROVAL_DENIED",
                    run["state"],
                    actor.user_id,
                    {"reason": "separation_of_duties", "requester_id": run["created_by"]},
                )
                separation_violation = True
            elif request.payload_hash != run["payload_hash"]:
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "APPROVE_AND_SWAP_DENIED", run["state"], actor.user_id, {"submitted_payload_hash": request.payload_hash})
                payload_mismatch = True
            else:
                render = {
                    "run_id": run_id,
                    "loop_id": run["loop_id"],
                    "title": run["title"],
                    "risk_tier": run["risk_tier"],
                    "payload_hash": run["payload_hash"],
                    "plan": json.loads(run["plan_json"]),
                }
                approval_id = f"approval-{uuid.uuid4()}"
                created_at = utc_now()
                expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
                cursor.execute(
                    """
                    INSERT INTO approvals(approval_id, tenant_id, run_id, payload_hash, render_hash, render_json, decision,
                      decision_reason, actor_id, actor_role, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?)
                    """,
                    (approval_id, actor.tenant_id, run_id, request.payload_hash, sha256_json(render), canonical_json(render), request.decision_reason, actor.user_id, actor.role, created_at, expires_at),
                )
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "APPROVAL_GRANTED", run["state"], actor.user_id, {"approval_id": approval_id, "payload_hash": request.payload_hash, "render_hash": sha256_json(render), "reason": request.decision_reason})
        if separation_violation:
            raise Forbidden("Approval requires separation of duties from the run requester.")
        if payload_mismatch:
            raise Conflict("Approval payload hash does not match the executable plan.")
        return approval_id

    def reject(self, actor: Actor, run_id: str, request: ApprovalRequest) -> str:
        if actor.role not in {"Approver", "Executive"}:
            try:
                run = self.get_run(actor.tenant_id, run_id)
                self.append_event(actor.tenant_id, run_id, "REJECTION_DENIED", run.state, actor.user_id, {"reason": "role_not_authorized", "role": actor.role})
            except NotFound:
                pass
            raise Forbidden("Only Approver or Executive roles can reject a governed action.")
        payload_mismatch = False
        separation_violation = False
        decision_id = ""
        with self.transaction() as cursor:
            run = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (actor.tenant_id, run_id)).fetchone()
            if not run:
                raise NotFound("Run not found.")
            if run["state"] != "PLANNED":
                raise Conflict("Rejection is accepted only while a run is PLANNED.")
            if run["created_by"] == actor.user_id:
                self._append_event_cursor(
                    cursor,
                    actor.tenant_id,
                    run_id,
                    "REJECTION_DENIED",
                    run["state"],
                    actor.user_id,
                    {"reason": "separation_of_duties", "requester_id": run["created_by"]},
                )
                separation_violation = True
            elif request.payload_hash != run["payload_hash"]:
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "REJECT_AND_SWAP_DENIED", run["state"], actor.user_id, {"submitted_payload_hash": request.payload_hash})
                payload_mismatch = True
            else:
                render = {
                    "run_id": run_id,
                    "loop_id": run["loop_id"],
                    "title": run["title"],
                    "risk_tier": run["risk_tier"],
                    "payload_hash": run["payload_hash"],
                    "plan": json.loads(run["plan_json"]),
                }
                decision_id = f"approval-{uuid.uuid4()}"
                created_at = utc_now()
                cursor.execute(
                    """
                    INSERT INTO approvals(approval_id, tenant_id, run_id, payload_hash, render_hash, render_json, decision,
                      decision_reason, actor_id, actor_role, created_at, expires_at, consumed_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'rejected', ?, ?, ?, ?, ?, ?)
                    """,
                    (decision_id, actor.tenant_id, run_id, request.payload_hash, sha256_json(render), canonical_json(render), request.decision_reason, actor.user_id, actor.role, created_at, created_at, created_at),
                )
                cursor.execute(
                    "UPDATE runs SET state = 'BLOCKED', runner_status = 'failed', last_error = ?, updated_at = ? WHERE tenant_id = ? AND run_id = ?",
                    (f"Rejected by {actor.user_id}: {request.decision_reason}", created_at, actor.tenant_id, run_id),
                )
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "APPROVAL_REJECTED", "PLANNED", actor.user_id, {"decision_id": decision_id, "payload_hash": request.payload_hash, "render_hash": sha256_json(render), "reason": request.decision_reason})
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "STATE_TRANSITION", "BLOCKED", actor.user_id, {"from_state": "PLANNED", "to_state": "BLOCKED", "reason": "approval_rejected"})
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "RUN_RELEASED", "BLOCKED", actor.user_id, {"runner_status": "failed", "error": request.decision_reason})
        if separation_violation:
            raise Forbidden("Rejection requires separation of duties from the run requester.")
        if payload_mismatch:
            raise Conflict("Rejection payload hash does not match the executable plan.")
        return decision_id

    def consume_approval(self, tenant_id: str, run_id: str, payload_hash: str) -> str:
        with self.transaction() as cursor:
            approval = cursor.execute(
                """
                SELECT * FROM approvals WHERE tenant_id = ? AND run_id = ? AND payload_hash = ? AND decision = 'approved'
                  AND consumed_at IS NULL AND expires_at > ? ORDER BY created_at DESC LIMIT 1
                """,
                (tenant_id, run_id, payload_hash, utc_now()),
            ).fetchone()
            if not approval:
                raise Forbidden("A current, unconsumed approval is required.")
            consumed_at = utc_now()
            cursor.execute("UPDATE approvals SET consumed_at = ? WHERE approval_id = ? AND consumed_at IS NULL", (consumed_at, approval["approval_id"]))
            self._append_event_cursor(cursor, tenant_id, run_id, "APPROVAL_CONSUMED", "PLANNED", "authority-engine", {"approval_id": approval["approval_id"], "payload_hash": payload_hash})
        return str(approval["approval_id"])

    def save_evidence(self, tenant_id: str, run_id: str, evidence_id: str, kind: str, source_ref: str, content: Any, freshness_seconds: int) -> dict[str, Any]:
        record_id = f"evidence-{uuid.uuid4()}"
        timestamp = datetime.now(timezone.utc)
        content_hash = sha256_json(content)
        with self.transaction() as cursor:
            cursor.execute(
                self._upsert_evidence_sql(),
                (
                    record_id,
                    tenant_id,
                    run_id,
                    evidence_id,
                    kind,
                    source_ref,
                    canonical_json(content),
                    content_hash,
                    timestamp.isoformat(),
                    (timestamp + timedelta(seconds=freshness_seconds)).isoformat(),
                ),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "EVIDENCE_COLLECTED", "OBSERVED", "authority-engine", {"evidence_id": evidence_id, "kind": kind, "source_ref": source_ref, "content_hash": content_hash})
        return {"evidence_id": evidence_id, "kind": kind, "source_ref": source_ref, "content": content, "content_hash": content_hash}

    def list_evidence(self, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute("SELECT * FROM evidence WHERE tenant_id = ? AND run_id = ? ORDER BY collected_at", (tenant_id, run_id)).fetchall()
        return [{**dict(row), "content": json.loads(row["content_json"])} for row in rows]

    def begin_invocation(self, tenant_id: str, run_id: str, tool_name: str, idempotency_key: str, request: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        request_hash = sha256_json(request)
        with self.transaction() as cursor:
            existing = cursor.execute(
                "SELECT * FROM tool_invocations WHERE tenant_id = ? AND tool_name = ? AND idempotency_key = ?",
                (tenant_id, tool_name, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise Conflict("Idempotency key was reused with a different tool payload.")
                result = json.loads(existing["result_json"]) if existing["result_json"] else None
                return str(existing["invocation_id"]), result
            invocation_id = f"invoke-{uuid.uuid4()}"
            cursor.execute(
                """
                INSERT INTO tool_invocations(invocation_id, tenant_id, run_id, tool_name, idempotency_key, request_json,
                  request_hash, status, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'started', ?)
                """,
                (invocation_id, tenant_id, run_id, tool_name, idempotency_key, canonical_json(request), request_hash, utc_now()),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "TOOL_DISPATCH_INTENT", "ACTION_IN_PROGRESS", "authority-engine", {"invocation_id": invocation_id, "tool": tool_name, "request_hash": request_hash, "idempotency_key": idempotency_key})
        return invocation_id, None

    def record_invocation_attempt(self, tenant_id: str, run_id: str, invocation_id: str, attempt: int, error: str | None = None) -> None:
        with self.transaction() as cursor:
            cursor.execute("UPDATE tool_invocations SET attempts = ? WHERE tenant_id = ? AND invocation_id = ?", (attempt, tenant_id, invocation_id))
            self._append_event_cursor(cursor, tenant_id, run_id, "TOOL_ATTEMPT", "ACTION_IN_PROGRESS", "authority-engine", {"invocation_id": invocation_id, "attempt": attempt, "error": error})

    def complete_invocation(
        self,
        tenant_id: str,
        run_id: str,
        invocation_id: str,
        result: dict[str, Any],
        *,
        latency_ms: int | None = None,
        retry_count: int | None = None,
    ) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE tool_invocations SET status = 'succeeded', result_json = ?, completed_at = ? WHERE tenant_id = ? AND invocation_id = ?",
                (canonical_json(result), utc_now(), tenant_id, invocation_id),
            )
            payload = {"invocation_id": invocation_id, "result_hash": sha256_json(result)}
            if latency_ms is not None or retry_count is not None:
                payload["observability"] = {
                    "latency_ms": latency_ms,
                    "retry_count": retry_count,
                }
            self._append_event_cursor(cursor, tenant_id, run_id, "TOOL_SUCCEEDED", "ACTION_IN_PROGRESS", "authority-engine", payload)

    def fail_invocation(
        self,
        tenant_id: str,
        run_id: str,
        invocation_id: str,
        code: str,
        message: str,
        *,
        latency_ms: int | None = None,
        retry_count: int | None = None,
    ) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE tool_invocations SET status = 'failed', error_code = ?, error_message = ?, completed_at = ? WHERE tenant_id = ? AND invocation_id = ?",
                (code, message, utc_now(), tenant_id, invocation_id),
            )
            payload = {"invocation_id": invocation_id, "code": code, "message": message}
            if latency_ms is not None or retry_count is not None:
                payload["observability"] = {
                    "latency_ms": latency_ms,
                    "retry_count": retry_count,
                }
            self._append_event_cursor(cursor, tenant_id, run_id, "TOOL_FAILED", "ACTION_IN_PROGRESS", "authority-engine", payload)

    def save_action_artifact(self, tenant_id: str, run_id: str, idempotency_key: str, artifact: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as cursor:
            existing = cursor.execute("SELECT * FROM action_artifacts WHERE tenant_id = ? AND idempotency_key = ?", (tenant_id, idempotency_key)).fetchone()
            if existing:
                return json.loads(existing["artifact_json"])
            artifact_id = f"artifact-{uuid.uuid4()}"
            stored = {"artifact_id": artifact_id, **artifact}
            cursor.execute(
                "INSERT INTO action_artifacts(artifact_id, tenant_id, run_id, idempotency_key, artifact_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (artifact_id, tenant_id, run_id, idempotency_key, canonical_json(stored), utc_now()),
            )
        return stored

    def compensate_action_artifact(self, tenant_id: str, idempotency_key: str) -> dict[str, Any]:
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM action_artifacts WHERE tenant_id = ? AND idempotency_key = ?", (tenant_id, idempotency_key)).fetchone()
            if not row:
                raise NotFound("Action artifact to compensate was not found.")
            if not row["compensated_at"]:
                cursor.execute("UPDATE action_artifacts SET compensated_at = ? WHERE artifact_id = ?", (utc_now(), row["artifact_id"]))
            artifact = json.loads(row["artifact_json"])
        return {**artifact, "compensated": True}

    def save_probe(self, tenant_id: str, run_id: str, phase: str, probe_id: str, passed: bool, detail: dict[str, Any]) -> None:
        with self.transaction() as cursor:
            run = cursor.execute("SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not run:
                raise NotFound("Run not found.")
            cursor.execute(
                "INSERT INTO probe_results(probe_result_id, tenant_id, run_id, phase, probe_id, passed, detail_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"probe-{uuid.uuid4()}", tenant_id, run_id, phase, probe_id, int(passed), canonical_json(detail), utc_now()),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "PROBE_COMPLETED", run["state"], "authority-engine", {"phase": phase, "probe_id": probe_id, "passed": passed, "detail": detail})

    def append_event(self, tenant_id: str, run_id: str | None, event_type: str, state: str | None, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as cursor:
            return self._append_event_cursor(cursor, tenant_id, run_id, event_type, state, actor_id, payload)

    def set_output(self, tenant_id: str, run_id: str, output: dict[str, Any]) -> None:
        with self.transaction() as cursor:
            state = cursor.execute("SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not state:
                raise NotFound("Run not found.")
            cursor.execute("UPDATE runs SET output_json = ?, last_error = NULL, updated_at = ? WHERE tenant_id = ? AND run_id = ?", (canonical_json(output), utc_now(), tenant_id, run_id))
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_OUTPUT_RECORDED", state["state"], "authority-engine", {"output_hash": sha256_json(output)})

    def increment_attempt(self, tenant_id: str, run_id: str) -> int:
        with self.transaction() as cursor:
            cursor.execute("UPDATE runs SET attempt = attempt + 1, updated_at = ? WHERE tenant_id = ? AND run_id = ?", (utc_now(), tenant_id, run_id))
            row = cursor.execute("SELECT attempt FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
        if not row:
            raise NotFound("Run not found.")
        return int(row["attempt"])

    def events_after(self, tenant_id: str, run_id: str | None, sequence: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        with self.lock:
            if run_id is None:
                rows = self.connection.execute(
                    "SELECT * FROM audit_events WHERE tenant_id = ? AND run_id IS NULL AND sequence > ? ORDER BY sequence LIMIT ?",
                    (tenant_id, sequence, min(limit, 500)),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    "SELECT * FROM audit_events WHERE tenant_id = ? AND run_id = ? AND sequence > ? ORDER BY sequence LIMIT ?",
                    (tenant_id, run_id, sequence, min(limit, 500)),
                ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def verify_audit_chain(self, tenant_id: str) -> tuple[bool, int, int | None]:
        with self.lock:
            rows = self.connection.execute("SELECT * FROM audit_events WHERE tenant_id = ? ORDER BY sequence", (tenant_id,)).fetchall()
        previous_hash = "0" * 64
        for index, row in enumerate(rows):
            core = self._event_core(row["event_id"], row["tenant_id"], row["run_id"], row["event_type"], row["state"], row["actor_id"], row["payload_json"], row["created_at"], previous_hash)
            expected = hashlib.sha256((previous_hash + canonical_json(core)).encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return False, len(rows), int(row["sequence"])
            previous_hash = row["event_hash"]
        return True, len(rows), None

    def pending_audit_anchors(
        self,
        limit: int = 100,
        include_deferred: bool = False,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        where = "delivered_at IS NULL"
        parameters: list[Any] = []
        if tenant_id is not None:
            where += " AND tenant_id = ?"
            parameters.append(tenant_id)
        if not include_deferred:
            where += " AND next_attempt_at <= ?"
            parameters.append(utc_now())
        parameters.append(min(max(limit, 1), 500))
        with self.lock:
            rows = self.connection.execute(
                f"SELECT * FROM audit_anchor_outbox WHERE {where} ORDER BY created_at, event_id LIMIT ?",
                tuple(parameters),
            ).fetchall()
        return [{**dict(row), "envelope": json.loads(row["envelope_json"])} for row in rows]

    def mark_audit_anchor_delivered(self, event_id: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE audit_anchor_outbox SET delivered_at = ?, last_error = NULL WHERE event_id = ? AND delivered_at IS NULL",
                (utc_now(), event_id),
            )

    def record_audit_anchor_failure(self, event_id: str, error: str) -> None:
        with self.transaction() as cursor:
            row = cursor.execute(
                "SELECT attempts FROM audit_anchor_outbox WHERE event_id = ? AND delivered_at IS NULL",
                (event_id,),
            ).fetchone()
            if not row:
                return
            attempts = int(row["attempts"]) + 1
            retry_seconds = min(300, 2 ** min(attempts, 8))
            next_attempt_at = (datetime.now(timezone.utc) + timedelta(seconds=retry_seconds)).isoformat()
            cursor.execute(
                "UPDATE audit_anchor_outbox SET attempts = ?, next_attempt_at = ?, last_error = ? WHERE event_id = ? AND delivered_at IS NULL",
                (attempts, next_attempt_at, error[:500], event_id),
            )

    def audit_anchor_backlog(self, tenant_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS count FROM audit_anchor_outbox WHERE delivered_at IS NULL"
        parameters: tuple[Any, ...] = ()
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            parameters = (tenant_id,)
        with self.lock:
            row = self.connection.execute(query, parameters).fetchone()
        return int(row["count"]) if row else 0

    def consume_request_rate_limit(
        self,
        client_key: str,
        limit: int,
        window_seconds: int,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Request rate-limit values must be positive.")
        current_epoch = int(now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp())
        window_started_at = current_epoch - (current_epoch % window_seconds)
        bucket_key = f"{hashlib.sha256(client_key.encode('utf-8')).hexdigest()}:{window_started_at}"
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO request_rate_limits(bucket_key, window_started_at, request_count)
                VALUES (?, ?, 1)
                ON CONFLICT(bucket_key) DO UPDATE SET request_count = request_rate_limits.request_count + 1
                """,
                (bucket_key, window_started_at),
            )
            row = cursor.execute(
                "SELECT request_count FROM request_rate_limits WHERE bucket_key = ?",
                (bucket_key,),
            ).fetchone()
            cursor.execute(
                "DELETE FROM request_rate_limits WHERE window_started_at < ?",
                (window_started_at - (window_seconds * 2),),
            )
        count = int(row["request_count"]) if row else 0
        allowed = count <= limit
        return {
            "allowed": allowed,
            "limit": limit,
            "remaining": max(0, limit - count),
            "retry_after": max(1, window_started_at + window_seconds - current_epoch) if not allowed else 0,
            "window_started_at": window_started_at,
        }

    def audit_anchor_delivery_status(
        self,
        max_age_seconds: float | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        where = ""
        parameters: tuple[Any, ...] = ()
        if tenant_id is not None:
            where = " WHERE tenant_id = ?"
            parameters = (tenant_id,)
        with self.lock:
            row = self.connection.execute(
                f"""
                SELECT
                  COUNT(CASE WHEN delivered_at IS NOT NULL THEN 1 END) AS delivered_count,
                  MAX(delivered_at) AS last_delivered_at
                FROM audit_anchor_outbox
                {where}
                """,
                parameters,
            ).fetchone()
        delivered_count = int(row["delivered_count"] or 0) if row else 0
        last_delivered_at = row["last_delivered_at"] if row else None
        fresh = delivered_count > 0
        if max_age_seconds is not None:
            delivered_at = parse_iso_datetime(last_delivered_at) if last_delivered_at else None
            now = datetime.now(timezone.utc)
            fresh = bool(
                delivered_at
                and now - timedelta(seconds=max_age_seconds) <= delivered_at <= now + timedelta(minutes=5)
            )
        return {
            "verified": fresh,
            "fresh": fresh,
            "delivered_count": delivered_count,
            "last_delivered_at": last_delivered_at,
        }

    def _append_event_cursor(self, cursor: StoreCursor, tenant_id: str, run_id: str | None, event_type: str, state: str | None, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = cursor.execute("SELECT event_hash FROM audit_events WHERE tenant_id = ? ORDER BY sequence DESC LIMIT 1", (tenant_id,)).fetchone()
        previous_hash = str(previous["event_hash"]) if previous else "0" * 64
        event_id = f"event-{uuid.uuid4()}"
        created_at = utc_now()
        payload_json = canonical_json(payload)
        core = self._event_core(event_id, tenant_id, run_id, event_type, state, actor_id, payload_json, created_at, previous_hash)
        event_hash = hashlib.sha256((previous_hash + canonical_json(core)).encode("utf-8")).hexdigest()
        sequence = self._insert_audit_event(cursor, event_id, tenant_id, run_id, event_type, state, actor_id, payload_json, created_at, previous_hash, event_hash)
        envelope = {**core, "event_hash": event_hash, "sequence": sequence}
        cursor.execute(
            """
            INSERT INTO audit_anchor_outbox(event_id, tenant_id, envelope_json, attempts, next_attempt_at, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (event_id, tenant_id, canonical_json(envelope), created_at, created_at),
        )
        return envelope

    def _insert_audit_event(
        self,
        cursor: StoreCursor,
        event_id: str,
        tenant_id: str,
        run_id: str | None,
        event_type: str,
        state: str | None,
        actor_id: str,
        payload_json: str,
        created_at: str,
        previous_hash: str,
        event_hash: str,
    ) -> int:
        cursor.execute(
            "INSERT INTO audit_events(event_id, tenant_id, run_id, event_type, state, actor_id, payload_json, created_at, previous_hash, event_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, tenant_id, run_id, event_type, state, actor_id, payload_json, created_at, previous_hash, event_hash),
        )
        return int(cursor.lastrowid or 0)

    def _upsert_evidence_sql(self) -> str:
        return """
                INSERT OR REPLACE INTO evidence(evidence_record_id, tenant_id, run_id, evidence_id, kind, source_ref,
                  content_json, content_hash, collected_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

    @staticmethod
    def _row_to_workspace(row: Any) -> WorkspaceRecord:
        return WorkspaceRecord(
            workspace_id=row["workspace_id"],
            tenant_id=row["tenant_id"],
            revision=int(row["revision"]),
            document=json.loads(row["document_json"]),
            document_hash=row["document_hash"],
            created_by=row["created_by"],
            updated_by=row["updated_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_execution_job(row: Any) -> dict[str, Any]:
        return {
            **dict(row),
            "payload": json.loads(row["payload_json"]),
            "attempts": int(row["attempts"]),
        }

    @staticmethod
    def _event_core(event_id: str, tenant_id: str, run_id: str | None, event_type: str, state: str | None, actor_id: str, payload_json: str, created_at: str, previous_hash: str) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "run_id": run_id,
            "event_type": event_type,
            "state": state,
            "actor_id": actor_id,
            "payload_json": payload_json,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            loop_id=row["loop_id"],
            title=row["title"],
            trigger=row["trigger_text"],
            state=row["state"],
            runner_status=row["runner_status"],
            risk_tier=row["risk_tier"],
            requires_approval=bool(row["requires_approval"]),
            payload_hash=row["payload_hash"],
            plan=ExecutionPlan.model_validate(json.loads(row["plan_json"])),
            attempt=row["attempt"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_error=row["last_error"],
            output=json.loads(row["output_json"]) if row["output_json"] else None,
            recovery_of=row["recovery_of"],
            effectiveness_due_at=row["effectiveness_due_at"],
        )

    @staticmethod
    def _release_initiative_payload(row: Any) -> dict[str, Any]:
        return {
            "tenant_id": row["tenant_id"],
            "workspace_id": row["workspace_id"],
            "title": row["title"],
            "description": row["description"],
            "workflow_type": row["workflow_type"],
            "business_outcome": row["business_outcome"],
            "maturity": row["maturity"],
            "risk_tier": row["risk_tier"],
            "status": row["status"],
            "release_name": row["release_name"],
            "loop_bundle_ids": json.loads(row["loop_bundle_json"]),
            "source_event_ids": json.loads(row["source_event_ids_json"]),
            "release_assurance": json.loads(row["release_assurance_json"]),
        }

    @staticmethod
    def _row_to_release_initiative(row: Any) -> ReleaseInitiativeRecord:
        return ReleaseInitiativeRecord(
            initiative_id=row["initiative_id"],
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            title=row["title"],
            description=row["description"],
            workflow_type=row["workflow_type"],
            business_outcome=row["business_outcome"],
            maturity=row["maturity"],
            risk_tier=row["risk_tier"],
            status=row["status"],
            release_name=row["release_name"],
            loop_bundle_ids=json.loads(row["loop_bundle_json"]),
            source_event_ids=json.loads(row["source_event_ids_json"]),
            release_assurance=json.loads(row["release_assurance_json"]),
            freshness_summary=json.loads(row["freshness_summary_json"]),
            readiness_verdict=json.loads(row["readiness_verdict_json"]),
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_connector_event(row: Any) -> ConnectorEventRecord:
        return ConnectorEventRecord(
            connector_event_id=row["connector_event_id"],
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            system=row["system"],
            event_kind=row["event_kind"],
            external_id=row["external_id"],
            label=row["label"],
            url=row["url"],
            observed_at=row["observed_at"],
            payload_hash=row["payload_hash"],
            payload=json.loads(row["payload_json"]),
            verification_status=row["verification_status"],
            delivery_id=row["delivery_id"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )
