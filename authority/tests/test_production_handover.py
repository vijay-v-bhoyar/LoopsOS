from __future__ import annotations

import json
import unittest

from scripts.verify_production_handover import HttpResult, verify_production_handover


class FakeHandoverClient:
    def __init__(self, *, worker_verified: bool = True):
        self.worker_verified = worker_verified
        self.calls: list[tuple[str, str, dict[str, str], dict[str, object] | None]] = []
        self.session_count = 0

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
    ) -> HttpResult:
        normalized_headers = headers or {}
        self.calls.append((method, path, normalized_headers, body))
        if path == "/health/live":
            return HttpResult(200, {"status": "live"})
        if path == "/v1/sessions":
            self.session_count += 1
            primary = self.session_count == 1
            return HttpResult(
                200,
                {
                    "access_token": "primary-session-token" if primary else "secondary-session-token",
                    "actor": {
                        "tenant_id": "tenant-primary" if primary else "tenant-secondary",
                        "user_id": "primary-user" if primary else "secondary-user",
                        "name": "Handover verifier",
                        "role": "Executive" if primary else "Auditor",
                    },
                },
            )
        if method == "PUT" and path.startswith("/v1/workspaces/handover-probe-"):
            return HttpResult(201, {"revision": 1, "workspace_id": path.rsplit("/", 1)[-1]})
        if method == "GET" and path.startswith("/v1/workspaces/handover-probe-"):
            return HttpResult(404, {"detail": "Workspace not found."})
        if method == "DELETE" and path.startswith("/v1/workspaces/handover-probe-"):
            return HttpResult(204, None)
        if path == "/v1/operations/jobs/drain":
            return HttpResult(
                200,
                {
                    "processed": 0,
                    "backlog": 0,
                    "dispatch": {
                        "verified": self.worker_verified,
                        "source": "external",
                        "observed_at": "2026-07-30T12:00:00+00:00",
                        "age_seconds": 1,
                        "detail": {"claimed_jobs": 0},
                    },
                    "audit_backlog": 0,
                },
            )
        if path == "/health/ready":
            return HttpResult(
                200,
                {
                    "status": "ready",
                    "development_auth": False,
                    "production_identity": True,
                    "storage_backend": "postgres",
                    "audit_anchor_configured": True,
                    "audit_anchor_backlog": 0,
                    "audit_anchor_delivery_verified": True,
                    "execution_job_backlog": 0,
                    "execution_worker_dispatch": {
                        "verified": self.worker_verified,
                        "source": "external",
                        "observed_at": "2026-07-30T12:00:00+00:00",
                        "age_seconds": 1,
                        "detail": {"claimed_jobs": 0},
                    },
                    "operational_bindings": {
                        "retention_verified": True,
                        "support_verified": True,
                        "outbound_policy_verified": True,
                        "backup_restore_verified": True,
                        "worker_dispatch_verified": self.worker_verified,
                    },
                },
            )
        if path == "/v1/workspaces":
            return HttpResult(200, [])
        return HttpResult(500, {"detail": f"Unexpected fake request: {method} {path}"})


class ProductionHandoverVerifierTests(unittest.TestCase):
    def test_passes_only_after_two_tenant_isolation_cleanup_and_runtime_proof(self) -> None:
        client = FakeHandoverClient()

        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
        )

        self.assertEqual(report["verdict"], "GO")
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        paths = [(method, path) for method, path, _headers, _body in client.calls]
        marker_path = next(path for method, path in paths if method == "PUT")
        self.assertIn(("GET", marker_path), paths)
        self.assertIn(("DELETE", marker_path), paths)
        self.assertLess(paths.index(("GET", marker_path)), paths.index(("DELETE", marker_path)))
        serialized = json.dumps(report)
        self.assertNotIn("primary-secret-assertion", serialized)
        self.assertNotIn("secondary-secret-assertion", serialized)
        self.assertNotIn("worker-secret-token", serialized)
        self.assertNotIn("primary-session-token", serialized)

    def test_fails_closed_when_worker_runtime_proof_is_missing(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_verified=False),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("worker_dispatch", failed)
        self.assertIn("production_readiness", failed)

    def test_fails_closed_without_two_identity_assertions(self) -> None:
        client = FakeHandoverClient()
        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="",
            worker_token="worker-secret-token",
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("secondary_identity", failed)
        self.assertIn("tenant_isolation", failed)

    def test_never_transmits_assertions_to_an_insecure_target(self) -> None:
        client = FakeHandoverClient()

        report = verify_production_handover(
            client,
            base_url="http://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
        )

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertEqual(client.calls, [])

    def test_rejects_targets_with_embedded_credentials_or_query_secrets(self) -> None:
        for target in [
            "https://user:password@loopos.example.com/api",
            "https://loopos.example.com/api?token=secret",
        ]:
            with self.subTest(target=target):
                client = FakeHandoverClient()
                report = verify_production_handover(
                    client,
                    base_url=target,
                    primary_identity_assertion="primary-secret-assertion",
                    secondary_identity_assertion="secondary-secret-assertion",
                    worker_token="worker-secret-token",
                )

                self.assertEqual(report["verdict"], "NO_GO")
                self.assertEqual(client.calls, [])
                serialized = json.dumps(report)
                self.assertNotIn("password", serialized)
                self.assertNotIn("token=secret", serialized)
