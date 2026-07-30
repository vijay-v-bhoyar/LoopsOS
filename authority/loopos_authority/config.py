from __future__ import annotations

import os
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse


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
    if value <= 0:
        raise ValueError(f"{name} must be a positive number.")
    return value


def _validate_audit_anchor(url: str | None, secret: str | None) -> tuple[str | None, str | None]:
    if bool(url) != bool(secret):
        raise ValueError("LOOPOS_AUDIT_ANCHOR_URL and LOOPOS_AUDIT_ANCHOR_HMAC_SECRET must be configured together.")
    if not url or not secret:
        return None, None
    parsed = urlparse(url)
    localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and localhost):
        raise ValueError("LOOPOS_AUDIT_ANCHOR_URL must use HTTPS outside local development.")
    if not parsed.hostname:
        raise ValueError("LOOPOS_AUDIT_ANCHOR_URL must be an absolute HTTP(S) URL.")
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("LOOPOS_AUDIT_ANCHOR_HMAC_SECRET must contain at least 32 bytes.")
    return url, secret

def _secure_reference(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    return bool(parsed.hostname and (parsed.scheme == "https" or (parsed.scheme == "http" and localhost)))


def operational_binding_status(settings: "Settings") -> dict[str, bool]:
    try:
        verified_at = datetime.fromisoformat((settings.backup_restore_verified_at or "").replace("Z", "+00:00"))
        if verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)
        verified_at = verified_at.astimezone(timezone.utc)
    except ValueError:
        verified_at = datetime.min.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    backup_recent = now - timedelta(days=settings.backup_restore_max_age_days) <= verified_at <= now + timedelta(minutes=5)
    outbound_verified = settings.outbound_policy_mode == "deny_all" or (
        settings.outbound_policy_mode == "allowlist" and bool(settings.allowed_http_hosts)
    )
    return {
        "retention_verified": _secure_reference(settings.retention_policy_url),
        "support_verified": bool(settings.support_contact and settings.support_contact.strip()),
        "outbound_policy_verified": outbound_verified,
        "backup_restore_verified": _secure_reference(settings.backup_restore_evidence_url) and backup_recent,
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
    retention_policy_url: str | None = None
    support_contact: str | None = None
    outbound_policy_mode: str | None = None
    backup_restore_evidence_url: str | None = None
    backup_restore_verified_at: str | None = None
    backup_restore_max_age_days: float = 90.0

    @classmethod
    def from_env(cls) -> "Settings":
        repo_root = Path(os.getenv("LOOPOS_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
        database_path = Path(os.getenv("LOOPOS_DATABASE_PATH", repo_root / "authority" / "data" / "loopos-authority.db")).resolve()
        storage_backend = os.getenv("LOOPOS_STORAGE_BACKEND", "sqlite").strip().lower()
        if storage_backend not in {"sqlite", "postgres"}:
            raise ValueError("LOOPOS_STORAGE_BACKEND must be either 'sqlite' or 'postgres'.")
        allow_dev_auth = _boolean("LOOPOS_ALLOW_DEV_AUTH", True)
        session_secret = os.getenv("LOOPOS_SESSION_HMAC_SECRET", "loopos-local-development-secret-change-before-production")
        if not allow_dev_auth and len(session_secret.encode("utf-8")) < 32:
            raise ValueError("LOOPOS_SESSION_HMAC_SECRET must contain at least 32 bytes when development authentication is disabled.")
        oidc_issuer = os.getenv("LOOPOS_OIDC_ISSUER")
        oidc_audience = os.getenv("LOOPOS_OIDC_AUDIENCE")
        oidc_jwks_url = os.getenv("LOOPOS_OIDC_JWKS_URL")
        oidc_role_mapping = _role_mapping(os.getenv("LOOPOS_OIDC_ROLE_MAPPING_JSON", "{}"))
        oidc_values = (oidc_issuer, oidc_audience, oidc_jwks_url)
        if any(oidc_values) and (not all(oidc_values) or not oidc_role_mapping):
            raise ValueError("OIDC configuration requires issuer, audience, JWKS URL, and at least one role mapping.")
        audit_anchor_url, audit_anchor_hmac_secret = _validate_audit_anchor(
            os.getenv("LOOPOS_AUDIT_ANCHOR_URL"),
            os.getenv("LOOPOS_AUDIT_ANCHOR_HMAC_SECRET"),
        )
        outbound_policy_mode = os.getenv("LOOPOS_OUTBOUND_POLICY_MODE")
        if outbound_policy_mode and outbound_policy_mode not in {"allowlist", "deny_all"}:
            raise ValueError("LOOPOS_OUTBOUND_POLICY_MODE must be 'allowlist' or 'deny_all'.")
        retention_policy_url = os.getenv("LOOPOS_RETENTION_POLICY_URL")
        backup_restore_evidence_url = os.getenv("LOOPOS_BACKUP_RESTORE_EVIDENCE_URL")
        if retention_policy_url and not _secure_reference(retention_policy_url):
            raise ValueError("LOOPOS_RETENTION_POLICY_URL must use HTTPS outside local development.")
        if backup_restore_evidence_url and not _secure_reference(backup_restore_evidence_url):
            raise ValueError("LOOPOS_BACKUP_RESTORE_EVIDENCE_URL must use HTTPS outside local development.")
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
            webhook_secrets=_connector_tokens(os.getenv("LOOPOS_WEBHOOK_SECRETS_JSON", "{}")),
            oidc_issuer=oidc_issuer,
            oidc_audience=oidc_audience,
            oidc_jwks_url=oidc_jwks_url,
            oidc_tenant_claim=os.getenv("LOOPOS_OIDC_TENANT_CLAIM", "tenant_id"),
            oidc_role_claim=os.getenv("LOOPOS_OIDC_ROLE_CLAIM", "groups"),
            oidc_role_mapping=oidc_role_mapping,
            audit_anchor_url=audit_anchor_url,
            audit_anchor_hmac_secret=audit_anchor_hmac_secret,
            audit_anchor_poll_seconds=_positive_float("LOOPOS_AUDIT_ANCHOR_POLL_SECONDS", 5.0),
            retention_policy_url=retention_policy_url,
            support_contact=os.getenv("LOOPOS_SUPPORT_CONTACT"),
            outbound_policy_mode=outbound_policy_mode,
            backup_restore_evidence_url=backup_restore_evidence_url,
            backup_restore_verified_at=os.getenv("LOOPOS_BACKUP_RESTORE_VERIFIED_AT"),
            backup_restore_max_age_days=_positive_float("LOOPOS_BACKUP_RESTORE_MAX_AGE_DAYS", 90.0),
        )


def _connector_tokens(raw: str) -> dict[str, str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON must be a JSON object.") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(token, str) for key, token in value.items()):
        raise ValueError("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON must map hostnames to bearer tokens.")
    return {key.lower(): token for key, token in value.items()}


def _role_mapping(raw: str) -> dict[str, Literal["Executive", "Approver", "Operator", "Auditor"]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("LOOPOS_OIDC_ROLE_MAPPING_JSON must be a JSON object.") from error
    roles = {"Executive", "Approver", "Operator", "Auditor"}
    if not isinstance(value, dict) or not all(isinstance(key, str) and role in roles for key, role in value.items()):
        raise ValueError("LOOPOS_OIDC_ROLE_MAPPING_JSON must map external role names to supported LoopOS roles.")
    return value
