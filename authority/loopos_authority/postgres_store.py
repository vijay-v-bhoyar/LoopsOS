from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .corpus import Corpus
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
    def __init__(self, cursor: Any):
        self._cursor = cursor
        self.lastrowid: int | None = None

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> "PostgresCursor":
        self.lastrowid = None
        self._cursor.execute(_postgres_sql(sql), tuple(parameters))
        return self

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return list(self._cursor.fetchall())

    def close(self) -> None:
        self._cursor.close()


class PostgresConnection:
    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError("Postgres storage requires the optional psycopg package. Install authority/requirements.txt.") from error
        self._connection = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self._connection.cursor())

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> PostgresCursor:
        cursor = self.cursor()
        return cursor.execute(sql, parameters)

    def executescript(self, sql: str) -> None:
        with self._connection.cursor() as cursor:
            for statement in split_postgres_script(sql):
                cursor.execute(statement)

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
            for migration in sorted(self.migrations_dir.glob("*.sql")):
                self.connection.executescript(migration.read_text(encoding="utf-8"))

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
