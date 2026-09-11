from __future__ import annotations

import importlib
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[2]


class PostgresRestoreEvidenceTests(unittest.TestCase):
    def test_ci_runs_live_postgres_and_retains_restore_evidence(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "loopos-ui.yml").read_text(encoding="utf-8")

        self.assertIn(
            "postgres:17.10-alpine3.24@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193",
            workflow,
        )
        self.assertIn("LOOPOS_TEST_POSTGRES_DSN", workflow)
        self.assertIn("scripts/verify_postgres_restore.py", workflow)
        self.assertIn(".release-evidence/postgres-restore.json", workflow)
        self.assertIn(".release-evidence/postgres-backup.dump", workflow)

    def test_restore_verifier_checks_data_and_restored_controls(self) -> None:
        verifier_path = REPO_ROOT / "scripts" / "verify_postgres_restore.py"
        self.assertTrue(verifier_path.exists())
        if not verifier_path.exists():
            return

        verifier = verifier_path.read_text(encoding="utf-8")
        for contract in [
            "pg_dump",
            "pg_restore",
            "row_counts_match",
            "runs_match",
            "audit_events_match",
            "row_level_security_restored",
            "audit_mutation_denied",
            "backup_sha256",
            'report["verified"] = False',
        ]:
            self.assertIn(contract, verifier)

    def test_missing_docker_emits_a_fail_closed_report(self) -> None:
        try:
            verifier = importlib.import_module("scripts.verify_postgres_restore")
        except ModuleNotFoundError:
            self.fail("scripts.verify_postgres_restore is missing")

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "restore.json"
            backup = Path(temporary_directory) / "backup.dump"
            with patch(
                "scripts.verify_postgres_restore.subprocess.run",
                side_effect=FileNotFoundError("docker is unavailable"),
            ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = verifier.verify_postgres_restore(
                    container="postgres-test",
                    source_dsn="postgresql://secret@127.0.0.1/postgres",
                    output=output,
                    backup_output=backup,
                )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertFalse(report["verified"])
        self.assertFalse(report["cleanup_verified"])
        self.assertNotIn("secret", json.dumps(report))
        self.assertIn("could not be executed", report["error"])

    def test_container_backup_cleanup_failure_invalidates_restore_evidence(self) -> None:
        verifier = importlib.import_module("scripts.verify_postgres_restore")
        connection = Mock()
        failed_cleanup = subprocess.CompletedProcess(
            ["docker", "exec", "postgres-test", "rm", "-f", "/tmp/restore.dump"],
            17,
            "",
            "permission denied",
        )

        with patch.object(verifier, "_connect", return_value=connection), patch.object(
            verifier, "_run", return_value=failed_cleanup
        ) as run:
            cleanup_verified, failures = verifier._cleanup_restore(
                container="postgres-test",
                container_backup="/tmp/restore.dump",
                source_dsn="postgresql://secret@127.0.0.1/postgres",
                restore_database="loopos_restore_test",
                restore_created=True,
            )

        self.assertFalse(cleanup_verified)
        self.assertEqual(failures, ["container backup cleanup failed: permission denied"])
        run.assert_called_once_with(
            ["docker", "exec", "postgres-test", "rm", "-f", "/tmp/restore.dump"],
            check=False,
        )

    def test_restore_error_redacts_keyword_dsn_passwords(self) -> None:
        verifier = importlib.import_module("scripts.verify_postgres_restore")

        for dsn, message in (
            (
                "host=db.example user=loopos password=secret dbname=postgres",
                "connection failed password=secret",
            ),
            (
                "host=db.example user=loopos password='secret value' dbname=postgres",
                "connection failed password='secret value'",
            ),
        ):
            with self.subTest(dsn=dsn):
                rendered = verifier._safe_error(RuntimeError(message), dsn)
                self.assertNotIn("secret", rendered)
                self.assertIn("[redacted]", rendered)


if __name__ == "__main__":
    unittest.main()
