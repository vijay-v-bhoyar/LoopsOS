from __future__ import annotations

import hashlib
import json
import unittest

from scripts.verify_production_handover import HttpResult, verify_production_handover


RESTORE_VERIFIED_AT = "2026-07-30T12:00:00+00:00"
RESTORE_CHECKS = [
    "backup_archive_created",
    "schema_tables_match",
    "row_counts_match",
    "runs_match",
    "audit_events_match",
    "row_level_security_restored",
    "audit_triggers_restored",
    "audit_mutation_denied",
]
RESTORE_TABLES = [
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
]
RESTORE_COUNTS = {
    table: 23 if table in {"audit_events", "audit_anchor_outbox"} else 1 if table == "runs" else 0
    for table in RESTORE_TABLES
}
RESTORE_EVIDENCE = json.dumps(
    {
        "schema_version": 1,
        "generated_at": RESTORE_VERIFIED_AT,
        "verified": True,
        "cleanup_verified": True,
        "backup_sha256": "b" * 64,
        "checks": [{"name": name, "passed": True} for name in RESTORE_CHECKS],
        "source_row_counts": RESTORE_COUNTS,
        "restored_row_counts": RESTORE_COUNTS,
        "container_image": f"postgres:17.10-alpine3.24@sha256:{'a' * 64}",
        "container_image_id": f"sha256:{'c' * 64}",
    },
    sort_keys=True,
).encode("utf-8")
RESTORE_EVIDENCE_SHA256 = hashlib.sha256(RESTORE_EVIDENCE).hexdigest()


class FakeHandoverClient:
    def __init__(self, *, worker_verified: bool = True, restore_evidence_sha256: str = RESTORE_EVIDENCE_SHA256):
        self.worker_verified = worker_verified
        self.restore_evidence_sha256 = restore_evidence_sha256
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
        if path == "/v1/audit/verify":
            return HttpResult(
                200,
                {
                    "tenant_id": "tenant-primary",
                    "valid": True,
                    "event_count": 501,
                    "first_invalid_sequence": None,
                },
            )
        if path == "/v1/events?after=0&limit=500":
            return HttpResult(
                200,
                [
                    {
                        "sequence": sequence,
                        "event_type": "WORKSPACE_UPDATED",
                        "payload": {"workspace_id": f"historical-{sequence}", "revision": 1},
                    }
                    for sequence in range(1, 501)
                ],
            )
        if path == "/v1/events?after=500&limit=500":
            marker_path = next(
                call_path
                for call_method, call_path, _headers, _body in self.calls
                if call_method == "PUT" and call_path.startswith("/v1/workspaces/handover-probe-")
            )
            return HttpResult(
                200,
                [
                    {
                        "sequence": 501,
                        "event_type": "WORKSPACE_DELETED",
                        "payload": {"workspace_id": marker_path.rsplit("/", 1)[-1], "revision": 1},
                    }
                ],
            )
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
                    "backup_restore_evidence": {
                        "url": "https://evidence.example.com/loopos/postgres-restore.json",
                        "sha256": self.restore_evidence_sha256,
                        "verified_at": RESTORE_VERIFIED_AT,
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
            backup_restore_evidence=RESTORE_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "GO")
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        paths = [(method, path) for method, path, _headers, _body in client.calls]
        marker_path = next(path for method, path in paths if method == "PUT")
        self.assertIn(("GET", marker_path), paths)
        self.assertIn(("DELETE", marker_path), paths)
        self.assertLess(paths.index(("GET", marker_path)), paths.index(("DELETE", marker_path)))
        delete_index = paths.index(("DELETE", marker_path))
        self.assertTrue(any(index > delete_index and call == ("GET", marker_path) for index, call in enumerate(paths)))
        self.assertIn(("GET", "/v1/audit/verify"), paths)
        self.assertIn(("GET", "/v1/events?after=0&limit=500"), paths)
        self.assertIn(("GET", "/v1/events?after=500&limit=500"), paths)
        passed = {check["name"] for check in report["checks"] if check["passed"]}
        self.assertTrue({"probe_absence", "audit_chain", "deletion_audit_event"}.issubset(passed))
        serialized = json.dumps(report)
        self.assertNotIn("primary-secret-assertion", serialized)
        self.assertNotIn("secondary-secret-assertion", serialized)
        self.assertNotIn("worker-secret-token", serialized)
        self.assertNotIn("primary-session-token", serialized)
        self.assertEqual(report["backup_restore_evidence_sha256"], RESTORE_EVIDENCE_SHA256)

    def test_fails_closed_when_worker_runtime_proof_is_missing(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_verified=False),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
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
            backup_restore_evidence=RESTORE_EVIDENCE,
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
            backup_restore_evidence=RESTORE_EVIDENCE,
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
                    backup_restore_evidence=RESTORE_EVIDENCE,
                )

                self.assertEqual(report["verdict"], "NO_GO")
                self.assertEqual(client.calls, [])
                serialized = json.dumps(report)
                self.assertNotIn("password", serialized)
                self.assertNotIn("token=secret", serialized)

    def test_fails_closed_when_restore_evidence_bytes_are_modified(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE + b"\n",
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("backup_restore_evidence", failed)

    def test_fails_closed_when_hashed_restore_evidence_omits_a_required_control(self) -> None:
        evidence = json.loads(RESTORE_EVIDENCE)
        evidence["checks"] = [
            check for check in evidence["checks"] if check["name"] != "audit_mutation_denied"
        ]
        evidence_bytes = json.dumps(evidence, sort_keys=True).encode("utf-8")
        report = verify_production_handover(
            FakeHandoverClient(restore_evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest()),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=evidence_bytes,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        restore_check = next(check for check in report["checks"] if check["name"] == "backup_restore_evidence")
        self.assertFalse(restore_check["passed"])
        self.assertIn("required_checks", restore_check["detail"])
