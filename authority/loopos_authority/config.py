from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
        )


def _connector_tokens(raw: str) -> dict[str, str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON must be a JSON object.") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(token, str) for key, token in value.items()):
        raise ValueError("LOOPOS_CONNECTOR_BEARER_TOKENS_JSON must map hostnames to bearer tokens.")
    return {key.lower(): token for key, token in value.items()}
