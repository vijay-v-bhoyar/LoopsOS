from __future__ import annotations

import argparse
import hashlib
import json
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


def _readiness_failures(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["readiness response is not an object"]
    failures: list[str] = []
    expected = {
        "status": "ready",
        "development_auth": False,
        "production_identity": True,
        "storage_backend": "postgres",
        "audit_anchor_configured": True,
        "audit_anchor_backlog": 0,
        "audit_anchor_delivery_verified": True,
        "execution_job_backlog": 0,
    }
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            failures.append(field)
    dispatch = payload.get("execution_worker_dispatch")
    if not isinstance(dispatch, dict) or dispatch.get("verified") is not True:
        failures.append("execution_worker_dispatch")
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
    expected_sha256 = descriptor.get("sha256")
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        return ["readiness restore evidence digest is invalid"]
    if hashlib.sha256(evidence_bytes).hexdigest() != expected_sha256:
        return ["restore evidence digest does not match readiness"]

    evidence_url = descriptor.get("url")
    parsed_url = urlparse(evidence_url) if isinstance(evidence_url, str) else None
    if (
        parsed_url is None
        or parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
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
    checks = evidence.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(check, dict)
            or not isinstance(check.get("name"), str)
            or check.get("passed") is not True
            for check in checks
        )
    ):
        failures.append("checks")
    elif not REQUIRED_RESTORE_CHECKS.issubset({check["name"] for check in checks}):
        failures.append("required_checks")
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


def _safe_report_target(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname:
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
) -> dict[str, Any]:
    checks: list[dict[str, object]] = []
    report_target = _safe_report_target(base_url)

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    parsed_url = urlparse(base_url)
    transport_ok = bool(
        parsed_url.scheme == "https"
        and parsed_url.hostname
        and not parsed_url.username
        and not parsed_url.password
        and not parsed_url.query
        and not parsed_url.fragment
    )
    record(
        "secure_transport",
        transport_ok,
        "Authority target uses an absolute HTTPS origin." if transport_ok else "Authority target must use HTTPS without embedded credentials, query, or fragment.",
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
    primary_ok = primary_response.status == 200 and bool(primary_token) and isinstance(primary_tenant, str)
    record("primary_identity", primary_ok, f"Primary identity exchange returned HTTP {primary_response.status}.")

    secondary_response, secondary_token, secondary_actor = _session(client, secondary_identity_assertion)
    secondary_tenant = secondary_actor.get("tenant_id")
    secondary_ok = secondary_response.status == 200 and bool(secondary_token) and isinstance(secondary_tenant, str)
    record("secondary_identity", secondary_ok, f"Secondary identity exchange returned HTTP {secondary_response.status}.")

    identities_distinct = bool(primary_ok and secondary_ok and primary_tenant != secondary_tenant)
    expected_tenants_match = (
        (not expected_primary_tenant or primary_tenant == expected_primary_tenant)
        and (not expected_secondary_tenant or secondary_tenant == expected_secondary_tenant)
    )
    record(
        "tenant_identity",
        identities_distinct and expected_tenants_match,
        "Identity assertions resolved to distinct expected tenants." if identities_distinct and expected_tenants_match else "Tenant identities are missing, equal, or unexpected.",
    )

    marker_id = f"handover-probe-{uuid.uuid4()}"
    marker_path = f"/v1/workspaces/{marker_id}"
    marker_created = False
    revision: int | None = None
    if primary_token and secondary_token:
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
            marker_created and isolated.status == 404,
            f"Secondary tenant marker read returned HTTP {isolated.status}; expected 404.",
        )
    else:
        record("workspace_write", False, "Workspace marker was not created because both sessions are required.")
        record("tenant_isolation", False, "Tenant isolation was not tested because both sessions are required.")

    if marker_created and primary_token and revision is not None:
        deleted = _safe_request(
            client,
            "DELETE",
            marker_path,
            headers={
                "authorization": f"Bearer {primary_token}",
                "if-match": f'"{revision}"',
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
            and audit_payload.get("valid") is True
            and isinstance(audit_payload.get("event_count"), int)
            and audit_payload.get("event_count", 0) > 0
            and audit_payload.get("first_invalid_sequence") is None
        )
        record("audit_chain", audit_valid, f"Primary tenant audit verification returned HTTP {audit.status}.")
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
        drain_payload = drain.payload if isinstance(drain.payload, dict) else {}
        dispatch = drain_payload.get("dispatch")
        dispatch_verified = isinstance(dispatch, dict) and dispatch.get("verified") is True
        record("worker_dispatch", drain.status == 200 and dispatch_verified, f"Protected worker dispatch returned HTTP {drain.status}.")
    else:
        record("worker_dispatch", False, "Worker token is missing.")

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

    workspace_reads_ok = False
    if primary_token and secondary_token:
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
        detail = "Tenant workspace reads were not tested because both sessions are required."
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
        "checks": checks,
    }


def _missing_configuration_report(base_url: str, missing: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": _safe_report_target(base_url),
        "verdict": "NO_GO",
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
    required = {
        "LOOPOS_HANDOVER_BASE_URL": args.base_url,
        "LOOPOS_HANDOVER_PRIMARY_IDENTITY_ASSERTION": primary_assertion,
        "LOOPOS_HANDOVER_SECONDARY_IDENTITY_ASSERTION": secondary_assertion,
        "LOOPOS_HANDOVER_WORKER_TOKEN": worker_token,
        "LOOPOS_HANDOVER_BACKUP_RESTORE_EVIDENCE_FILE": restore_evidence_path,
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
            report = verify_production_handover(
                UrlJsonClient(args.base_url, timeout_seconds=args.timeout_seconds),
                base_url=args.base_url,
                primary_identity_assertion=primary_assertion,
                secondary_identity_assertion=secondary_assertion,
                worker_token=worker_token,
                expected_primary_tenant=os.getenv("LOOPOS_HANDOVER_EXPECTED_PRIMARY_TENANT", ""),
                expected_secondary_tenant=os.getenv("LOOPOS_HANDOVER_EXPECTED_SECONDARY_TENANT", ""),
                backup_restore_evidence=restore_evidence,
            )

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["verdict"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
