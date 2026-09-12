from __future__ import annotations

import hashlib
import json
import unittest

from scripts.verify_production_handover import (
    HttpResult,
    REQUIRED_HANDOVER_INPUTS,
    _missing_configuration_report,
    verify_production_handover,
)


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
OPERATIONAL_VERIFIED_AT = "2026-07-30T12:00:00+00:00"
OPERATIONAL_BINDING_FINGERPRINT = "d" * 64
OPERATIONAL_CHECKS = [
    "retention_policy_approved",
    "retention_deletion_test_passed",
    "support_route_tested",
    "support_escalation_test_passed",
    "outbound_policy_enforced",
    "outbound_denial_test_passed",
]
OPERATIONAL_EVIDENCE = json.dumps(
    {
        "schema_version": 1,
        "generated_at": OPERATIONAL_VERIFIED_AT,
        "verified": True,
        "binding_fingerprint": OPERATIONAL_BINDING_FINGERPRINT,
        "checks": [{"name": name, "passed": True} for name in OPERATIONAL_CHECKS],
    },
    sort_keys=True,
).encode("utf-8")
OPERATIONAL_EVIDENCE_SHA256 = hashlib.sha256(OPERATIONAL_EVIDENCE).hexdigest()


class FakeHandoverClient:
    def __init__(
        self,
        *,
        worker_verified: bool = True,
        rate_limit_configured: bool = True,
        audit_delivery_fresh: bool = True,
        primary_role: str = "Executive",
        restore_evidence_sha256: str = RESTORE_EVIDENCE_SHA256,
        operational_evidence_sha256: str = OPERATIONAL_EVIDENCE_SHA256,
        configuration_contract_mode: str = "valid",
        configuration_backup_restore_url: str = "https://evidence.example.com/loopos/postgres-restore.json",
        audit_delivery_timestamp: object = "2026-07-30T12:00:00+00:00",
        worker_source: object = "external",
        worker_dispatch_observed_at: object = "2026-07-30T12:00:00+00:00",
        worker_dispatch_age_seconds: object = 1,
        worker_backlog: object = 0,
        worker_audit_backlog: object = 0,
        worker_execution_verified: bool = True,
        audit_tenant_id: object = "tenant-primary",
        restore_verified_at: object = RESTORE_VERIFIED_AT,
        operational_verified_at: object = OPERATIONAL_VERIFIED_AT,
        configuration_allowed_http_hosts: object = None,
        session_token_type: object = "bearer",
        session_expires_in: object = 900,
    ):
        self.worker_verified = worker_verified
        self.rate_limit_configured = rate_limit_configured
        self.audit_delivery_fresh = audit_delivery_fresh
        self.primary_role = primary_role
        self.restore_evidence_sha256 = restore_evidence_sha256
        self.operational_evidence_sha256 = operational_evidence_sha256
        self.configuration_contract_mode = configuration_contract_mode
        self.configuration_backup_restore_url = configuration_backup_restore_url
        self.audit_delivery_timestamp = audit_delivery_timestamp
        self.worker_source = worker_source
        self.worker_dispatch_observed_at = worker_dispatch_observed_at
        self.worker_dispatch_age_seconds = worker_dispatch_age_seconds
        self.worker_backlog = worker_backlog
        self.worker_audit_backlog = worker_audit_backlog
        self.worker_execution_verified = worker_execution_verified
        self.audit_tenant_id = audit_tenant_id
        self.restore_verified_at = restore_verified_at
        self.operational_verified_at = operational_verified_at
        self.configuration_allowed_http_hosts = configuration_allowed_http_hosts
        self.session_token_type = session_token_type
        self.session_expires_in = session_expires_in
        self.calls: list[tuple[str, str, dict[str, str], dict[str, object] | None]] = []
        self.session_count = 0
        self.marker_deleted = False
        self.worker_probe_run_id: str | None = None

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
                    "token_type": self.session_token_type,
                    "expires_in": self.session_expires_in,
                    "actor": {
                        "tenant_id": "tenant-primary" if primary else "tenant-secondary",
                        "user_id": "primary-user" if primary else "secondary-user",
                        "name": "Handover verifier",
                        "role": self.primary_role if primary else "Operator",
                    },
                },
            )
        if method == "PUT" and path.startswith("/v1/workspaces/handover-probe-"):
            if normalized_headers.get("authorization") == "Bearer secondary-session-token":
                return HttpResult(404, {"detail": "Workspace not found."})
            return HttpResult(201, {"revision": 1, "workspace_id": path.rsplit("/", 1)[-1]})
        if method == "GET" and path.startswith("/v1/workspaces/handover-probe-"):
            if self.marker_deleted or normalized_headers.get("authorization") == "Bearer secondary-session-token":
                return HttpResult(404, {"detail": "Workspace not found."})
            return HttpResult(200, {"revision": 1, "workspace_id": path.rsplit("/", 1)[-1]})
        if method == "DELETE" and path.startswith("/v1/workspaces/handover-probe-"):
            if normalized_headers.get("authorization") == "Bearer secondary-session-token":
                return HttpResult(404, {"detail": "Workspace not found."})
            self.marker_deleted = True
            return HttpResult(204, None)
        if method == "POST" and path == "/v1/runs":
            self.worker_probe_run_id = "handover-worker-run"
            return HttpResult(201, {"run_id": self.worker_probe_run_id})
        if method == "POST" and path == "/v1/runs/handover-worker-run/start":
            return HttpResult(202, {"run_id": self.worker_probe_run_id, "state": "QUEUED", "runner_status": "queued"})
        if path == "/v1/audit/verify":
            return HttpResult(
                200,
                {
                    "tenant_id": self.audit_tenant_id,
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
                    "processed": 1 if self.worker_execution_verified and self.worker_probe_run_id else 0,
                    "backlog": self.worker_backlog,
                    "dispatch": {
                        "verified": self.worker_verified,
                        "source": "external",
                        "observed_at": self.worker_dispatch_observed_at,
                        "age_seconds": self.worker_dispatch_age_seconds,
                        "detail": {"claimed_jobs": 1 if self.worker_execution_verified and self.worker_probe_run_id else 0},
                    },
                    "audit_backlog": self.worker_audit_backlog,
                },
            )
        if method == "GET" and path == "/v1/runs/handover-worker-run":
            return HttpResult(
                200,
                {
                    "run_id": self.worker_probe_run_id,
                    "state": "EFFECTIVENESS_PROVEN" if self.worker_execution_verified else "QUEUED",
                    "runner_status": "completed" if self.worker_execution_verified else "queued",
                },
            )
        if path == "/health/ready":
            readiness = {
                    "status": "ready",
                    "development_auth": False,
                    "rate_limit_configured": self.rate_limit_configured,
                    "production_identity": True,
                    "storage_backend": "postgres",
                    "audit_anchor_configured": True,
                    "audit_anchor_backlog": 0,
                    "audit_anchor_delivery_verified": True,
                    "audit_anchor_delivery_fresh": self.audit_delivery_fresh,
                    "audit_anchor_last_delivered_at": self.audit_delivery_timestamp,
                    "execution_job_backlog": 0,
                    "execution_worker_dispatch": {
                        "verified": self.worker_verified,
                        "source": self.worker_source,
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
                        "verified_at": self.restore_verified_at,
                    },
                    "operational_evidence": {
                        "url": "https://evidence.example.com/loopos/operational-controls.json",
                        "sha256": self.operational_evidence_sha256,
                        "verified_at": self.operational_verified_at,
                        "binding_fingerprint": OPERATIONAL_BINDING_FINGERPRINT,
                    },
                    "configuration_contract": {
                        "allowed_http_hosts": self.configuration_allowed_http_hosts or ["api.example.com"],
                        "outbound_policy_mode": "allowlist",
                        "retention_policy_url": "https://policy.example.com/loopos-retention",
                        "support_contact": "loopos-operations@example.com",
                        "backup_restore_evidence_url": self.configuration_backup_restore_url,
                    },
                }
            if self.configuration_contract_mode == "missing":
                readiness.pop("configuration_contract")
            elif self.configuration_contract_mode == "malformed":
                readiness["configuration_contract"].pop("support_contact")
            return HttpResult(200, readiness)
        if path == "/v1/workspaces":
            return HttpResult(200, [])
        return HttpResult(500, {"detail": f"Unexpected fake request: {method} {path}"})


class ProductionHandoverVerifierTests(unittest.TestCase):
    def test_missing_configuration_report_is_machine_readable_without_secrets(self) -> None:
        report = _missing_configuration_report(
            "https://authority.example/api",
            [
                "LOOPOS_HANDOVER_BASE_URL",
                "LOOPOS_HANDOVER_PRIMARY_IDENTITY_ASSERTION",
                "LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE (unreadable or oversized)",
            ],
        )

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertEqual(len(report["required_inputs"]), len(REQUIRED_HANDOVER_INPUTS))
        self.assertEqual(report["missing_inputs"][0], {
            "name": "LOOPOS_HANDOVER_BASE_URL",
            "status": "missing",
            "sensitive": False,
        })
        self.assertTrue(report["missing_inputs"][1]["sensitive"])
        self.assertEqual(report["missing_inputs"][2]["status"], "invalid")
        rendered = json.dumps(report)
        self.assertNotIn("assertion-secret", rendered)
        self.assertIn("Rerun the handover verifier", report["next_actions"][1])

    def test_rejects_invalid_port_before_network_proof(self) -> None:
        client = FakeHandoverClient()
        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com:bad/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
        )

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertEqual([check["name"] for check in report["checks"]], ["secure_transport"])
        self.assertEqual(client.calls, [])

    def test_rejects_targets_not_using_the_api_route_before_network_proof(self) -> None:
        for target in ("https://loopos.example.com", "https://loopos.example.com/wrong-route"):
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
                self.assertEqual([check["name"] for check in report["checks"]], ["secure_transport"])
                self.assertEqual(client.calls, [])

    def test_rejects_non_global_targets_before_network_proof(self) -> None:
        for target in (
            "https://127.0.0.1/api",
            "https://100.64.0.1/api",
            "https://192.0.2.1/api",
        ):
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
                self.assertEqual([check["name"] for check in report["checks"]], ["secure_transport"])
                self.assertEqual(client.calls, [])

    def test_handover_probe_covers_cross_tenant_mutation_isolation(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        check_names = {check["name"] for check in report["checks"]}
        self.assertIn("tenant_isolation_write", check_names)
        self.assertIn("tenant_isolation_delete", check_names)

    def test_requires_expected_tenants_before_mutation_proof(self) -> None:
        client = FakeHandoverClient()

        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        tenant_check = next(check for check in report["checks"] if check["name"] == "tenant_identity")
        self.assertFalse(tenant_check["passed"])
        self.assertIn("expected tenant IDs were not explicitly declared", tenant_check["detail"])
        self.assertFalse(any(method == "PUT" for method, _path, _headers, _body in client.calls))

    def test_cleans_a_created_marker_when_revision_contract_is_malformed(self) -> None:
        class MissingRevisionClient(FakeHandoverClient):
            def request(self, method, path, **kwargs):  # noqa: ANN001
                result = super().request(method, path, **kwargs)
                if method == "PUT" and path.startswith("/v1/workspaces/handover-probe-"):
                    return HttpResult(201, {"workspace_id": path.rsplit("/", 1)[-1]})
                if (
                    method == "GET"
                    and path.startswith("/v1/workspaces/handover-probe-")
                    and (kwargs.get("headers") or {}).get("authorization") == "Bearer primary-session-token"
                ):
                    return HttpResult(200, {"workspace_id": path.rsplit("/", 1)[-1]})
                return result

        client = MissingRevisionClient()
        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(client.marker_deleted)
        self.assertTrue(
            any(
                method == "DELETE"
                and path.startswith("/v1/workspaces/handover-probe-")
                and headers.get("authorization") == "Bearer primary-session-token"
                and headers.get("if-match") == '"1"'
                for method, path, headers, _body in client.calls
            )
        )
        for name in ("tenant_isolation", "tenant_isolation_write", "tenant_isolation_delete"):
            check = next(check for check in report["checks"] if check["name"] == name)
            self.assertFalse(check["passed"])

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
            operational_evidence=OPERATIONAL_EVIDENCE,
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
        self.assertTrue({"probe_absence", "audit_chain", "deletion_audit_event", "tenant_isolation_write", "tenant_isolation_delete"}.issubset(passed))
        serialized = json.dumps(report)
        self.assertNotIn("primary-secret-assertion", serialized)
        self.assertNotIn("secondary-secret-assertion", serialized)
        self.assertNotIn("worker-secret-token", serialized)
        self.assertNotIn("primary-session-token", serialized)
        self.assertEqual(report["backup_restore_evidence_sha256"], RESTORE_EVIDENCE_SHA256)
        self.assertEqual(report["operational_evidence_sha256"], OPERATIONAL_EVIDENCE_SHA256)

    def test_fails_closed_when_audit_verification_is_for_another_tenant(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(audit_tenant_id="tenant-secondary"),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        audit_check = next(check for check in report["checks"] if check["name"] == "audit_chain")
        self.assertFalse(audit_check["passed"])
        self.assertIn("tenant", audit_check["detail"])

    def test_fails_closed_when_worker_drain_leaves_backlog(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_backlog=1, worker_audit_backlog=1),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        worker_check = next(check for check in report["checks"] if check["name"] == "worker_dispatch")
        self.assertFalse(worker_check["passed"])
        self.assertIn("backlog", worker_check["detail"])

    def test_fails_closed_when_worker_runtime_proof_is_missing(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_verified=False),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("worker_dispatch", failed)
        self.assertIn("production_readiness", failed)

    def test_fails_closed_when_worker_cannot_complete_a_queued_execution(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_execution_verified=False),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        worker_check = next(check for check in report["checks"] if check["name"] == "worker_execution")
        self.assertFalse(worker_check["passed"])

    def test_handover_verifies_a_completed_queued_execution(self) -> None:
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
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "GO")
        worker_check = next(check for check in report["checks"] if check["name"] == "worker_execution")
        self.assertTrue(worker_check["passed"])
        self.assertIn(("POST", "/v1/runs"), [(method, path) for method, path, _headers, _body in client.calls])

    def test_handover_does_not_enqueue_a_probe_without_worker_authority(self) -> None:
        client = FakeHandoverClient()
        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertNotIn(("POST", "/v1/runs"), [(method, path) for method, path, _headers, _body in client.calls])
        worker_check = next(check for check in report["checks"] if check["name"] == "worker_execution_queued")
        self.assertFalse(worker_check["passed"])

    def test_fails_closed_when_identity_session_contract_is_malformed(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(session_token_type="basic", session_expires_in=0),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        primary_check = next(check for check in report["checks"] if check["name"] == "primary_identity")
        secondary_check = next(check for check in report["checks"] if check["name"] == "secondary_identity")
        self.assertFalse(primary_check["passed"])
        self.assertFalse(secondary_check["passed"])
        self.assertIn("token_type", primary_check["detail"])
        self.assertIn("expires_in", primary_check["detail"])

    def test_fails_closed_when_identity_session_lifetime_exceeds_authority_contract(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(session_expires_in=901),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {
            check["name"]
            for check in report["checks"]
            if not check["passed"]
        }
        self.assertIn("primary_identity", failed)
        self.assertIn("secondary_identity", failed)
        self.assertIn("expires_in", next(check["detail"] for check in report["checks"] if check["name"] == "primary_identity"))

    def test_fails_closed_when_live_worker_dispatch_shape_is_unverifiable(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_dispatch_age_seconds=float("nan")),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        worker_check = next(check for check in report["checks"] if check["name"] == "worker_dispatch")
        self.assertFalse(worker_check["passed"])
        self.assertIn("execution_worker_dispatch.age_seconds", worker_check["detail"])

    def test_fails_closed_when_evidence_descriptor_timestamp_is_naive(self) -> None:
        cases = [
            ("restore", {"restore_verified_at": "2026-07-30T12:00:00"}, "backup_restore_evidence"),
            ("operational", {"operational_verified_at": "2026-07-30T12:00:00"}, "operational_evidence"),
        ]
        for label, overrides, check_name in cases:
            with self.subTest(label=label):
                report = verify_production_handover(
                    FakeHandoverClient(**overrides),
                    base_url="https://loopos.example.com/api",
                    primary_identity_assertion="primary-secret-assertion",
                    secondary_identity_assertion="secondary-secret-assertion",
                    worker_token="worker-secret-token",
                    backup_restore_evidence=RESTORE_EVIDENCE,
                    operational_evidence=OPERATIONAL_EVIDENCE,
                )

                self.assertEqual(report["verdict"], "NO_GO")
                evidence_check = next(check for check in report["checks"] if check["name"] == check_name)
                self.assertFalse(evidence_check["passed"])
                self.assertIn("not timezone-qualified", evidence_check["detail"])

    def test_fails_closed_when_configuration_contract_allows_private_hosts(self) -> None:
        for host in ("127.0.0.1", "100.64.0.1"):
            with self.subTest(host=host):
                report = verify_production_handover(
                    FakeHandoverClient(configuration_allowed_http_hosts=[host]),
                    base_url="https://loopos.example.com/api",
                    primary_identity_assertion="primary-secret-assertion",
                    secondary_identity_assertion="secondary-secret-assertion",
                    worker_token="worker-secret-token",
                    backup_restore_evidence=RESTORE_EVIDENCE,
                    operational_evidence=OPERATIONAL_EVIDENCE,
                )

                self.assertEqual(report["verdict"], "NO_GO")
                readiness_check = next(check for check in report["checks"] if check["name"] == "production_readiness")
                self.assertFalse(readiness_check["passed"])
                self.assertIn("configuration_contract.allowed_http_hosts", readiness_check["detail"])

    def test_fails_closed_when_configuration_contract_uses_non_global_evidence_hosts(self) -> None:
        for evidence_url in ("https://127.0.0.1/restore.json", "https://100.64.0.1/restore.json"):
            with self.subTest(evidence_url=evidence_url):
                report = verify_production_handover(
                    FakeHandoverClient(configuration_backup_restore_url=evidence_url),
                    base_url="https://loopos.example.com/api",
                    primary_identity_assertion="primary-secret-assertion",
                    secondary_identity_assertion="secondary-secret-assertion",
                    worker_token="worker-secret-token",
                    backup_restore_evidence=RESTORE_EVIDENCE,
                    operational_evidence=OPERATIONAL_EVIDENCE,
                )

                self.assertEqual(report["verdict"], "NO_GO")
                readiness_check = next(check for check in report["checks"] if check["name"] == "production_readiness")
                self.assertFalse(readiness_check["passed"])
                self.assertIn("configuration_contract.backup_restore_evidence_url", readiness_check["detail"])

    def test_fails_closed_when_readiness_configuration_contract_is_missing_or_malformed(self) -> None:
        for mode in ("missing", "malformed"):
            with self.subTest(mode=mode):
                report = verify_production_handover(
                    FakeHandoverClient(configuration_contract_mode=mode),
                    base_url="https://loopos.example.com/api",
                    primary_identity_assertion="primary-secret-assertion",
                    secondary_identity_assertion="secondary-secret-assertion",
                    worker_token="worker-secret-token",
                    backup_restore_evidence=RESTORE_EVIDENCE,
                    operational_evidence=OPERATIONAL_EVIDENCE,
                )

                self.assertEqual(report["verdict"], "NO_GO")
                readiness_check = next(
                    check for check in report["checks"] if check["name"] == "production_readiness"
                )
                self.assertFalse(readiness_check["passed"])
                self.assertIn("configuration_contract", readiness_check["detail"])

    def test_fails_closed_when_restore_evidence_urls_disagree(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(
                configuration_backup_restore_url="https://evidence.example.com/loopos/different-restore.json"
            ),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        restore_check = next(check for check in report["checks"] if check["name"] == "backup_restore_evidence")
        self.assertFalse(restore_check["passed"])
        self.assertIn("configuration contract restore evidence URL mismatch", restore_check["detail"])

    def test_fails_closed_when_audit_delivery_is_stale(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(audit_delivery_fresh=False),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("production_readiness", failed)

    def test_fails_closed_when_audit_delivery_timestamp_is_missing(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(audit_delivery_timestamp=None),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        readiness_check = next(
            check for check in report["checks"] if check["name"] == "production_readiness"
        )
        self.assertFalse(readiness_check["passed"])
        self.assertIn("audit_anchor_last_delivered_at", readiness_check["detail"])

    def test_fails_closed_when_worker_heartbeat_shape_is_unverifiable(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(worker_source="unknown"),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        readiness_check = next(
            check for check in report["checks"] if check["name"] == "production_readiness"
        )
        self.assertFalse(readiness_check["passed"])
        self.assertIn("execution_worker_dispatch.source", readiness_check["detail"])

    def test_fails_closed_when_rate_limit_proof_is_missing(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(rate_limit_configured=False),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            expected_primary_tenant="tenant-primary",
            expected_secondary_tenant="tenant-secondary",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        readiness_check = next(
            check for check in report["checks"] if check["name"] == "production_readiness"
        )
        self.assertFalse(readiness_check["passed"])
        self.assertIn("rate_limit_configured", readiness_check["detail"])

    def test_fails_closed_without_two_identity_assertions(self) -> None:
        client = FakeHandoverClient()
        report = verify_production_handover(
            client,
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("secondary_identity", failed)
        self.assertIn("tenant_isolation", failed)

    def test_fails_closed_without_executive_primary_identity(self) -> None:
        report = verify_production_handover(
            FakeHandoverClient(primary_role="Operator"),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("primary_identity", failed)
        self.assertIn("workspace_write", failed)

    def test_never_transmits_assertions_to_an_insecure_target(self) -> None:
        client = FakeHandoverClient()

        report = verify_production_handover(
            client,
            base_url="http://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertEqual(client.calls, [])

    def test_rejects_targets_with_embedded_credentials_or_query_secrets(self) -> None:
        for target in [
            "https://user:password@loopos.example.com/api",
            "https://loopos.example.com/api?token=secret",
            "https://loopos.example.com\\\\evil.example/api",
            "https://internal/api",
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
                    operational_evidence=OPERATIONAL_EVIDENCE,
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
            operational_evidence=OPERATIONAL_EVIDENCE,
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
            operational_evidence=OPERATIONAL_EVIDENCE,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        restore_check = next(check for check in report["checks"] if check["name"] == "backup_restore_evidence")
        self.assertFalse(restore_check["passed"])
        self.assertIn("required_checks", restore_check["detail"])

    def test_fails_closed_when_hashed_operational_evidence_omits_a_required_control(self) -> None:
        evidence = json.loads(OPERATIONAL_EVIDENCE)
        evidence["checks"] = [
            check for check in evidence["checks"] if check["name"] != "outbound_denial_test_passed"
        ]
        evidence_bytes = json.dumps(evidence, sort_keys=True).encode("utf-8")
        report = verify_production_handover(
            FakeHandoverClient(
                operational_evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest()
            ),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=evidence_bytes,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        operational_check = next(
            check for check in report["checks"] if check["name"] == "operational_evidence"
        )
        self.assertFalse(operational_check["passed"])
        self.assertIn("required_checks", operational_check["detail"])

    def test_fails_closed_when_hashed_operational_evidence_contains_an_unapproved_control(self) -> None:
        evidence = json.loads(OPERATIONAL_EVIDENCE)
        evidence["checks"].append({"name": "unapproved_control", "passed": True})
        evidence_bytes = json.dumps(evidence, sort_keys=True).encode("utf-8")
        report = verify_production_handover(
            FakeHandoverClient(
                operational_evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest()
            ),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=evidence_bytes,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        operational_check = next(
            check for check in report["checks"] if check["name"] == "operational_evidence"
        )
        self.assertFalse(operational_check["passed"])
        self.assertIn("unexpected_checks", operational_check["detail"])

    def test_fails_closed_when_operational_evidence_targets_different_bindings(self) -> None:
        evidence = json.loads(OPERATIONAL_EVIDENCE)
        evidence["binding_fingerprint"] = "c" * 64
        evidence_bytes = json.dumps(evidence, sort_keys=True).encode("utf-8")
        report = verify_production_handover(
            FakeHandoverClient(
                operational_evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest()
            ),
            base_url="https://loopos.example.com/api",
            primary_identity_assertion="primary-secret-assertion",
            secondary_identity_assertion="secondary-secret-assertion",
            worker_token="worker-secret-token",
            backup_restore_evidence=RESTORE_EVIDENCE,
            operational_evidence=evidence_bytes,
        )

        self.assertEqual(report["verdict"], "NO_GO")
        operational_check = next(
            check for check in report["checks"] if check["name"] == "operational_evidence"
        )
        self.assertFalse(operational_check["passed"])
        self.assertIn("binding_fingerprint", operational_check["detail"])
