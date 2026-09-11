from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlparse


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HTTP_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
DEVELOPMENT_SESSION_SECRET = "loopos-local-development-secret-change-before-production"
SECURE_POSTGRES_SSLMODES = {"require", "verify-ca", "verify-full"}
POSTGRES_PORT_KEY_PATTERN = re.compile(r"(?:^|\s)port\s*=", re.IGNORECASE)
POSTGRES_PORT_VALUE_PATTERN = re.compile(
    r"""(?:^|\s)port\s*=\s*(?:(?P<single>'(?:\\.|[^'])*')|(?P<double>\"(?:\\.|[^\"])*\")|(?P<bare>[^\s]+))""",
    re.IGNORECASE,
)


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive number.") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number.")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a positive integer.") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return _positive_int(name, 1)


def _safe_urlparse(value: str):
    try:
        parsed = urlparse(value)
        parsed.port
    except ValueError:
        return None
    return parsed


def _validate_audit_anchor(
    url: str | None,
    secret: str | None,
    *,
    allow_local_http: bool = False,
) -> tuple[str | None, str | None]:
    if bool(url) != bool(secret):
        raise ValueError("LOOPOS_AUDIT_ANCHOR_URL and LOOPOS_AUDIT_ANCHOR_HMAC_SECRET must be configured together.")
    if not url or not secret:
        return None, None
    parsed = _safe_urlparse(url)
    localhost = parsed is not None and _is_local_hostname(parsed.hostname)
    if parsed is None or parsed.scheme != "https" and not (allow_local_http and parsed.scheme == "http" and localhost):
        raise ValueError("LOOPOS_AUDIT_ANCHOR_URL must use HTTPS outside local development.")
    if (
        parsed is None
        or not parsed.hostname
        or not _http_host_is_valid(parsed.hostname.lower(), allow_local=allow_local_http)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "\\" in url
    ):
        raise ValueError("LOOPOS_AUDIT_ANCHOR_URL must be a credential-free URL without query, fragment, or backslash.")
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("LOOPOS_AUDIT_ANCHOR_HMAC_SECRET must contain at least 32 bytes.")
    return url, secret

def _secure_evidence_reference(url: str | None, *, allow_local: bool = False) -> bool:
    if not url:
        return False
    parsed = _safe_urlparse(url)
    if parsed is None:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and _http_host_is_valid(parsed.hostname.lower(), allow_local=allow_local)
        and not any((parsed.username, parsed.password, parsed.query, parsed.fragment))
        and "\\" not in url
    )


def _secure_cors_origins(origins: tuple[str, ...], *, allow_local: bool = False) -> bool:
    for origin in origins:
        parsed = _safe_urlparse(origin)
        if (
            parsed is None
            or parsed.scheme != "https"
            or not parsed.hostname
            or not _http_host_is_valid(parsed.hostname.lower(), allow_local=allow_local)
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or "\\" in origin
        ):
            return False
    return True


def _connector_credentials_allowlisted(settings: "Settings") -> bool:
    credential_hosts = set((settings.connector_bearer_tokens or {}).keys())
    return credential_hosts <= set(settings.allowed_http_hosts)


def _connector_credentials_are_brokered(settings: "Settings") -> bool:
    """Static bearer-token configuration is never a production credential broker."""
    return not bool(settings.connector_bearer_tokens)


def _http_host_is_valid(host: str, *, allow_local: bool = False) -> bool:
    if not host or host != host.strip() or host.lower() != host or len(host) > 253:
        return False
    normalized = host.rstrip(".")
    if not normalized:
        return False
    if normalized == "localhost" or normalized.endswith(".localhost") or normalized == "::1":
        return allow_local
    try:
        address = ipaddress.ip_address(normalized)
        if normalized == "127.0.0.1" and allow_local:
            return True
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
            or not address.is_global
        ):
            return False
        return True
    except ValueError:
        pass
    labels = normalized.split(".")
    return bool(labels) and all(HTTP_HOST_LABEL_PATTERN.fullmatch(label) for label in labels)


def _is_local_hostname(host: str | None) -> bool:
    normalized = (host or "").lower().rstrip(".")
    return normalized == "localhost" or normalized.endswith(".localhost") or normalized in {"127.0.0.1", "::1"}


def _http_hosts_valid(hosts: tuple[str, ...], *, allow_local: bool = False) -> bool:
    return all(_http_host_is_valid(host, allow_local=allow_local) for host in hosts)


def _outbound_policy_valid(settings: "Settings") -> bool:
    if settings.outbound_policy_mode == "deny_all":
        return not settings.allowed_http_hosts
    return (
        settings.outbound_policy_mode == "allowlist"
        and bool(settings.allowed_http_hosts)
        and _http_hosts_valid(settings.allowed_http_hosts, allow_local=settings.allow_dev_auth)
    )


def _secure_postgres_dsn(dsn: str | None) -> bool:
    if not dsn:
        return False
    parsed = _safe_urlparse(dsn)
    if parsed is None:
        return False
    sslmode: str | None = None
    if parsed.scheme.lower() in {"postgres", "postgresql"}:
        sslmode = (parse_qs(parsed.query).get("sslmode") or [None])[-1]
    if sslmode is None:
        match = re.search(r"(?:^|\s)sslmode\s*=\s*['\"]?([^\s'\"]+)", dsn, re.IGNORECASE)
        sslmode = match.group(1) if match else None
    if not sslmode or sslmode.lower() not in SECURE_POSTGRES_SSLMODES:
        return False
    if parsed.scheme.lower() in {"postgres", "postgresql"}:
        return True
    if not POSTGRES_PORT_KEY_PATTERN.search(dsn):
        return True
    port_match = POSTGRES_PORT_VALUE_PATTERN.search(dsn)
    if not port_match:
        return False
    raw_port = next(
        value for value in (port_match.group("single"), port_match.group("double"), port_match.group("bare")) if value is not None
    )
    port = raw_port[1:-1] if raw_port[:1] in {"'", '"'} else raw_port
    return port.isdecimal() and 1 <= int(port) <= 65535


def _recent_evidence(verified_at_value: str | None, max_age_days: float) -> bool:
    try:
        verified_at = datetime.fromisoformat((verified_at_value or "").replace("Z", "+00:00"))
        if verified_at.tzinfo is None:
            return False
        verified_at = verified_at.astimezone(timezone.utc)
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    return now - timedelta(days=max_age_days) <= verified_at <= now + timedelta(minutes=5)


def operational_binding_fingerprint(settings: "Settings") -> str:
    binding = {
        "allowed_http_hosts": sorted(set(settings.allowed_http_hosts)),
        "outbound_policy_mode": settings.outbound_policy_mode,
        "retention_policy_url": settings.retention_policy_url,
        "support_contact": settings.support_contact,
    }
    canonical = json.dumps(binding, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def operational_binding_status(settings: "Settings") -> dict[str, bool]:
    backup_recent = _recent_evidence(
        settings.backup_restore_verified_at,
        settings.backup_restore_max_age_days,
    )
    operational_evidence_verified = (
        _secure_evidence_reference(settings.operational_evidence_url)
        and bool(SHA256_PATTERN.fullmatch(settings.operational_evidence_sha256 or ""))
        and _recent_evidence(
            settings.operational_evidence_verified_at,
            settings.operational_evidence_max_age_days,
        )
    )
    outbound_verified = _outbound_policy_valid(settings)
    return {
        "retention_verified": bool(
            _secure_evidence_reference(settings.retention_policy_url) and operational_evidence_verified
        ),
        "support_verified": bool(
            settings.support_contact
            and settings.support_contact.strip()
            and operational_evidence_verified
        ),
        "outbound_policy_verified": bool(outbound_verified and operational_evidence_verified),
        "backup_restore_verified": (
            _secure_evidence_reference(settings.backup_restore_evidence_url)
            and bool(SHA256_PATTERN.fullmatch(settings.backup_restore_evidence_sha256 or ""))
            and backup_recent
        ),
        "worker_dispatch_verified": bool(settings.worker_token and len(settings.worker_token.encode("utf-8")) >= 32),
    }


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    database_path: Path
    session_secret: str
    allow_dev_auth: bool
    allowed_http_hosts: tuple[str, ...]
    cors_origins: tuple[str, ...]
    storage_backend: str = "sqlite"
    postgres_dsn: str | None = None
    connector_bearer_tokens: dict[str, str] | None = None
    webhook_secrets: dict[str, str] | None = None
    event_poll_seconds: float = 0.25
    http_timeout_seconds: float = 15.0
    http_max_response_bytes: int = 1_000_000
    max_retry_attempts: int = 5
    retry_wait_seconds: float = 0.1
    scheduler_poll_seconds: float = 1.0
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_tenant_claim: str = "tenant_id"
    oidc_role_claim: str = "groups"
    oidc_role_mapping: dict[str, Literal["Executive", "Approver", "Operator", "Auditor"]] | None = None
    audit_anchor_url: str | None = None
    audit_anchor_hmac_secret: str | None = None
    audit_anchor_poll_seconds: float = 5.0
    audit_anchor_delivery_max_age_seconds: float = 300.0
    retention_policy_url: str | None = None
    support_contact: str | None = None
    outbound_policy_mode: str | None = None
    backup_restore_evidence_url: str | None = None
    backup_restore_evidence_sha256: str | None = None
    backup_restore_verified_at: str | None = None
    backup_restore_max_age_days: float = 90.0
    operational_evidence_url: str | None = None
    operational_evidence_sha256: str | None = None
    operational_evidence_verified_at: str | None = None
    operational_evidence_max_age_days: float = 90.0
    worker_token: str | None = None
    execution_worker_poll_seconds: float = 0.25
    execution_job_lease_seconds: int = 120
    execution_job_max_attempts: int = 5
    execution_worker_mode: Literal["internal", "external"] = "internal"
    execution_worker_heartbeat_max_age_seconds: float = 180.0
    rate_limit_requests: int | None = None
    rate_limit_window_seconds: int | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        repo_root = Path(os.getenv("LOOPOS_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
        database_path = Path(os.getenv("LOOPOS_DATABASE_PATH", repo_root / "authority" / "data" / "loopos-authority.db")).resolve()
        storage_backend = os.getenv("LOOPOS_STORAGE_BACKEND", "sqlite").strip().lower()
        if storage_backend not in {"sqlite", "postgres"}:
            raise ValueError("LOOPOS_STORAGE_BACKEND must be either 'sqlite' or 'postgres'.")
        vercel_runtime = _boolean("VERCEL")
        allow_dev_auth = _boolean("LOOPOS_ALLOW_DEV_AUTH", not vercel_runtime)
        if vercel_runtime and allow_dev_auth:
            raise ValueError("LOOPOS_ALLOW_DEV_AUTH cannot be enabled on Vercel deployments.")
        session_secret = os.getenv("LOOPOS_SESSION_HMAC_SECRET", DEVELOPMENT_SESSION_SECRET)
        if not allow_dev_auth and (
            session_secret == DEVELOPMENT_SESSION_SECRET or len(session_secret.encode("utf-8")) < 32
        ):
            raise ValueError(
                "LOOPOS_SESSION_HMAC_SECRET must be explicitly configured with at least 32 bytes when development authentication is disabled."
            )
        oidc_issuer = (os.getenv("LOOPOS_OIDC_ISSUER") or "").strip() or None
        oidc_audience = (os.getenv("LOOPOS_OIDC_AUDIENCE") or "").strip() or None
        oidc_jwks_url = (os.getenv("LOOPOS_OIDC_JWKS_URL") or "").strip() or None
        oidc_tenant_claim = os.getenv("LOOPOS_OIDC_TENANT_CLAIM", "tenant_id").strip()
        oidc_role_claim = os.getenv("LOOPOS_OIDC_ROLE_CLAIM", "groups").strip()
        oidc_role_mapping = _role_mapping(os.getenv("LOOPOS_OIDC_ROLE_MAPPING_JSON", "{}"))
        oidc_values = (oidc_issuer, oidc_audience, oidc_jwks_url)
        if any(oidc_values) and (not all(oidc_values) or not oidc_role_mapping):
            raise ValueError("OIDC configuration requires issuer, audience, JWKS URL, and at least one role mapping.")
        if any(oidc_values) and (not oidc_tenant_claim or not oidc_role_claim):
            raise ValueError("OIDC tenant and role claim names must be non-blank.")
        if oidc_issuer and not _secure_evidence_reference(oidc_issuer, allow_local=allow_dev_auth):
            raise ValueError("LOOPOS_OIDC_ISSUER must use a credential-free HTTPS URL.")
        if oidc_jwks_url and not _secure_evidence_reference(oidc_jwks_url, allow_local=allow_dev_auth):
            raise ValueError("LOOPOS_OIDC_JWKS_URL must use a credential-free HTTPS URL.")
        audit_anchor_url, audit_anchor_hmac_secret = _validate_audit_anchor(
            os.getenv("LOOPOS_AUDIT_ANCHOR_URL"),
            os.getenv("LOOPOS_AUDIT_ANCHOR_HMAC_SECRET"),
            allow_local_http=allow_dev_auth,
        )
        outbound_policy_mode = os.getenv("LOOPOS_OUTBOUND_POLICY_MODE")
        if outbound_policy_mode and outbound_policy_mode not in {"allowlist", "deny_all"}:
            raise ValueError("LOOPOS_OUTBOUND_POLICY_MODE must be 'allowlist' or 'deny_all'.")
        retention_policy_url = os.getenv("LOOPOS_RETENTION_POLICY_URL")
        backup_restore_evidence_url = os.getenv("LOOPOS_BACKUP_RESTORE_EVIDENCE_URL")
        backup_restore_evidence_sha256 = os.getenv("LOOPOS_BACKUP_RESTORE_EVIDENCE_SHA256")
        operational_evidence_url = os.getenv("LOOPOS_OPERATIONAL_EVIDENCE_URL")
        operational_evidence_sha256 = os.getenv("LOOPOS_OPERATIONAL_EVIDENCE_SHA256")
        if retention_policy_url and not _secure_evidence_reference(retention_policy_url, allow_local=allow_dev_auth):
            raise ValueError("LOOPOS_RETENTION_POLICY_URL must use a credential-free HTTPS URL.")
        if backup_restore_evidence_url and not _secure_evidence_reference(backup_restore_evidence_url, allow_local=allow_dev_auth):
            raise ValueError(
                "LOOPOS_BACKUP_RESTORE_EVIDENCE_URL must use a credential-free HTTPS URL outside local development."
            )
        if backup_restore_evidence_sha256 and not SHA256_PATTERN.fullmatch(backup_restore_evidence_sha256):
            raise ValueError("LOOPOS_BACKUP_RESTORE_EVIDENCE_SHA256 must be a lowercase SHA-256 digest.")
        if operational_evidence_url and not _secure_evidence_reference(operational_evidence_url, allow_local=allow_dev_auth):
            raise ValueError(
                "LOOPOS_OPERATIONAL_EVIDENCE_URL must use a credential-free HTTPS URL outside local development."
            )
        if operational_evidence_sha256 and not SHA256_PATTERN.fullmatch(operational_evidence_sha256):
            raise ValueError("LOOPOS_OPERATIONAL_EVIDENCE_SHA256 must be a lowercase SHA-256 digest.")
        worker_token = os.getenv("LOOPOS_WORKER_TOKEN") or os.getenv("CRON_SECRET")
        if worker_token and len(worker_token.encode("utf-8")) < 32:
            raise ValueError("LOOPOS_WORKER_TOKEN must contain at least 32 bytes.")
        execution_worker_mode = os.getenv(
            "LOOPOS_EXECUTION_WORKER_MODE",
            "external" if vercel_runtime else "internal",
        ).strip().lower()
        if execution_worker_mode not in {"internal", "external"}:
            raise ValueError("LOOPOS_EXECUTION_WORKER_MODE must be 'internal' or 'external'.")
        if vercel_runtime and execution_worker_mode != "external":
            raise ValueError("LOOPOS_EXECUTION_WORKER_MODE must be 'external' on Vercel deployments.")
        rate_limit_requests = _optional_positive_int("LOOPOS_RATE_LIMIT_REQUESTS")
        rate_limit_window_seconds = _optional_positive_int("LOOPOS_RATE_LIMIT_WINDOW_SECONDS")
        if not allow_dev_auth and (rate_limit_requests is None or rate_limit_window_seconds is None):
            raise ValueError(
                "Production request rate limiting requires LOOPOS_RATE_LIMIT_REQUESTS and LOOPOS_RATE_LIMIT_WINDOW_SECONDS."
            )
        return cls(
            repo_root=repo_root,
            database_path=database_path,
            storage_backend=storage_backend,
            postgres_dsn=os.getenv("LOOPOS_POSTGRES_DSN"),
            session_secret=session_secret,
            allow_dev_auth=allow_dev_auth,
            allowed_http_hosts=tuple(filter(None, (item.strip().lower() for item in os.getenv("LOOPOS_ALLOWED_HTTP_HOSTS", "").split(",")))),
            cors_origins=tuple(filter(None, (item.strip() for item in os.getenv("LOOPOS_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")))),
            connector_bearer_tokens=_connector_tokens(os.getenv("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON", "{}")),
            webhook_secrets=_webhook_secrets(
                os.getenv("LOOPOS_WEBHOOK_SECRETS_JSON", "{}"),
                allow_global=allow_dev_auth,
            ),
            oidc_issuer=oidc_issuer,
            oidc_audience=oidc_audience,
            oidc_jwks_url=oidc_jwks_url,
            oidc_tenant_claim=oidc_tenant_claim,
            oidc_role_claim=oidc_role_claim,
            oidc_role_mapping=oidc_role_mapping,
            audit_anchor_url=audit_anchor_url,
            audit_anchor_hmac_secret=audit_anchor_hmac_secret,
            audit_anchor_poll_seconds=_positive_float("LOOPOS_AUDIT_ANCHOR_POLL_SECONDS", 5.0),
            audit_anchor_delivery_max_age_seconds=_positive_float(
                "LOOPOS_AUDIT_ANCHOR_DELIVERY_MAX_AGE_SECONDS",
                300.0,
            ),
            retention_policy_url=retention_policy_url,
            support_contact=os.getenv("LOOPOS_SUPPORT_CONTACT"),
            outbound_policy_mode=outbound_policy_mode,
            backup_restore_evidence_url=backup_restore_evidence_url,
            backup_restore_evidence_sha256=backup_restore_evidence_sha256,
            backup_restore_verified_at=os.getenv("LOOPOS_BACKUP_RESTORE_VERIFIED_AT"),
            backup_restore_max_age_days=_positive_float("LOOPOS_BACKUP_RESTORE_MAX_AGE_DAYS", 90.0),
            operational_evidence_url=operational_evidence_url,
            operational_evidence_sha256=operational_evidence_sha256,
            operational_evidence_verified_at=os.getenv("LOOPOS_OPERATIONAL_EVIDENCE_VERIFIED_AT"),
            operational_evidence_max_age_days=_positive_float("LOOPOS_OPERATIONAL_EVIDENCE_MAX_AGE_DAYS", 90.0),
            worker_token=worker_token,
            execution_worker_poll_seconds=_positive_float("LOOPOS_EXECUTION_WORKER_POLL_SECONDS", 0.25),
            execution_job_lease_seconds=_positive_int("LOOPOS_EXECUTION_JOB_LEASE_SECONDS", 120),
            execution_job_max_attempts=_positive_int("LOOPOS_EXECUTION_JOB_MAX_ATTEMPTS", 5),
            execution_worker_mode=execution_worker_mode,  # type: ignore[arg-type]
            execution_worker_heartbeat_max_age_seconds=_positive_float(
                "LOOPOS_EXECUTION_WORKER_HEARTBEAT_MAX_AGE_SECONDS",
                180.0,
            ),
            rate_limit_requests=rate_limit_requests,
            rate_limit_window_seconds=rate_limit_window_seconds,
        )


def _connector_tokens(raw: str) -> dict[str, str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON must be a JSON object.") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(token, str) for key, token in value.items()):
        raise ValueError("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON must map hostnames to bearer tokens.")
    return {key.lower(): token for key, token in value.items()}


def _webhook_secrets(raw: str, *, allow_global: bool) -> dict[str, str]:
    secrets = _connector_tokens(raw)
    if allow_global:
        return secrets
    invalid = [
        key
        for key, secret in secrets.items()
        if key.count(":") != 1
        or not key.split(":", 1)[0]
        or key.rsplit(":", 1)[1] not in {"github", "jira"}
        or len(secret.encode("utf-8")) < 32
    ]
    if invalid:
        raise ValueError(
            "Production webhook secrets must use tenant:github or tenant:jira keys and contain at least 32 bytes."
        )
    return secrets


def _role_mapping(raw: str) -> dict[str, Literal["Executive", "Approver", "Operator", "Auditor"]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("LOOPOS_OIDC_ROLE_MAPPING_JSON must be a JSON object.") from error
    roles = {"Executive", "Approver", "Operator", "Auditor"}
    if not isinstance(value, dict) or not all(
        isinstance(key, str)
        and bool(key.strip())
        and key == key.strip()
        and role in roles
        for key, role in value.items()
    ):
        raise ValueError(
            "LOOPOS_OIDC_ROLE_MAPPING_JSON must map non-blank external role names to supported LoopOS roles."
        )
    return value
