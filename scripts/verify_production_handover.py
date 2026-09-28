from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_RESPONSE_BYTES = 1_000_000
MAX_RESTORE_EVIDENCE_BYTES = 5_000_000
MAX_OPERATIONAL_EVIDENCE_BYTES = 1_000_000
MAX_ENTERPRISE_SESSION_SECONDS = 900
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SHA256_REFERENCE_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PINNED_IMAGE_PATTERN = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
REQUIRED_RESTORE_CHECKS = {
    "backup_archive_created",
    "schema_tables_match",
    "row_counts_match",
    "runs_match",
    "audit_events_match",
    "row_level_security_restored",
    "audit_triggers_restored",
    "audit_mutation_denied",
}
REQUIRED_RESTORE_TABLES = {
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
}
REQUIRED_OPERATIONAL_CHECKS = {
    "retention_policy_approved",
    "retention_deletion_test_passed",
    "support_route_tested",
    "support_escalation_test_passed",
    "outbound_policy_enforced",
    "outbound_denial_test_passed",
}
REQUIRED_CONFIGURATION_CONTRACT_FIELDS = {
    "allowed_http_hosts",
    "outbound_policy_mode",
    "retention_policy_url",
    "support_contact",
    "backup_restore_evidence_url",
}
REQUIRED_HANDOVER_INPUTS = (
    ("LOOPOS_HANDOVER_BASE_URL", "absolute HTTPS /api authority origin", False),
    ("LOOPOS_HANDOVER_PRIMARY_IDENTITY_ASSERTION", "primary organization identity assertion", True),
    ("LOOPOS_HANDOVER_SECONDARY_IDENTITY_ASSERTION", "secondary organization identity assertion", True),
    ("LOOPOS_HANDOVER_EXPECTED_PRIMARY_TENANT", "expected primary tenant identifier", False),
    ("LOOPOS_HANDOVER_EXPECTED_SECONDARY_TENANT", "expected secondary tenant identifier", False),
    ("LOOPOS_HANDOVER_WORKER_TOKEN", "protected worker dispatch token", True),
    ("LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE", "fresh restore evidence JSON file", False),
    ("LOOPOS_HANDOVER_OPERATIONAL_EVIDENCE_FILE", "fresh operational evidence JSON file", False),
)


@dataclass(frozen=True)
class HttpResult:
    status: int
    payload: Any


class HandoverClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
    ) -> HttpResult:
        ...


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class UrlJsonClient:
    def __init__(self, base_url: str, timeout_seconds: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.opener = build_opener(_RejectRedirects())

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
    ) -> HttpResult:
        encoded_body = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        request_headers = {"accept": "application/json", **(headers or {})}
        if encoded_body is not None:
            request_headers["content-type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=encoded_body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                return HttpResult(response.status, _read_payload(response))
        except HTTPError as error:
            return HttpResult(error.code, _read_payload(error))
        except URLError as error:
            raise RuntimeError(f"Authority request failed: {error.reason}") from error


def _read_payload(response) -> Any:  # noqa: ANN001
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Authority response exceeded the handover verifier size limit.")
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Authority response exceeded the handover verifier size limit.")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("Authority returned a non-JSON response.") from error


def _safe_urlparse(value: str):
    try:
        parsed = urlparse(value)
        parsed.port
    except ValueError:
        return None
    return parsed


def _safe_request(
    client: HandoverClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
) -> HttpResult:
    try:
        return client.request(method, path, headers=headers, body=body)
    except Exception as error:
        return HttpResult(0, {"error": error.__class__.__name__})


def _session(
    client: HandoverClient,
    assertion: str,
) -> tuple[HttpResult, str | None, dict[str, Any]]:
    if not assertion:
        return HttpResult(0, {"detail": "Identity assertion is missing."}), None, {}
    response = _safe_request(
        client,
        "POST",
        "/v1/sessions",
        headers={"x-loopos-identity-token": assertion},
    )
    payload = response.payload if isinstance(response.payload, dict) else {}
    token = payload.get("access_token")
    actor = payload.get("actor")
    return (
        response,
        token if isinstance(token, str) and token else None,
        actor if isinstance(actor, dict) else {},
    )


def _session_contract_failures(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["session response is not an object"]

    failures: list[str] = []
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        failures.append("access_token")
    if payload.get("token_type") != "bearer":
        failures.append("token_type")
    expires_in = payload.get("expires_in")
    if (
        not isinstance(expires_in, int)
        or isinstance(expires_in, bool)
        or expires_in <= 0
        or expires_in > MAX_ENTERPRISE_SESSION_SECONDS
    ):
        failures.append("expires_in")

    actor = payload.get("actor")
    if not isinstance(actor, dict):
        failures.append("actor")
        return failures
    for field in ("tenant_id", "user_id", "name"):
        value = actor.get(field)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"actor.{field}")
    if actor.get("role") not in {"Executive", "Approver", "Operator", "Auditor"}:
        failures.append("actor.role")
    email = actor.get("email")
    if email is not None and (not isinstance(email, str) or not email.strip()):
        failures.append("actor.email")
    return failures


def _workspace_document(workspace_id: str, owner_user_id: str) -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "workspace_id": workspace_id,
        "name": "Production handover isolation probe",
        "created_at": timestamp,
        "updated_at": timestamp,
        "owner_user_id": owner_user_id,
        "use_case": {
            "title": "Production handover isolation probe",
            "description": "Reversible marker used to verify tenant isolation during handover.",
        },
        "selected_loop_ids": [],
        "action_plan_markdown": "",
        "owner_evidence_edits": [],
        "approvals": [],
        "execution_records": [],
        "initiatives": [],
        "question_suggestions": [],
        "input_sources": [],
    }


def _worker_probe_request(workspace_id: str) -> dict[str, object]:
    """Build a bounded, non-external-effect run for the live worker probe."""
    action_key = f"handover-worker-{uuid.uuid4()}"
    return {
        "workspace_id": workspace_id,
        "loop_id": "loop-001-product-discovery-loop",
        "title": "Production handover worker probe",
        "trigger": "A production handover verifier requested a reversible worker probe.",
        "requested_risk_tier": "R1",
        "plan": {
            "evidence": [{
                "evidence_id": "handover-worker-probe",
                "kind": "workspace_snapshot",
                "source_ref": f"workspace:{workspace_id}",
                "content": {"purpose": "worker-dispatch-verification"},
            }],
            "action": {
                "tool": "record_action",
                "idempotency_key": action_key,
                "external_effect": False,
                "arguments": {
                    "operation": "handover_worker_probe",
                    "summary": "Verify the deployed durable execution worker.",
                    "outputs": ["worker-dispatch-verified"],
                },
            },
            "validation_probes": [{
                "probe_id": "worker-validation-status",
                "kind": "json_equals",
                "path": "status",
                "expected": "applied",
            }],
            "effectiveness_probes": [{
                "probe_id": "worker-effectiveness-status",
                "kind": "json_equals",
                "path": "status",
                "expected": "applied",
            }],
            "max_attempts": 1,
        },
    }


def _production_host_is_safe(host: Any) -> bool:
    if not isinstance(host, str) or not host or host != host.strip() or host != host.lower() or len(host) > 253:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        # A single-label name can resolve through private or split-horizon DNS;
        # it is not a verifiable global handover target.
        return len(labels) >= 2 and all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
        )
    return not any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
            not address.is_global,
        )
    )


def _production_evidence_url_is_safe(value: Any) -> bool:
    parsed = _safe_urlparse(value) if isinstance(value, str) else None
    return bool(
        parsed is not None
        and parsed.scheme == "https"
        and parsed.hostname
        and _production_host_is_safe(parsed.hostname.lower())
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and "\\" not in value
    )


def _configuration_contract_failures(payload: Any) -> list[str]:
    contract = payload.get("configuration_contract") if isinstance(payload, dict) else None
    if not isinstance(contract, dict):
        return ["configuration_contract"]

    failures: list[str] = []
    if set(contract) != REQUIRED_CONFIGURATION_CONTRACT_FIELDS:
        failures.append("configuration_contract_fields")

    hosts = contract.get("allowed_http_hosts")
    if (
        not isinstance(hosts, list)
        or any(not _production_host_is_safe(host) for host in hosts)
    ):
        failures.append("configuration_contract.allowed_http_hosts")

    mode = contract.get("outbound_policy_mode")
    if mode not in {"allowlist", "deny_all"}:
        failures.append("configuration_contract.outbound_policy_mode")
    elif (mode == "allowlist" and not hosts) or (mode == "deny_all" and hosts):
        failures.append("configuration_contract.outbound_policy")

    for field in ("retention_policy_url", "backup_restore_evidence_url"):
        value = contract.get(field)
        if not _production_evidence_url_is_safe(value):
            failures.append(f"configuration_contract.{field}")

    support_contact = contract.get("support_contact")
    if not isinstance(support_contact, str) or not support_contact.strip():
        failures.append("configuration_contract.support_contact")
    return failures


def _iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _worker_dispatch_failures(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["execution_worker_dispatch"]

    failures: list[str] = []
    if value.get("verified") is not True:
        failures.append("execution_worker_dispatch.verified")
    if value.get("source") not in {"internal", "external"}:
        failures.append("execution_worker_dispatch.source")
    if not _iso_timestamp(value.get("observed_at")):
        failures.append("execution_worker_dispatch.observed_at")
    age_seconds = value.get("age_seconds")
    if (
        not isinstance(age_seconds, (int, float))
        or isinstance(age_seconds, bool)
        or not math.isfinite(float(age_seconds))
        or age_seconds < 0
    ):
        failures.append("execution_worker_dispatch.age_seconds")
    return failures


def _worker_drain_failures(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["worker drain response is not an object"]

    failures: list[str] = []
    for field in ("processed", "backlog", "audit_backlog"):
        value = payload.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            failures.append(f"worker drain {field}")
    if payload.get("backlog") != 0:
        failures.append("worker drain backlog must be zero")
    if payload.get("audit_backlog") != 0:
        failures.append("worker drain audit_backlog must be zero")
    failures.extend(_worker_dispatch_failures(payload.get("dispatch")))
    return failures


def _readiness_failures(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["readiness response is not an object"]
    failures: list[str] = []
    expected = {
        "status": "ready",
        "development_auth": False,
        "rate_limit_configured": True,
        "production_identity": True,
        "storage_backend": "postgres",
        "audit_anchor_configured": True,
        "audit_anchor_backlog": 0,
        "audit_anchor_delivery_verified": True,
        "audit_anchor_delivery_fresh": True,
        "execution_job_backlog": 0,
    }
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            failures.append(field)
    if not _iso_timestamp(payload.get("audit_anchor_last_delivered_at")):
        failures.append("audit_anchor_last_delivered_at")
    failures.extend(_configuration_contract_failures(payload))
    failures.extend(_worker_dispatch_failures(payload.get("execution_worker_dispatch")))
    bindings = payload.get("operational_bindings")
    required_bindings = {
        "retention_verified",
        "support_verified",
        "outbound_policy_verified",
        "backup_restore_verified",
        "worker_dispatch_verified",
    }
    if not isinstance(bindings, dict):
        failures.append("operational_bindings")
    else:
        failures.extend(sorted(name for name in required_bindings if bindings.get(name) is not True))
    return failures


def _evidence_check_failures(value: Any, required_names: set[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["checks"]

    names: list[str] = []
    for check in value:
        if (
            not isinstance(check, dict)
            or set(check) != {"name", "passed"}
            or not isinstance(check.get("name"), str)
            or check.get("passed") is not True
        ):
            return ["checks"]
        names.append(check["name"])

    failures: list[str] = []
    name_set = set(names)
    if len(names) != len(name_set):
        failures.append("duplicate_checks")
    if not required_names.issubset(name_set):
        failures.append("required_checks")
    if not name_set.issubset(required_names):
        failures.append("unexpected_checks")
    return failures


def _restore_evidence_failures(readiness: Any, evidence_bytes: bytes) -> list[str]:
    if not evidence_bytes:
        return ["restore evidence file is missing"]
    if len(evidence_bytes) > MAX_RESTORE_EVIDENCE_BYTES:
        return ["restore evidence exceeds the size limit"]
    if not isinstance(readiness, dict):
        return ["readiness response is not an object"]
    descriptor = readiness.get("backup_restore_evidence")
    if not isinstance(descriptor, dict):
        return ["readiness has no restore evidence descriptor"]
    if not _iso_timestamp(descriptor.get("verified_at")):
        return ["readiness restore evidence verified_at is not timezone-qualified"]
    expected_sha256 = descriptor.get("sha256")
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        return ["readiness restore evidence digest is invalid"]
    if hashlib.sha256(evidence_bytes).hexdigest() != expected_sha256:
        return ["restore evidence digest does not match readiness"]

    evidence_url = descriptor.get("url")
    configuration_contract = readiness.get("configuration_contract")
    if (
        isinstance(configuration_contract, dict)
        and configuration_contract.get("backup_restore_evidence_url") != evidence_url
    ):
        return ["configuration contract restore evidence URL mismatch"]
    if not _production_evidence_url_is_safe(evidence_url):
        return ["readiness restore evidence URL is not a credential-free HTTPS reference"]
    try:
        evidence = json.loads(evidence_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ["restore evidence is not valid JSON"]
    if not isinstance(evidence, dict):
        return ["restore evidence is not an object"]

    failures: list[str] = []
    if evidence.get("schema_version") != 1:
        failures.append("schema_version")
    if evidence.get("verified") is not True:
        failures.append("verified")
    if evidence.get("cleanup_verified") is not True:
        failures.append("cleanup_verified")
    if evidence.get("generated_at") != descriptor.get("verified_at"):
        failures.append("verified_at")
    backup_sha256 = evidence.get("backup_sha256")
    if not isinstance(backup_sha256, str) or not SHA256_PATTERN.fullmatch(backup_sha256):
        failures.append("backup_sha256")
    failures.extend(_evidence_check_failures(evidence.get("checks"), REQUIRED_RESTORE_CHECKS))
    source_counts = evidence.get("source_row_counts")
    restored_counts = evidence.get("restored_row_counts")
    valid_counts = bool(
        isinstance(source_counts, dict)
        and set(source_counts) == REQUIRED_RESTORE_TABLES
        and all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in source_counts.values())
    )
    if not valid_counts or source_counts != restored_counts:
        failures.append("row_counts")
    container_image = evidence.get("container_image")
    if not isinstance(container_image, str) or not PINNED_IMAGE_PATTERN.fullmatch(container_image):
        failures.append("container_image")
    container_image_id = evidence.get("container_image_id")
    if not isinstance(container_image_id, str) or not SHA256_REFERENCE_PATTERN.fullmatch(container_image_id):
        failures.append("container_image_id")
    return failures


def _operational_evidence_failures(readiness: Any, evidence_bytes: bytes) -> list[str]:
    if not evidence_bytes:
        return ["operational evidence file is missing"]
    if len(evidence_bytes) > MAX_OPERATIONAL_EVIDENCE_BYTES:
        return ["operational evidence exceeds the size limit"]
    if not isinstance(readiness, dict):
        return ["readiness response is not an object"]
    descriptor = readiness.get("operational_evidence")
    if not isinstance(descriptor, dict):
        return ["readiness has no operational evidence descriptor"]
    if not _iso_timestamp(descriptor.get("verified_at")):
        return ["readiness operational evidence verified_at is not timezone-qualified"]
    expected_sha256 = descriptor.get("sha256")
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        return ["readiness operational evidence digest is invalid"]
    if hashlib.sha256(evidence_bytes).hexdigest() != expected_sha256:
        return ["operational evidence digest does not match readiness"]

    evidence_url = descriptor.get("url")
    if not _production_evidence_url_is_safe(evidence_url):
        return ["readiness operational evidence URL is not a credential-free HTTPS reference"]
    try:
        evidence = json.loads(evidence_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ["operational evidence is not valid JSON"]
    if not isinstance(evidence, dict):
        return ["operational evidence is not an object"]

    failures: list[str] = []
    if evidence.get("schema_version") != 1:
        failures.append("schema_version")
    if evidence.get("verified") is not True:
        failures.append("verified")
    if evidence.get("generated_at") != descriptor.get("verified_at"):
        failures.append("verified_at")
    binding_fingerprint = evidence.get("binding_fingerprint")
    if (
        not isinstance(binding_fingerprint, str)
        or not SHA256_PATTERN.fullmatch(binding_fingerprint)
        or binding_fingerprint != descriptor.get("binding_fingerprint")
    ):
        failures.append("binding_fingerprint")
    failures.extend(_evidence_check_failures(evidence.get("checks"), REQUIRED_OPERATIONAL_CHECKS))
    return failures


def _safe_report_target(base_url: str) -> str:
    parsed = _safe_urlparse(base_url)
    if parsed is None or not parsed.scheme or not parsed.hostname:
        return ""
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    try:
        netloc = f"{host}:{parsed.port}" if parsed.port else host
    except ValueError:
        netloc = host
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def verify_production_handover(
    client: HandoverClient,
    *,
    base_url: str,
    primary_identity_assertion: str,
    secondary_identity_assertion: str,
    worker_token: str,
    expected_primary_tenant: str = "",
    expected_secondary_tenant: str = "",
    backup_restore_evidence: bytes = b"",
    operational_evidence: bytes = b"",
) -> dict[str, Any]:
    checks: list[dict[str, object]] = []
    report_target = _safe_report_target(base_url)
    expected_primary_tenant = (expected_primary_tenant or "").strip()
    expected_secondary_tenant = (expected_secondary_tenant or "").strip()

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    parsed_url = _safe_urlparse(base_url)
    transport_ok = bool(
        parsed_url is not None
        and parsed_url.scheme == "https"
        and parsed_url.hostname
        and _production_host_is_safe(parsed_url.hostname.lower())
        and parsed_url.path in {"/api", "/api/"}
        and not parsed_url.username
        and not parsed_url.password
        and not parsed_url.query
        and not parsed_url.fragment
        and "\\" not in base_url
    )
    record(
        "secure_transport",
        transport_ok,
        "Authority target uses the absolute HTTPS /api route on a safe host." if transport_ok else "Authority target must use HTTPS /api on a global host without embedded credentials, query, or fragment.",
    )
    if not transport_ok:
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target": report_target,
            "verdict": "NO_GO",
            "checks": checks,
        }

    live = _safe_request(client, "GET", "/health/live")
    record("liveness", live.status == 200 and live.payload == {"status": "live"}, f"Authority liveness returned HTTP {live.status}.")

    primary_response, primary_token, primary_actor = _session(client, primary_identity_assertion)
    primary_tenant = primary_actor.get("tenant_id")
    primary_session_failures = _session_contract_failures(primary_response.payload)
    primary_ok = (
        primary_response.status == 200
        and not primary_session_failures
        and bool(primary_token)
        and isinstance(primary_tenant, str)
        and primary_actor.get("role") == "Executive"
    )
    record(
        "primary_identity",
        primary_ok,
        f"Primary identity exchange returned HTTP {primary_response.status} and Executive authority."
        if primary_ok
        else f"Primary identity exchange returned HTTP {primary_response.status}; failing fields: {', '.join(primary_session_failures) if primary_session_failures else 'required Executive authority'}.",
    )

    secondary_response, secondary_token, secondary_actor = _session(client, secondary_identity_assertion)
    secondary_tenant = secondary_actor.get("tenant_id")
    secondary_session_failures = _session_contract_failures(secondary_response.payload)
    secondary_ok = (
        secondary_response.status == 200
        and not secondary_session_failures
        and bool(secondary_token)
        and isinstance(secondary_tenant, str)
    )
    record(
        "secondary_identity",
        secondary_ok,
        f"Secondary identity exchange returned HTTP {secondary_response.status}; failing fields: {', '.join(secondary_session_failures) if secondary_session_failures else 'none'}.",
    )

    identities_distinct = bool(primary_ok and secondary_ok and primary_tenant != secondary_tenant)
    tenant_expectations_declared = bool(
        expected_primary_tenant
        and expected_secondary_tenant
        and expected_primary_tenant != expected_secondary_tenant
    )
    expected_tenants_match = (
        tenant_expectations_declared
        and primary_tenant == expected_primary_tenant
        and secondary_tenant == expected_secondary_tenant
    )
    record(
        "tenant_identity",
        identities_distinct and expected_tenants_match,
        "Identity assertions resolved to distinct expected tenants." if identities_distinct and expected_tenants_match else "Tenant identities are missing, equal, or unexpected, or expected tenant IDs were not explicitly declared.",
    )

    marker_id = f"handover-probe-{uuid.uuid4()}"
    marker_path = f"/v1/workspaces/{marker_id}"
    marker_created = False
    revision: int | None = None
    if primary_ok and secondary_ok and identities_distinct and expected_tenants_match:
        created = _safe_request(
            client,
            "PUT",
            marker_path,
            headers={
                "authorization": f"Bearer {primary_token}",
                "if-none-match": "*",
            },
            body={"document": _workspace_document(marker_id, str(primary_actor.get("user_id") or "handover-verifier"))},
        )
        created_payload = created.payload if isinstance(created.payload, dict) else {}
        revision_value = created_payload.get("revision")
        if created.status == 201 and not isinstance(revision_value, int):
            recovered = _safe_request(
                client,
                "GET",
                marker_path,
                headers={"authorization": f"Bearer {primary_token}"},
            )
            recovered_payload = recovered.payload if isinstance(recovered.payload, dict) else {}
            revision_value = recovered_payload.get("revision")
        marker_created = created.status == 201
        revision = revision_value if isinstance(revision_value, int) else None
        # Create-only workspace writes start at revision 1. Keep the fallback
        # bounded so a malformed 201 response can still be cleaned up safely.
        probe_revision = revision if revision is not None else 1
        record(
            "workspace_write",
            marker_created and revision is not None,
            f"Primary tenant marker creation returned HTTP {created.status}.",
        )

        isolated = _safe_request(
            client,
            "GET",
            marker_path,
            headers={"authorization": f"Bearer {secondary_token}"},
        )
        record(
            "tenant_isolation",
            marker_created and revision is not None and isolated.status == 404,
            f"Secondary tenant marker read returned HTTP {isolated.status}; expected 404.",
        )

        secondary_write = _safe_request(
            client,
            "PUT",
            marker_path,
            headers={
                "authorization": f"Bearer {secondary_token}",
                "if-match": f'"{probe_revision}"',
            },
            body={"document": _workspace_document(marker_id, str(primary_actor.get("user_id") or "handover-verifier"))},
        )
        primary_after_write = _safe_request(
            client,
            "GET",
            marker_path,
            headers={"authorization": f"Bearer {primary_token}"},
        )
        primary_after_write_payload = primary_after_write.payload if isinstance(primary_after_write.payload, dict) else {}
        write_isolated = (
            marker_created
            and revision is not None
            and secondary_write.status == 404
            and primary_after_write.status == 200
            and primary_after_write_payload.get("revision") == revision
        )
        record(
            "tenant_isolation_write",
            write_isolated,
            f"Secondary tenant workspace update returned HTTP {secondary_write.status}; primary marker read returned HTTP {primary_after_write.status}.",
        )

        secondary_delete = _safe_request(
            client,
            "DELETE",
            marker_path,
            headers={
                "authorization": f"Bearer {secondary_token}",
                "if-match": f'"{probe_revision}"',
            },
        )
        primary_after_delete = _safe_request(
            client,
            "GET",
            marker_path,
            headers={"authorization": f"Bearer {primary_token}"},
        )
        primary_after_delete_payload = primary_after_delete.payload if isinstance(primary_after_delete.payload, dict) else {}
        delete_isolated = (
            marker_created
            and revision is not None
            and secondary_delete.status == 404
            and primary_after_delete.status == 200
            and primary_after_delete_payload.get("revision") == revision
        )
        record(
            "tenant_isolation_delete",
            delete_isolated,
            f"Secondary tenant workspace delete returned HTTP {secondary_delete.status}; primary marker read returned HTTP {primary_after_delete.status}.",
        )
    else:
        record("workspace_write", False, "Workspace marker was not created because both sessions are required.")
        record("tenant_isolation", False, "Tenant isolation was not tested because both sessions are required.")
        record("tenant_isolation_write", False, "Tenant update isolation was not tested because both sessions are required.")
        record("tenant_isolation_delete", False, "Tenant delete isolation was not tested because both sessions are required.")

    worker_probe_started = False
    worker_probe_run_id: str | None = None
    if marker_created and primary_ok and primary_token and worker_token:
        start_status = 0
        worker_probe = _safe_request(
            client,
            "POST",
            "/v1/runs",
            headers={
                "authorization": f"Bearer {primary_token}",
                "idempotency-key": f"handover-worker-{uuid.uuid4()}",
            },
            body=_worker_probe_request(marker_id),
        )
        worker_probe_payload = worker_probe.payload if isinstance(worker_probe.payload, dict) else {}
        candidate_run_id = worker_probe_payload.get("run_id")
        if worker_probe.status == 201 and isinstance(candidate_run_id, str) and candidate_run_id:
            worker_probe_run_id = candidate_run_id
            started = _safe_request(
                client,
                "POST",
                f"/v1/runs/{worker_probe_run_id}/start",
                headers={"authorization": f"Bearer {primary_token}"},
            )
            start_status = started.status
            worker_probe_started = started.status == 202
        record(
            "worker_execution_queued",
            worker_probe_started,
            f"Worker probe creation returned HTTP {worker_probe.status}; start returned HTTP {start_status}.",
        )
    else:
        record("worker_execution_queued", False, "Worker execution was not tested because the primary workspace or worker token was unavailable.")

    cleanup_revision = revision if revision is not None else (1 if marker_created else None)
    if marker_created and primary_ok and cleanup_revision is not None:
        deleted = _safe_request(
            client,
            "DELETE",
            marker_path,
            headers={
                "authorization": f"Bearer {primary_token}",
                "if-match": f'"{cleanup_revision}"',
            },
        )
        record("probe_cleanup", deleted.status == 204, f"Primary tenant marker cleanup returned HTTP {deleted.status}.")
        absent = _safe_request(
            client,
            "GET",
            marker_path,
            headers={"authorization": f"Bearer {primary_token}"},
        )
        record(
            "probe_absence",
            deleted.status == 204 and absent.status == 404,
            f"Primary tenant post-delete marker read returned HTTP {absent.status}; expected 404.",
        )
        audit = _safe_request(
            client,
            "GET",
            "/v1/audit/verify",
            headers={"authorization": f"Bearer {primary_token}"},
        )
        audit_payload = audit.payload if isinstance(audit.payload, dict) else {}
        audit_valid = (
            audit.status == 200
            and audit_payload.get("tenant_id") == primary_tenant
            and audit_payload.get("valid") is True
            and isinstance(audit_payload.get("event_count"), int)
            and audit_payload.get("event_count", 0) > 0
            and audit_payload.get("first_invalid_sequence") is None
        )
        record(
            "audit_chain",
            audit_valid,
            f"Primary tenant audit verification returned HTTP {audit.status}; tenant binding was {'valid' if audit_payload.get('tenant_id') == primary_tenant else 'invalid'}.",
        )
        event_count = audit_payload.get("event_count", 0)
        max_event_pages = max(1, (event_count + 499) // 500) if isinstance(event_count, int) else 1
        event_cursor = 0
        event_pages = 0
        events_status = 0
        deletion_recorded = False
        while event_pages < max_event_pages:
            events = _safe_request(
                client,
                "GET",
                f"/v1/events?after={event_cursor}&limit=500",
                headers={"authorization": f"Bearer {primary_token}"},
            )
            events_status = events.status
            event_pages += 1
            if events.status != 200 or not isinstance(events.payload, list):
                break
            deletion_recorded = any(
                isinstance(event, dict)
                and event.get("event_type") == "WORKSPACE_DELETED"
                and isinstance(event.get("payload"), dict)
                and event["payload"].get("workspace_id") == marker_id
                and event["payload"].get("revision") == revision
                for event in events.payload
            )
            if deletion_recorded or len(events.payload) < 500:
                break
            page_sequences = [
                event.get("sequence")
                for event in events.payload
                if isinstance(event, dict)
                and isinstance(event.get("sequence"), int)
                and event["sequence"] > event_cursor
            ]
            if not page_sequences:
                break
            next_cursor = max(page_sequences)
            if next_cursor <= event_cursor:
                break
            event_cursor = next_cursor
        record(
            "deletion_audit_event",
            events_status == 200 and deletion_recorded,
            f"Primary tenant deletion-event retrieval returned HTTP {events_status} after {event_pages} page(s).",
        )
    else:
        record("probe_cleanup", False, "No verified marker revision was available for cleanup.")
        record("probe_absence", False, "No verified marker revision was available for post-delete verification.")
        record("audit_chain", False, "Audit verification requires a created and deleted marker.")
        record("deletion_audit_event", False, "Deletion-event verification requires a created and deleted marker.")

    if worker_token:
        drain = _safe_request(
            client,
            "POST",
            "/v1/operations/jobs/drain",
            headers={"x-loopos-worker-token": worker_token},
        )
        drain_failures = _worker_drain_failures(drain.payload)
        record(
            "worker_dispatch",
            drain.status == 200 and not drain_failures,
            (
                f"Protected worker dispatch returned HTTP {drain.status}; failing fields: "
                f"{', '.join(drain_failures) if drain_failures else 'none'}."
            ),
        )
        if worker_probe_started and worker_probe_run_id and drain.status == 200:
            worker_run = _safe_request(
                client,
                "GET",
                f"/v1/runs/{worker_probe_run_id}",
                headers={"authorization": f"Bearer {primary_token}"},
            )
            worker_run_payload = worker_run.payload if isinstance(worker_run.payload, dict) else {}
            worker_execution_ok = (
                worker_run.status == 200
                and worker_run_payload.get("state") == "EFFECTIVENESS_PROVEN"
                and worker_run_payload.get("runner_status") == "completed"
                and isinstance(drain.payload, dict)
                and drain.payload.get("processed", 0) >= 1
            )
            record(
                "worker_execution",
                worker_execution_ok,
                f"External worker probe returned HTTP {worker_run.status} with state {worker_run_payload.get('state', 'unknown')} and runner status {worker_run_payload.get('runner_status', 'unknown')}.",
            )
        else:
            record("worker_execution", False, "External worker execution was not verified because the probe was not queued or drain failed.")
    else:
        record("worker_dispatch", False, "Worker token is missing.")
        record("worker_execution", False, "External worker execution was not verified because the worker token is missing.")

    ready = _safe_request(client, "GET", "/health/ready")
    readiness_failures = _readiness_failures(ready.payload)
    record(
        "production_readiness",
        ready.status == 200 and not readiness_failures,
        f"Readiness returned HTTP {ready.status}; failing fields: {', '.join(readiness_failures) if readiness_failures else 'none'}.",
    )
    restore_evidence_failures = _restore_evidence_failures(ready.payload, backup_restore_evidence)
    record(
        "backup_restore_evidence",
        not restore_evidence_failures,
        (
            "Restore evidence bytes match the production readiness descriptor."
            if not restore_evidence_failures
            else f"Restore evidence failed: {', '.join(restore_evidence_failures)}."
        ),
    )
    operational_evidence_failures = _operational_evidence_failures(ready.payload, operational_evidence)
    record(
        "operational_evidence",
        not operational_evidence_failures,
        (
            "Operational evidence bytes match the production readiness descriptor and deployed binding fingerprint."
            if not operational_evidence_failures
            else f"Operational evidence failed: {', '.join(operational_evidence_failures)}."
        ),
    )

    workspace_reads_ok = False
    if primary_ok and secondary_ok and identities_distinct and expected_tenants_match:
        primary_list = _safe_request(
            client,
            "GET",
            "/v1/workspaces",
            headers={"authorization": f"Bearer {primary_token}"},
        )
        secondary_list = _safe_request(
            client,
            "GET",
            "/v1/workspaces",
            headers={"authorization": f"Bearer {secondary_token}"},
        )
        workspace_reads_ok = (
            primary_list.status == 200
            and isinstance(primary_list.payload, list)
            and secondary_list.status == 200
            and isinstance(secondary_list.payload, list)
        )
        detail = f"Tenant workspace reads returned HTTP {primary_list.status} and {secondary_list.status}."
    else:
        detail = "Tenant workspace reads were not tested because both verified sessions and explicit expected tenant IDs are required."
    record("tenant_workspace_reads", workspace_reads_ok, detail)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": report_target,
        "verdict": "GO" if all(bool(check["passed"]) for check in checks) else "NO_GO",
        "backup_restore_evidence_sha256": (
            hashlib.sha256(backup_restore_evidence).hexdigest()
            if backup_restore_evidence
            else None
        ),
        "operational_evidence_sha256": (
            hashlib.sha256(operational_evidence).hexdigest()
            if operational_evidence
            else None
        ),
        "checks": checks,
    }


def _missing_configuration_report(base_url: str, missing: list[str]) -> dict[str, Any]:
    required_inputs = [
        {"name": name, "purpose": purpose, "sensitive": sensitive}
        for name, purpose, sensitive in REQUIRED_HANDOVER_INPUTS
    ]
    missing_inputs = [
        {
            "name": name,
            "status": "invalid" if "(" in name else "missing",
            "sensitive": next((sensitive for required_name, _, sensitive in REQUIRED_HANDOVER_INPUTS if required_name == name), False),
        }
        for name in missing
    ]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": _safe_report_target(base_url),
        "verdict": "NO_GO",
        "required_inputs": required_inputs,
        "missing_inputs": missing_inputs,
        "next_actions": [
            "Provide every missing input without committing assertions, tokens, or evidence contents to the repository.",
            "Rerun the handover verifier against the deployed HTTPS /api authority after the inputs are available.",
        ],
        "checks": [
            {
                "name": "verifier_configuration",
                "passed": False,
                "detail": f"Missing required environment variables: {', '.join(missing)}.",
            }
        ],
    }


def _read_restore_evidence(path: str) -> bytes:
    try:
        with Path(path).open("rb") as evidence_file:
            evidence = evidence_file.read(MAX_RESTORE_EVIDENCE_BYTES + 1)
    except OSError as error:
        raise RuntimeError("The backup/restore evidence file could not be read.") from error
    if len(evidence) > MAX_RESTORE_EVIDENCE_BYTES:
        raise RuntimeError("The backup/restore evidence file exceeds the size limit.")
    return evidence


def _read_operational_evidence(path: str) -> bytes:
    try:
        with Path(path).open("rb") as evidence_file:
            evidence = evidence_file.read(MAX_OPERATIONAL_EVIDENCE_BYTES + 1)
    except OSError as error:
        raise RuntimeError("The operational evidence file could not be read.") from error
    if len(evidence) > MAX_OPERATIONAL_EVIDENCE_BYTES:
        raise RuntimeError("The operational evidence file exceeds the size limit.")
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the reversible LoopOS production handover proof.")
    parser.add_argument("--base-url", default=os.getenv("LOOPOS_HANDOVER_BASE_URL", ""))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)

    primary_assertion = os.getenv("LOOPOS_HANDOVER_PRIMARY_IDENTITY_ASSERTION", "")
    secondary_assertion = os.getenv("LOOPOS_HANDOVER_SECONDARY_IDENTITY_ASSERTION", "")
    worker_token = os.getenv("LOOPOS_HANDOVER_WORKER_TOKEN", "")
    restore_evidence_path = os.getenv("LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE", "")
    operational_evidence_path = os.getenv("LOOPOS_HANDOVER_OPERATIONAL_EVIDENCE_FILE", "")
    required = {
        "LOOPOS_HANDOVER_BASE_URL": args.base_url,
        "LOOPOS_HANDOVER_PRIMARY_IDENTITY_ASSERTION": primary_assertion,
        "LOOPOS_HANDOVER_SECONDARY_IDENTITY_ASSERTION": secondary_assertion,
        "LOOPOS_HANDOVER_EXPECTED_PRIMARY_TENANT": os.getenv("LOOPOS_HANDOVER_EXPECTED_PRIMARY_TENANT", ""),
        "LOOPOS_HANDOVER_EXPECTED_SECONDARY_TENANT": os.getenv("LOOPOS_HANDOVER_EXPECTED_SECONDARY_TENANT", ""),
        "LOOPOS_HANDOVER_WORKER_TOKEN": worker_token,
        "LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE": restore_evidence_path,
        "LOOPOS_HANDOVER_OPERATIONAL_EVIDENCE_FILE": operational_evidence_path,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        report = _missing_configuration_report(args.base_url, missing)
    else:
        try:
            restore_evidence = _read_restore_evidence(restore_evidence_path)
        except RuntimeError:
            report = _missing_configuration_report(
                args.base_url,
                ["LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE (unreadable or oversized)"],
            )
        else:
            try:
                operational_evidence = _read_operational_evidence(operational_evidence_path)
            except RuntimeError:
                report = _missing_configuration_report(
                    args.base_url,
                    ["LOOPOS_HANDOVER_OPERATIONAL_EVIDENCE_FILE (unreadable or oversized)"],
                )
            else:
                report = verify_production_handover(
                    UrlJsonClient(args.base_url, timeout_seconds=args.timeout_seconds),
                    base_url=args.base_url,
                    primary_identity_assertion=primary_assertion,
                    secondary_identity_assertion=secondary_assertion,
                    worker_token=worker_token,
                    expected_primary_tenant=os.getenv("LOOPOS_HANDOVER_EXPECTED_PRIMARY_TENANT", ""),
                    expected_secondary_tenant=os.getenv("LOOPOS_HANDOVER_EXPECTED_SECONDARY_TENANT", ""),
                    backup_restore_evidence=restore_evidence,
                    operational_evidence=operational_evidence,
                )

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["verdict"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
