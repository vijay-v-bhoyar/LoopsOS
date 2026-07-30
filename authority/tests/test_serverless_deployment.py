from __future__ import annotations

import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]


class ServerlessDeploymentContractTests(unittest.TestCase):
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
            with patch.dict(os.environ, environment, clear=False):
                namespace = runpy.run_path(str(entrypoint))
                with TestClient(namespace["app"]) as client:
                    response = client.get("/api/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "live"})

    def test_spa_rewrite_does_not_capture_api_requests(self) -> None:
        configuration = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
        spa_rewrite = next(item for item in configuration["rewrites"] if item["destination"] == "/index.html")

        self.assertIn("api/", spa_rewrite["source"])

    def test_api_subpaths_are_forwarded_to_the_python_function(self) -> None:
        configuration = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))

        self.assertIn(
            {"source": "/api/:path*", "destination": "/api"},
            configuration["rewrites"],
        )

    def test_root_dependencies_include_authority_runtime(self) -> None:
        root_requirements = REPO_ROOT / "requirements.txt"
        self.assertTrue(root_requirements.is_file(), "Vercel installs Python dependencies from the project root.")
        self.assertEqual(
            root_requirements.read_text(encoding="utf-8"),
            (REPO_ROOT / "authority" / "requirements.txt").read_text(encoding="utf-8"),
        )

    def test_vercel_declares_the_durable_worker_cron(self) -> None:
        configuration = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))

        self.assertIn(
            {"path": "/api/v1/operations/jobs/drain", "schedule": "* * * * *"},
            configuration.get("crons", []),
        )


if __name__ == "__main__":
    unittest.main()
