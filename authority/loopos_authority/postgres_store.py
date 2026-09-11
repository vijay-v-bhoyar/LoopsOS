from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .corpus import Corpus
from .contracts import REQUIRED_AUDIT_TRIGGERS, REQUIRED_POSTGRES_TABLES
from .store import AuthorityStore, StoreCursor


def _postgres_sql(sql: str) -> str:
    return sql.replace("?", "%s")


def split_postgres_script(sql: str) -> list[str]:
    statements: list[str] = []
    start = 0
    index = 0
    in_dollar_quote = False
    while index < len(sql):
        if sql.startswith("$$", index):
            in_dollar_quote = not in_dollar_quote
            index += 2
            continue
        if sql[index] == ";" and not in_dollar_quote:
            statement = sql[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1
        index += 1
    tail = sql[start:].strip()
    if tail:
        statements.append(tail)
    return statements


class PostgresCursor:
    def __init__(self, cursor: Any, close_after_fetch: bool = False):
        self._cursor = cursor
        self._close_after_fetch = close_after_fetch
        self.lastrowid: int | None = None

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> "PostgresCursor":
        self.lastrowid = None
        self._cursor.execute(_postgres_sql(sql), tuple(parameters))
        return self

    def fetchone(self) -> Any:
        try:
            return self._cursor.fetchone()
        finally:
            if self._close_after_fetch:
                self.close()

    def fetchall(self) -> list[Any]:
        try:
            return list(self._cursor.fetchall())
        finally:
            if self._close_after_fetch:
                self.close()

    def close(self) -> None:
        self._cursor.close()


class PostgresConnection:
    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError("Postgres storage requires the optional psycopg package. Install authority/requirements.txt.") from error
        self._connection = psycopg.connect(
            dsn,
            autocommit=True,
            row_factory=dict_row,
            prepare_threshold=None,
        )

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self._connection.cursor())

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> PostgresCursor:
        cursor = PostgresCursor(self._connection.cursor(), close_after_fetch=True)
        return cursor.execute(sql, parameters)

    def executescript(self, sql: str) -> None:
        with self._connection.cursor() as cursor:
            try:
                cursor.execute("BEGIN")
                for statement in split_postgres_script(sql):
                    cursor.execute(statement)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


class PostgresAuthorityStore(AuthorityStore):
    def __init__(self, dsn: str, corpus: Corpus, migrations_dir: Path):
        self.corpus = corpus
        self.connection = PostgresConnection(dsn)
        self.lock = threading.RLock()
        self.migrations_dir = migrations_dir
        self._initialize()

    @contextmanager
    def transaction(self) -> Iterator[StoreCursor]:
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute("BEGIN")
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
            migrations = sorted(self.migrations_dir.glob("*.sql"))
            if not migrations:
                raise RuntimeError("Postgres authority migrations are missing.")
            for migration in migrations:
                self.connection.executescript(migration.read_text(encoding="utf-8"))
            self.verify_schema()

    def verify_schema(self) -> None:
        with self.lock:
            tables = {
                str(row["table_name"])
                for row in self.connection.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """
                ).fetchall()
            }
            missing_tables = sorted(set(REQUIRED_POSTGRES_TABLES) - tables)
            if missing_tables:
                raise RuntimeError(
                    "Postgres authority schema is missing required tables: "
                    + ", ".join(missing_tables)
                    + "."
                )

            row_level_security = {
                str(row["relname"])
                for row in self.connection.execute(
                    """
                    SELECT relname
                    FROM pg_class
                    WHERE relnamespace = 'public'::regnamespace
                      AND relkind = 'r'
                      AND relrowsecurity
                    """
                ).fetchall()
            }
            missing_rls = sorted(set(REQUIRED_POSTGRES_TABLES) - row_level_security)
            if missing_rls:
                raise RuntimeError(
                    "Postgres authority schema is missing row-level security on: "
                    + ", ".join(missing_rls)
                    + "."
                )

            audit_triggers = {
                str(row["tgname"])
                for row in self.connection.execute(
                    """
                    SELECT tgname
                    FROM pg_trigger
                    WHERE tgrelid = 'public.audit_events'::regclass
                      AND NOT tgisinternal
                    """
                ).fetchall()
            }
            missing_triggers = sorted(REQUIRED_AUDIT_TRIGGERS - audit_triggers)
            if missing_triggers:
                raise RuntimeError(
                    "Postgres authority schema is missing append-only audit triggers: "
                    + ", ".join(missing_triggers)
                    + "."
                )

    def _append_event_cursor(
        self,
        cursor: StoreCursor,
        tenant_id: str,
        run_id: str | None,
        event_type: str,
        state: str | None,
        actor_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Serialize the predecessor read and insert for one tenant across
        # Postgres connections so concurrent requests cannot fork its chain.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
            (tenant_id,),
        )
        return super()._append_event_cursor(cursor, tenant_id, run_id, event_type, state, actor_id, payload)

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
            """
            INSERT INTO audit_events(event_id, tenant_id, run_id, event_type, state, actor_id, payload_json,
              created_at, previous_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING sequence
            """,
            (event_id, tenant_id, run_id, event_type, state, actor_id, payload_json, created_at, previous_hash, event_hash),
        )
        row = cursor.fetchone()
        return int(row["sequence"])

    def _upsert_evidence_sql(self) -> str:
        return """
                INSERT INTO evidence(evidence_record_id, tenant_id, run_id, evidence_id, kind, source_ref,
                  content_json, content_hash, collected_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, run_id, evidence_id)
                DO UPDATE SET
                  evidence_record_id = EXCLUDED.evidence_record_id,
                  kind = EXCLUDED.kind,
                  source_ref = EXCLUDED.source_ref,
                  content_json = EXCLUDED.content_json,
                  content_hash = EXCLUDED.content_hash,
                  collected_at = EXCLUDED.collected_at,
                  expires_at = EXCLUDED.expires_at
                """

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
                  AND kill_switches.active = true
              )
            ORDER BY available_at, created_at
            LIMIT ?
            FOR UPDATE SKIP LOCKED
        """

    def _run_for_update_sql(self) -> str:
        return "SELECT * FROM runs WHERE tenant_id = ? AND run_id = ? FOR UPDATE"

    def _due_effectiveness_claim_sql(self) -> str:
        return """
            SELECT * FROM runs
            WHERE state = 'EFFECTIVENESS_PENDING' AND runner_status = 'awaiting_effectiveness'
              AND effectiveness_due_at IS NOT NULL AND effectiveness_due_at <= ?
            ORDER BY effectiveness_due_at
            LIMIT ?
            FOR UPDATE SKIP LOCKED
        """

    def _incomplete_runs_claim_sql(self) -> str:
        return """
            SELECT * FROM runs
            WHERE runner_status IN ('queued', 'running')
            ORDER BY updated_at
            FOR UPDATE SKIP LOCKED
        """
