from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


EXPECTED_TABLES = (
    "action_artifacts",
    "approvals",
    "audit_anchor_outbox",
    "audit_events",
    "connector_events",
    "evidence",
    "execution_jobs",
    "operational_signals",
    "probe_results",
    "release_initiatives",
    "runs",
    "tool_invocations",
    "workspaces",
)
EXPECTED_AUDIT_TRIGGERS = {"audit_events_no_delete", "audit_events_no_update"}


class RestoreEvidenceError(RuntimeError):
    pass


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        if check:
            raise RestoreEvidenceError(f"{command[0]} could not be executed: {error}.") from error
        return subprocess.CompletedProcess(command, 127, "", str(error))
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RestoreEvidenceError(f"{' '.join(command[:3])} failed: {detail}")
    return result


def _inspect_container(container: str) -> dict[str, Any]:
    result = _run(["docker", "inspect", container])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RestoreEvidenceError("Docker returned invalid container inspection JSON.") from error
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise RestoreEvidenceError("Docker returned an unexpected container inspection payload.")
    return payload[0]


def _connect(dsn: str, database: str | None = None):
    try:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict, make_conninfo
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RestoreEvidenceError("Postgres restore verification requires psycopg.") from error

    connection_dsn = dsn
    if database is not None:
        parameters = conninfo_to_dict(dsn)
        parameters["dbname"] = database
        connection_dsn = make_conninfo(**parameters)
    try:
        return psycopg.connect(connection_dsn, autocommit=True, row_factory=dict_row)
    except Exception as error:
        raise RestoreEvidenceError("Postgres restore verification could not connect to the database.") from error


def _snapshot(dsn: str, database: str | None = None) -> dict[str, Any]:
    connection = _connect(dsn, database)
    try:
        tables = [
            row["table_name"]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ).fetchall()
        ]
        row_counts = {
            table: int(connection.execute(f'SELECT count(*) AS count FROM "{table}"').fetchone()["count"])
            for table in EXPECTED_TABLES
        }
        runs = [
            tuple(row.values())
            for row in connection.execute(
                """
                SELECT run_id, tenant_id, workspace_id, loop_id, state, runner_status,
                       payload_hash, request_key, recovery_of
                FROM runs
                ORDER BY run_id
                """
            ).fetchall()
        ]
        audit_events = [
            tuple(row.values())
            for row in connection.execute(
                """
                SELECT sequence, event_id, tenant_id, run_id, event_type, state, actor_id,
                       payload_json, created_at, previous_hash, event_hash
                FROM audit_events
                ORDER BY sequence
                """
            ).fetchall()
        ]
        row_level_security = {
            row["relname"]
            for row in connection.execute(
                """
                SELECT relname
                FROM pg_class
                WHERE relnamespace = 'public'::regnamespace
                  AND relkind = 'r'
                  AND relrowsecurity
                """
            ).fetchall()
        }
        audit_triggers = {
            row["tgname"]
            for row in connection.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE tgrelid = 'public.audit_events'::regclass
                  AND NOT tgisinternal
                """
            ).fetchall()
        }
        return {
            "database": connection.info.dbname,
            "user": connection.info.user,
            "tables": tables,
            "row_counts": row_counts,
            "runs": runs,
            "audit_events": audit_events,
            "row_level_security": row_level_security,
            "audit_triggers": audit_triggers,
        }
    except Exception as error:
        raise RestoreEvidenceError("Postgres restore verification could not inspect database state.") from error
    finally:
        connection.close()


def _audit_mutation_is_denied(dsn: str, database: str) -> bool:
    connection = _connect(dsn, database)
    try:
        try:
            connection.execute(
                """
                UPDATE audit_events
                SET event_type = event_type
                WHERE sequence = (SELECT min(sequence) FROM audit_events)
                """
            )
        except Exception as error:
            return "audit events are append-only" in str(error).lower()
        return False
    finally:
        connection.close()


def _safe_error(error: Exception, dsn: str) -> str:
    rendered = str(error).replace(dsn, "[redacted-dsn]")
    parsed = urlparse(dsn)
    if parsed.password:
        rendered = rendered.replace(parsed.password, "[redacted]")
        rendered = rendered.replace(unquote(parsed.password), "[redacted]")
    return rendered


def verify_postgres_restore(
    *,
    container: str,
    source_dsn: str,
    output: Path,
    backup_output: Path,
) -> int:
    restore_database = f"loopos_restore_{uuid.uuid4().hex[:12]}"
    container_backup = f"/tmp/{restore_database}.dump"
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified": False,
        "checks": [],
    }
    restore_created = False
    started_at = time.monotonic()
    source_database = ""
    source_user = ""
    try:
        inspection = _inspect_container(container)
        source = _snapshot(source_dsn)
        source_database = source["database"]
        source_user = source["user"]
        if source["row_counts"]["runs"] < 1 or source["row_counts"]["audit_events"] < 1:
            raise RestoreEvidenceError("The source database has no live integration evidence to restore.")

        backup_output.parent.mkdir(parents=True, exist_ok=True)
        _run([
            "docker",
            "exec",
            container,
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            f"--file={container_backup}",
            f"--username={source_user}",
            source_database,
        ])
        _run(["docker", "cp", f"{container}:{container_backup}", str(backup_output)])
        backup_bytes = backup_output.read_bytes()
        if not backup_bytes:
            raise RestoreEvidenceError("Postgres produced an empty backup archive.")
        backup_sha256 = hashlib.sha256(backup_bytes).hexdigest()

        admin = _connect(source_dsn)
        try:
            from psycopg import sql

            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(restore_database)))
            restore_created = True
        finally:
            admin.close()

        _run([
            "docker",
            "exec",
            container,
            "pg_restore",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-privileges",
            f"--username={source_user}",
            f"--dbname={restore_database}",
            container_backup,
        ])
        restored = _snapshot(source_dsn, restore_database)
        checks = {
            "backup_archive_created": len(backup_bytes) > 0,
            "schema_tables_match": source["tables"] == list(EXPECTED_TABLES) == restored["tables"],
            "row_counts_match": source["row_counts"] == restored["row_counts"],
            "runs_match": source["runs"] == restored["runs"],
            "audit_events_match": source["audit_events"] == restored["audit_events"],
            "row_level_security_restored": restored["row_level_security"] == set(EXPECTED_TABLES),
            "audit_triggers_restored": EXPECTED_AUDIT_TRIGGERS.issubset(restored["audit_triggers"]),
            "audit_mutation_denied": _audit_mutation_is_denied(source_dsn, restore_database),
        }
        report["checks"] = [{"name": name, "passed": passed} for name, passed in checks.items()]
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise RestoreEvidenceError(f"Postgres restore checks failed: {', '.join(failed)}.")
        report.update({
            "backup_sha256": backup_sha256,
            "backup_bytes": len(backup_bytes),
            "source_row_counts": source["row_counts"],
            "restored_row_counts": restored["row_counts"],
            "container_image": inspection.get("Config", {}).get("Image"),
            "container_image_id": inspection.get("Image"),
            "duration_seconds": round(time.monotonic() - started_at, 3),
            "verified": True,
        })
    except Exception as error:
        report["error"] = _safe_error(error, source_dsn)
    finally:
        if restore_created:
            try:
                admin = _connect(source_dsn)
                try:
                    from psycopg import sql

                    admin.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                        (restore_database,),
                    )
                    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(restore_database)))
                finally:
                    admin.close()
            except Exception:
                report["cleanup_verified"] = False
                report["verified"] = False
                report["error"] = "The restored database could not be removed after verification."
            else:
                report["cleanup_verified"] = True
        _run(["docker", "exec", container, "rm", "-f", container_backup], check=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
    return 0 if report["verified"] and report.get("cleanup_verified") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove a reversible logical restore of the LoopOS Postgres schema.")
    parser.add_argument("--container", required=True)
    parser.add_argument("--source-dsn", default=os.getenv("LOOPOS_TEST_POSTGRES_DSN", ""))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backup-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.source_dsn:
        parser.error("--source-dsn or LOOPOS_TEST_POSTGRES_DSN is required")
    return verify_postgres_restore(
        container=args.container,
        source_dsn=args.source_dsn,
        output=args.output,
        backup_output=args.backup_output,
    )


if __name__ == "__main__":
    sys.exit(main())
