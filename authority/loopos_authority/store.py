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
from .models import Actor, ApprovalRequest, ConnectorEventRecord, ConnectorEventRequest, CreateReleaseInitiativeRequest, CreateRunRequest, ExecutionPlan, ReleaseInitiativeRecord, ReleaseProofPack, RunRecord, WorkspaceRecord


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
        for loop_id in request.loop_bundle_ids:
            if loop_id not in self.corpus.loop_descriptors:
                raise NotFound(f"Unknown loop ID: {loop_id}")
        known_event_rows = self._connector_event_rows(actor.tenant_id, request.source_event_ids)
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
        return [self._row_to_release_initiative(row) for row in rows]

    def get_release_initiative(self, tenant_id: str, initiative_id: str) -> ReleaseInitiativeRecord:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM release_initiatives WHERE tenant_id = ? AND initiative_id = ?",
                (tenant_id, initiative_id),
            ).fetchone()
        if not row:
            raise NotFound("Release initiative not found.")
        return self._row_to_release_initiative(row)

    def build_release_proof_pack(self, tenant_id: str, initiative_id: str, actor_id: str = "authority-reader") -> ReleaseProofPack:
        initiative = self.get_release_initiative(tenant_id, initiative_id)
        source_events = self._connector_event_rows(tenant_id, initiative.source_event_ids)
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

    def _connector_event_rows(self, tenant_id: str, event_ids: list[str]) -> dict[str, Any]:
        if not event_ids:
            return {}
        placeholders = ",".join("?" for _ in event_ids)
        with self.lock:
            rows = self.connection.execute(
                f"SELECT * FROM connector_events WHERE tenant_id = ? AND connector_event_id IN ({placeholders})",
                [tenant_id, *event_ids],
            ).fetchall()
        return {str(row["connector_event_id"]): row for row in rows}

    @staticmethod
    def _release_freshness_summary(source_event_ids: list[str], event_rows: dict[str, Any], evaluated_at: str) -> dict[str, Any]:
        max_age_seconds = 86_400
        evaluated = parse_iso_datetime(evaluated_at) or datetime.now(timezone.utc)
        stale_event_ids: list[str] = []
        invalid_observed_at_event_ids: list[str] = []
        observed_times: list[datetime] = []
        verification_counts = {"session_authenticated": 0, "verified_webhook": 0}
        for event_id in source_event_ids:
            row = event_rows.get(event_id)
            if row is None:
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
        status = "missing" if not source_event_ids else "fresh"
        if stale_event_ids or invalid_observed_at_event_ids:
            status = "stale"
        return {
            "status": status,
            "policy": "release connector evidence must be observed within 24 hours of the authority release record",
            "max_age_seconds": max_age_seconds,
            "evaluated_at": evaluated_at,
            "source_event_count": len(source_event_ids),
            "verified_webhook_count": verification_counts["verified_webhook"],
            "session_authenticated_count": verification_counts["session_authenticated"],
            "stale_event_ids": stale_event_ids,
            "invalid_observed_at_event_ids": invalid_observed_at_event_ids,
            "oldest_observed_at": min(observed_times).isoformat() if observed_times else None,
            "newest_observed_at": max(observed_times).isoformat() if observed_times else None,
        }

    @staticmethod
    def _release_readiness_verdict(release_assurance: dict[str, Any], freshness_summary: dict[str, Any], evaluated_at: str) -> dict[str, Any]:
        gates = release_assurance.get("gates") if isinstance(release_assurance.get("gates"), list) else []
        gate_statuses = [str(gate.get("status", "missing")) if isinstance(gate, dict) else "missing" for gate in gates]
        failing_reasons: list[str] = []
        review_reasons: list[str] = []
        if freshness_summary.get("status") != "fresh":
            failing_reasons.append(f"connector evidence freshness is {freshness_summary.get('status', 'missing')}")
        if not gate_statuses:
            failing_reasons.append("no release assurance gates were recorded")
        blocked_or_gap = [status for status in gate_statuses if status in {"blocked", "gap", "missing"}]
        if blocked_or_gap:
            failing_reasons.append(f"{len(blocked_or_gap)} release gates are blocked, missing, or have evidence gaps")
        review_required = [status for status in gate_statuses if status in {"review_required", "exception_active"}]
        if review_required:
            review_reasons.append(f"{len(review_required)} release gates require review or active exception approval")
        verdict = "GO"
        if failing_reasons:
            verdict = "NO_GO"
        elif review_reasons:
            verdict = "REVIEW_REQUIRED"
        return {
            "verdict": verdict,
            "evaluated_at": evaluated_at,
            "policy": "GO only when connector evidence is fresh and every release assurance gate is passed; stale evidence, missing gates, blocked gates, and evidence gaps fail closed",
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
                row = cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if request_key_conflict:
            raise Conflict("Idempotency key was reused with a different run payload.")
        return self._row_to_run(row)

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

    def claim_run(self, tenant_id: str, run_id: str) -> RunRecord:
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            if row["runner_status"] == "running":
                raise Conflict("Run is already running.")
            if self.corpus.is_terminal(row["state"]):
                raise Conflict(f"Terminal run {run_id} cannot be started again.")
            if row["state"] == "EFFECTIVENESS_PENDING" and row["effectiveness_due_at"] and datetime.fromisoformat(row["effectiveness_due_at"]) > datetime.now(timezone.utc):
                raise Conflict("The effectiveness observation window is not due yet.")
            timestamp = utc_now()
            cursor.execute("UPDATE runs SET runner_status = 'running', updated_at = ? WHERE run_id = ?", (timestamp, run_id))
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_CLAIMED", row["state"], "authority-engine", {})
            updated = cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._row_to_run(updated)

    def queue_run(self, tenant_id: str, run_id: str, actor_id: str, command: str = "execute") -> RunRecord:
        with self.transaction() as cursor:
            row = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            if row["runner_status"] in {"queued", "running"}:
                raise Conflict("Run is already queued or running.")
            if self.corpus.is_terminal(row["state"]):
                raise Conflict("Terminal runs cannot accept new commands.")
            if row["state"] == "EFFECTIVENESS_PENDING" and row["effectiveness_due_at"] and datetime.fromisoformat(row["effectiveness_due_at"]) > datetime.now(timezone.utc):
                raise Conflict("The effectiveness observation window is not due yet.")
            cursor.execute("UPDATE runs SET runner_status = 'queued', updated_at = ? WHERE run_id = ?", (utc_now(), run_id))
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_QUEUED", row["state"], actor_id, {"command": command})
            updated = cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._row_to_run(updated)

    def release_run(self, tenant_id: str, run_id: str, status: str = "idle", error: str | None = None) -> None:
        with self.transaction() as cursor:
            row = cursor.execute("SELECT state FROM runs WHERE tenant_id = ? AND run_id = ?", (tenant_id, run_id)).fetchone()
            if not row:
                raise NotFound("Run not found.")
            cursor.execute(
                "UPDATE runs SET runner_status = ?, last_error = ?, updated_at = ? WHERE run_id = ?",
                (status, error, utc_now(), run_id),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_RELEASED", row["state"], "authority-engine", {"runner_status": status, "error": error})

    def requeue_incomplete_runs(self) -> list[tuple[str, str]]:
        recovered: list[tuple[str, str]] = []
        with self.transaction() as cursor:
            rows = cursor.execute("SELECT * FROM runs WHERE runner_status IN ('queued', 'running') ORDER BY updated_at").fetchall()
            for row in rows:
                cursor.execute("UPDATE runs SET runner_status = 'queued', updated_at = ? WHERE run_id = ?", (utc_now(), row["run_id"]))
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
            cursor.execute("UPDATE runs SET effectiveness_due_at = ?, runner_status = 'awaiting_effectiveness', updated_at = ? WHERE run_id = ?", (due_at, utc_now(), run_id))
            self._append_event_cursor(cursor, tenant_id, run_id, "EFFECTIVENESS_SCHEDULED", row["state"], "authority-engine", {"due_at": due_at, "delay_seconds": delay_seconds})
            self._append_event_cursor(cursor, tenant_id, run_id, "RUN_RELEASED", row["state"], "authority-engine", {"runner_status": "awaiting_effectiveness", "error": None})
        return due_at

    def queue_due_effectiveness(self, limit: int = 20) -> list[tuple[str, str]]:
        due: list[tuple[str, str]] = []
        with self.transaction() as cursor:
            rows = cursor.execute(
                """
                SELECT * FROM runs WHERE state = 'EFFECTIVENESS_PENDING' AND runner_status = 'awaiting_effectiveness'
                  AND effectiveness_due_at IS NOT NULL AND effectiveness_due_at <= ? ORDER BY effectiveness_due_at LIMIT ?
                """,
                (utc_now(), limit),
            ).fetchall()
            for row in rows:
                cursor.execute("UPDATE runs SET runner_status = 'queued', updated_at = ? WHERE run_id = ?", (utc_now(), row["run_id"]))
                self._append_event_cursor(cursor, row["tenant_id"], row["run_id"], "EFFECTIVENESS_QUEUED", row["state"], "authority-scheduler", {"due_at": row["effectiveness_due_at"]})
                due.append((str(row["tenant_id"]), str(row["run_id"])))
        return due

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
                cursor.execute("UPDATE runs SET state = ?, updated_at = ? WHERE run_id = ?", (to_state, timestamp, run_id))
                self._append_event_cursor(cursor, tenant_id, run_id, "STATE_TRANSITION", to_state, actor_id, {"from_state": from_state, "to_state": to_state, **(detail or {})})
            updated = cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
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
        approval_id = ""
        with self.transaction() as cursor:
            run = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (actor.tenant_id, run_id)).fetchone()
            if not run:
                raise NotFound("Run not found.")
            if run["state"] != "PLANNED":
                raise Conflict("Approval is accepted only while a run is PLANNED.")
            if request.payload_hash != run["payload_hash"]:
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
        decision_id = ""
        with self.transaction() as cursor:
            run = cursor.execute("SELECT * FROM runs WHERE tenant_id = ? AND run_id = ?", (actor.tenant_id, run_id)).fetchone()
            if not run:
                raise NotFound("Run not found.")
            if run["state"] != "PLANNED":
                raise Conflict("Rejection is accepted only while a run is PLANNED.")
            if request.payload_hash != run["payload_hash"]:
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
                    "UPDATE runs SET state = 'BLOCKED', runner_status = 'failed', last_error = ?, updated_at = ? WHERE run_id = ?",
                    (f"Rejected by {actor.user_id}: {request.decision_reason}", created_at, run_id),
                )
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "APPROVAL_REJECTED", "PLANNED", actor.user_id, {"decision_id": decision_id, "payload_hash": request.payload_hash, "render_hash": sha256_json(render), "reason": request.decision_reason})
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "STATE_TRANSITION", "BLOCKED", actor.user_id, {"from_state": "PLANNED", "to_state": "BLOCKED", "reason": "approval_rejected"})
                self._append_event_cursor(cursor, actor.tenant_id, run_id, "RUN_RELEASED", "BLOCKED", actor.user_id, {"runner_status": "failed", "error": request.decision_reason})
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

    def complete_invocation(self, tenant_id: str, run_id: str, invocation_id: str, result: dict[str, Any]) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE tool_invocations SET status = 'succeeded', result_json = ?, completed_at = ? WHERE tenant_id = ? AND invocation_id = ?",
                (canonical_json(result), utc_now(), tenant_id, invocation_id),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "TOOL_SUCCEEDED", "ACTION_IN_PROGRESS", "authority-engine", {"invocation_id": invocation_id, "result_hash": sha256_json(result)})

    def fail_invocation(self, tenant_id: str, run_id: str, invocation_id: str, code: str, message: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE tool_invocations SET status = 'failed', error_code = ?, error_message = ?, completed_at = ? WHERE tenant_id = ? AND invocation_id = ?",
                (code, message, utc_now(), tenant_id, invocation_id),
            )
            self._append_event_cursor(cursor, tenant_id, run_id, "TOOL_FAILED", "ACTION_IN_PROGRESS", "authority-engine", {"invocation_id": invocation_id, "code": code, "message": message})

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
            cursor.execute("UPDATE runs SET output_json = ?, last_error = NULL, updated_at = ? WHERE run_id = ?", (canonical_json(output), utc_now(), run_id))
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

    def pending_audit_anchors(self, limit: int = 100, include_deferred: bool = False) -> list[dict[str, Any]]:
        where = "delivered_at IS NULL"
        parameters: list[Any] = []
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

    def audit_anchor_backlog(self) -> int:
        with self.lock:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM audit_anchor_outbox WHERE delivered_at IS NULL"
            ).fetchone()
        return int(row["count"]) if row else 0

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
