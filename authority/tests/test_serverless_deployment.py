from __future__ import annotations

import builtins
import json
import os
import runpy
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def isolated_authority_entrypoint() -> Iterator[None]:
    """Avoid reusing an authority app whose lifespan already closed its store."""
    sys.modules.pop("loopos_authority.api", None)
    try:
        yield
    finally:
        sys.modules.pop("loopos_authority.api", None)


class ServerlessDeploymentContractTests(unittest.TestCase):
    def test_missing_runtime_dependency_keeps_serverless_api_fail_closed(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        with isolated_authority_entrypoint():
            sys.modules.pop("loopos_authority.identity", None)
            original_import = builtins.__import__

            def import_without_jwt(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "jwt":
                    raise ModuleNotFoundError("No module named 'jwt'")
                return original_import(name, globals, locals, fromlist, level)

            with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
                with patch("builtins.__import__", side_effect=import_without_jwt):
                    namespace = runpy.run_path(str(entrypoint))
                with TestClient(namespace["app"]) as client:
                    live = client.get("/api/health/live")
                    ready = client.get("/api/health/ready")
                    session = client.post("/api/v1/sessions", json={})

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(ready.json(), {"detail": "Authority initialization failed; inspect the deployment logs and restore the missing runtime dependency or configuration."})
        self.assertEqual(ready.headers["cache-control"], "no-store")
        self.assertEqual(ready.headers["x-loopos-readiness-code"], "authority_initialization_failed")
        self.assertEqual(session.status_code, 503)
        self.assertEqual(session.json(), {"detail": "Authority initialization failed; inspect the deployment logs and restore the missing runtime dependency or configuration."})
        self.assertEqual(session.headers["cache-control"], "no-store")
        self.assertEqual(session.headers["x-loopos-readiness-code"], "authority_initialization_failed")

    def test_vercel_entrypoint_serves_authority_under_api_prefix(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        self.assertTrue(entrypoint.is_file(), "Vercel requires api/index.py for the authority function.")

        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = {
                "LOOPOS_REPO_ROOT": str(REPO_ROOT),
                "LOOPOS_DATABASE_PATH": str(Path(temporary_directory) / "authority.db"),
                "LOOPOS_ALLOW_DEV_AUTH": "true",
                "LOOPOS_SESSION_HMAC_SECRET": "serverless-contract-test-secret-value",
            }
            with isolated_authority_entrypoint():
                with patch.dict(os.environ, environment, clear=False):
                    namespace = runpy.run_path(str(entrypoint))
                    with TestClient(namespace["app"]) as client:
                        response = client.get("/api/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "live"})

    def test_vercel_entrypoint_forwards_initialized_authority_routes(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = {
                "LOOPOS_REPO_ROOT": str(REPO_ROOT),
                "LOOPOS_DATABASE_PATH": str(Path(temporary_directory) / "authority.db"),
                "LOOPOS_ALLOW_DEV_AUTH": "true",
                "LOOPOS_SESSION_HMAC_SECRET": "serverless-route-test-secret-value",
            }
            with isolated_authority_entrypoint():
                with patch.dict(os.environ, environment, clear=False):
                    namespace = runpy.run_path(str(entrypoint))
                    with TestClient(namespace["app"]) as client:
                        response = client.post(
                            "/api/v1/dev/sessions",
                            json={
                                "tenant_id": "tenant-serverless",
                                "user_id": "operator",
                                "name": "Serverless Operator",
                                "role": "Operator",
                            },
                        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json().get("access_token"))

    def test_vercel_entrypoint_registers_prefixed_nested_routes(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = {
                "LOOPOS_REPO_ROOT": str(REPO_ROOT),
                "LOOPOS_DATABASE_PATH": str(Path(temporary_directory) / "authority.db"),
                "LOOPOS_ALLOW_DEV_AUTH": "true",
                "LOOPOS_SESSION_HMAC_SECRET": "serverless-route-map-test-secret-value",
            }
            with isolated_authority_entrypoint():
                with patch.dict(os.environ, environment, clear=False):
                    namespace = runpy.run_path(str(entrypoint))
                    paths = {route.path for route in namespace["app"].routes}
                    with TestClient(namespace["app"]):
                        pass

        self.assertIn("/api/health/live", paths)
        self.assertIn("/api/health/ready", paths)
        self.assertIn("/api/v1/sessions", paths)

    def test_invalid_vercel_configuration_returns_fail_closed_api_responses(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        with isolated_authority_entrypoint():
            with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
                namespace = runpy.run_path(str(entrypoint))
                with TestClient(namespace["app"]) as client:
                    live = client.get("/api/health/live")
                    ready = client.get("/api/health/ready")
                    session = client.post("/api/v1/dev/sessions", json={})
                    workspaces = client.get("/api/v1/workspaces")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(live.headers["cache-control"], "no-store")
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(ready.json(), {"detail": "Authority configuration is invalid; configure the required production environment variables and redeploy."})
        self.assertEqual(ready.headers["cache-control"], "no-store")
        self.assertEqual(ready.headers["x-loopos-readiness-code"], "configuration_invalid")
        self.assertEqual(session.status_code, 503)
        self.assertEqual(session.json(), {"detail": "Authority configuration is invalid; configure the required production environment variables and redeploy."})
        self.assertEqual(session.headers["cache-control"], "no-store")
        self.assertEqual(session.headers["x-loopos-readiness-code"], "configuration_invalid")
        self.assertEqual(workspaces.status_code, 503)
        self.assertEqual(workspaces.json(), {"detail": "Authority configuration is invalid; configure the required production environment variables and redeploy."})

    def test_unavailable_postgres_returns_fail_closed_api_responses(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        with isolated_authority_entrypoint():
            with patch.dict(
                os.environ,
                {
                    "VERCEL": "1",
                    "LOOPOS_SESSION_HMAC_SECRET": "serverless-postgres-test-secret-value",
                    "LOOPOS_STORAGE_BACKEND": "postgres",
                    "LOOPOS_POSTGRES_DSN": "postgresql://loopos-probe.invalid/loopos?sslmode=require",
                    "LOOPOS_RATE_LIMIT_REQUESTS": "120",
                    "LOOPOS_RATE_LIMIT_WINDOW_SECONDS": "60",
                },
                clear=True,
            ):
                with patch.object(
                    psycopg,
                    "connect",
                    side_effect=psycopg.errors.ConnectionTimeout("database unavailable"),
                ):
                    namespace = runpy.run_path(str(entrypoint))
                with TestClient(namespace["app"]) as client:
                    live = client.get("/api/health/live")
                    ready = client.get("/api/health/ready")
                    session = client.post("/api/v1/dev/sessions", json={})
                    workspaces = client.get("/api/v1/workspaces")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(live.headers["cache-control"], "no-store")
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(ready.json(), {"detail": "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."})
        self.assertEqual(ready.headers["cache-control"], "no-store")
        self.assertEqual(ready.headers["x-loopos-readiness-code"], "persistence_unavailable")
        self.assertEqual(session.status_code, 503)
        self.assertEqual(session.json(), {"detail": "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."})
        self.assertEqual(session.headers["cache-control"], "no-store")
        self.assertEqual(session.headers["x-loopos-readiness-code"], "persistence_unavailable")
        self.assertEqual(workspaces.status_code, 503)
        self.assertEqual(workspaces.json(), {"detail": "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."})

    def test_unavailable_sqlite_returns_fail_closed_api_responses(self) -> None:
        entrypoint = REPO_ROOT / "api" / "index.py"
        with isolated_authority_entrypoint():
            with tempfile.TemporaryDirectory() as temporary_directory:
                with patch.dict(
                    os.environ,
                    {
                        "VERCEL": "1",
                        "LOOPOS_ALLOW_DEV_AUTH": "false",
                        "LOOPOS_SESSION_HMAC_SECRET": "serverless-sqlite-test-secret-value",
                        "LOOPOS_RATE_LIMIT_REQUESTS": "120",
                        "LOOPOS_RATE_LIMIT_WINDOW_SECONDS": "60",
                        "LOOPOS_DATABASE_PATH": temporary_directory,
                    },
                    clear=True,
                ):
                    namespace = runpy.run_path(str(entrypoint))
                    with TestClient(namespace["app"]) as client:
                        live = client.get("/api/health/live")
                        ready = client.get("/api/health/ready")
                        session = client.post("/api/v1/dev/sessions", json={})
                        workspaces = client.get("/api/v1/workspaces")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(live.headers["cache-control"], "no-store")
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(ready.json(), {"detail": "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."})
        self.assertEqual(ready.headers["cache-control"], "no-store")
        self.assertEqual(ready.headers["x-loopos-readiness-code"], "persistence_unavailable")
        self.assertEqual(session.status_code, 503)
        self.assertEqual(session.json(), {"detail": "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."})
        self.assertEqual(session.headers["cache-control"], "no-store")
        self.assertEqual(session.headers["x-loopos-readiness-code"], "persistence_unavailable")
        self.assertEqual(workspaces.status_code, 503)
        self.assertEqual(workspaces.json(), {"detail": "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."})

    def test_spa_rewrite_does_not_capture_api_requests(self) -> None:
        configuration = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
        api_route = next(item for item in configuration["routes"] if item["dest"] == "/api/index.py")
        self.assertEqual(api_route["src"], "/api(?:/.*)?")
        spa_rewrite = next(item for item in configuration["rewrites"] if item["destination"] == "/index.html")

        self.assertIn("api(?:/|$)", spa_rewrite["source"])
        self.assertFalse(
            any(item.get("source") == "/api/:path*" for item in configuration["rewrites"]),
            "Vercel's native api/index.py routing must preserve the requested API suffix.",
        )

    def test_root_dependencies_include_authority_runtime(self) -> None:
        root_requirements = REPO_ROOT / "requirements.txt"
        self.assertTrue(root_requirements.is_file(), "Vercel installs Python dependencies from the project root.")
        self.assertEqual(
            root_requirements.read_text(encoding="utf-8"),
            (REPO_ROOT / "authority" / "requirements.txt").read_text(encoding="utf-8"),
        )

    def test_vercel_deployment_is_plan_portable_and_worker_schedule_is_external(self) -> None:
        configuration = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))

        self.assertNotIn("crons", configuration)
        authority_docs = (REPO_ROOT / "authority" / "README.md").read_text(encoding="utf-8")
        self.assertIn("external scheduler", authority_docs)
        self.assertIn("/api/v1/operations/jobs/drain", authority_docs)
        self.assertIn("LOOPOS_EXECUTION_WORKER_HEARTBEAT_MAX_AGE_SECONDS", authority_docs)

    def test_generated_graph_is_excluded_from_deployment_uploads(self) -> None:
        ignored = {
            line.strip().rstrip("/")
            for line in (REPO_ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("graphify-out", ignored)

    def test_production_build_runs_environment_preflight_before_vercel_data_shortcut(self) -> None:
        script = (REPO_ROOT / "ui" / "scripts" / "export-data-if-local.mjs").read_text(encoding="utf-8")

        self.assertIn('process.env.VERCEL_ENV?.trim().toLowerCase() === "production"', script)
        self.assertIn('"../scripts/verify_production_environment.py"', script)
        self.assertLess(
            script.index('"../scripts/verify_production_environment.py"'),
            script.index("if (process.env.VERCEL || process.env.LOOPOS_USE_CHECKED_IN_DATA"),
        )


if __name__ == "__main__":
    unittest.main()
