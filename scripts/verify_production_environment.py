from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = REPO_ROOT / "authority"
if str(AUTHORITY_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTHORITY_ROOT))

from loopos_authority.config import Settings, _connector_credentials_allowlisted, _connector_credentials_are_brokered, _http_host_is_valid, _outbound_policy_valid, _safe_urlparse, _secure_cors_origins, _secure_postgres_dsn, operational_binding_status  # noqa: E402
from loopos_authority.contracts import REQUIRED_AUDIT_TRIGGERS, REQUIRED_POSTGRES_TABLES  # noqa: E402


@dataclass(frozen=True)
class ConfigurationCheck:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _check(name: str, passed: bool, success: str, failure: str) -> ConfigurationCheck:
    return ConfigurationCheck(name=name, passed=passed, detail=success if passed else failure)


def _environment_value(name: str) -> str:
    return os.getenv(name, "").strip()


def _rate_limit_configuration_is_secure(settings: Settings | None = None) -> bool:
    if settings is not None:
        return bool(
            settings.rate_limit_requests is not None
            and settings.rate_limit_requests > 0
            and settings.rate_limit_window_seconds is not None
            and settings.rate_limit_window_seconds > 0
        )
    values = (_environment_value("LOOPOS_RATE_LIMIT_REQUESTS"), _environment_value("LOOPOS_RATE_LIMIT_WINDOW_SECONDS"))
    try:
        return all(int(value) > 0 for value in values)
    except (TypeError, ValueError):
        return False


def _secure_ui_authority_url(value: str, allowed_hosts: set[str] | None = None) -> bool:
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        parsed = _safe_urlparse(value)
        if parsed is None:
            return False
        return (
            parsed.path in {"/api", "/api/"}
            and not parsed.query
            and not parsed.fragment
        )
    parsed = _safe_urlparse(value)
    if parsed is None:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.path in {"/api", "/api/"}
        and not any((parsed.username, parsed.password, parsed.query, parsed.fragment))
        and _http_host_is_valid(parsed.hostname.lower())
        and (allowed_hosts is None or parsed.hostname.lower() in allowed_hosts or (parsed.netloc or "").lower() in allowed_hosts)
    )


def _comma_separated_hosts(name: str) -> set[str]:
    return {
        host.strip().lower()
        for host in _environment_value(name).split(",")
        if host.strip()
    }


def _configured_endpoint_hosts() -> set[str] | None:
    hosts: set[str] = set()
    for name in ("VITE_LOOPOS_LLM_ENDPOINT", "VITE_LOOPOS_TRANSCRIPTION_ENDPOINT"):
        value = _environment_value(name)
        if not value:
            continue
        parsed = _safe_urlparse(value)
        if (
            parsed is None
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or "\\" in value
            or not _http_host_is_valid(parsed.hostname.lower())
        ):
            return None
        hosts.add(parsed.hostname.lower())
    return hosts


def _vercel_routing_contract() -> tuple[bool, str]:
    """Keep the production preflight aligned with native api/index.py routing."""
    configuration_path = REPO_ROOT / "vercel.json"
    api_entrypoint = REPO_ROOT / "api" / "index.py"
    if not api_entrypoint.is_file():
        return False, "The Vercel serverless entrypoint api/index.py is missing."
    try:
        configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return False, f"The Vercel routing contract could not be loaded: {error}."
    routes = configuration.get("routes") if isinstance(configuration, dict) else None
    api_route = next(
        (
            item
            for item in routes or []
            if isinstance(item, dict) and item.get("dest") in {"/api/index.py", "api/index.py"}
        ),
        None,
    )
    if not isinstance(routes, list) or api_route is None or api_route.get("src") != "/api(?:/.*)?":
        return False, "The Vercel routing contract must map /api and every nested API path to api/index.py."
    rewrites = configuration.get("rewrites") if isinstance(configuration, dict) else None
    if not isinstance(rewrites, list):
        return False, "The Vercel routing contract must declare a rewrites list that excludes the native API route."
    if any(isinstance(item, dict) and item.get("source") == "/api/:path*" for item in rewrites):
        return False, "Remove the /api/:path* rewrite; Vercel must preserve the requested suffix for api/index.py."
    spa_rewrite = next(
        (
            item
            for item in rewrites
            if isinstance(item, dict)
            and item.get("destination") == "/index.html"
            and isinstance(item.get("source"), str)
            and "api(?:/|$)" in item["source"]
        ),
        None,
    )
    if spa_rewrite is None:
        return False, "The SPA rewrite must exclude /api and send only non-API paths to /index.html."
    return True, "Native api/index.py routing is preserved and the SPA rewrite excludes /api paths."


def _vercel_ignore_contract() -> tuple[bool, str]:
    """Keep local environment files out of uploaded Vercel build context."""
    ignore_path = REPO_ROOT / ".vercelignore"
    try:
        patterns = {
            line.strip()
            for line in ignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except (OSError, UnicodeDecodeError) as error:
        return False, f"The Vercel upload ignore contract could not be loaded: {error}."
    if ".env*" not in patterns:
        return False, "The Vercel upload ignore contract must exclude .env* files from build context."
    return True, "Vercel upload context excludes local environment files."


def _security_headers_contract() -> tuple[bool, str]:
    """Reject scheme-wide browser egress in the shipped deployment headers."""
    sources = (
        (REPO_ROOT / "vercel.json", "Vercel"),
        (REPO_ROOT / "ui" / "nginx.conf", "Nginx"),
    )
    failures: list[str] = []
    for path, label in sources:
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            failures.append(f"{label} security headers could not be loaded: {error}")
            continue

        if path.name == "vercel.json":
            try:
                configuration = json.loads(contents)
            except json.JSONDecodeError as error:
                failures.append(f"Vercel security headers could not be parsed: {error}")
                continue
            csp_values = [
                header.get("value", "")
                for group in configuration.get("headers", [])
                if isinstance(group, dict)
                for header in group.get("headers", [])
                if isinstance(header, dict)
                and str(header.get("key", "")).lower() == "content-security-policy"
            ]
        else:
            csp_values = re.findall(r"add_header\s+Content-Security-Policy\s+\"([^\"]+)\"", contents, re.IGNORECASE)

        if len(csp_values) != 1:
            failures.append(f"{label} must declare exactly one Content-Security-Policy header.")
            continue
        directives = {
            parts[0].lower(): parts[1:]
            for directive in csp_values[0].split(";")
            if (parts := directive.strip().split())
        }
        connect_sources = directives.get("connect-src", [])
        if "'self'" not in connect_sources:
            failures.append(f"{label} connect-src must retain the same-origin 'self' source.")
            continue
        for source in connect_sources:
            if source in {"https:", "http:", "*", "data:", "blob:"} or source.startswith("*."):
                failures.append(f"{label} connect-src contains a broad or non-network source: {source}.")
                continue
            if source == "'self'":
                continue
            parsed = urlparse(source)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                failures.append(f"{label} connect-src contains a non-exact HTTPS origin: {source}.")

    if failures:
        return False, " ".join(failures)
    return True, "Vercel and Nginx CSP headers use same-origin or exact HTTPS connect-src entries; scheme-wide egress is denied."


def _postgres_migration_contract() -> tuple[bool, str]:
    """Verify the checked-in migration carries the live store guarantees."""
    migrations_dir = REPO_ROOT / "supabase" / "migrations"
    try:
        migrations = sorted(migrations_dir.glob("*.sql"))
        migration_sql = "\n".join(path.read_text(encoding="utf-8") for path in migrations)
    except (OSError, UnicodeDecodeError) as error:
        return False, f"The Postgres migration contract could not be read: {error}."
    if not migrations:
        return False, "The Postgres migration contract is missing supabase/migrations/*.sql."

    missing_tables = [
        table
        for table in REQUIRED_POSTGRES_TABLES
        if not re.search(
            rf"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?{re.escape(table)}\b",
            migration_sql,
            re.IGNORECASE,
        )
    ]
    missing_rls = [
        table
        for table in REQUIRED_POSTGRES_TABLES
        if not re.search(
            rf"\balter\s+table\s+{re.escape(table)}\s+enable\s+row\s+level\s+security\b",
            migration_sql,
            re.IGNORECASE,
        )
    ]
    missing_triggers = [
        trigger
        for trigger in REQUIRED_AUDIT_TRIGGERS
        if not re.search(rf"\bcreate\s+trigger\s+{re.escape(trigger)}\b", migration_sql, re.IGNORECASE)
    ]
    failures = []
    if missing_tables:
        failures.append(f"tables={', '.join(sorted(missing_tables))}")
    if missing_rls:
        failures.append(f"rls={', '.join(sorted(missing_rls))}")
    if missing_triggers:
        failures.append(f"triggers={', '.join(sorted(missing_triggers))}")
    if failures:
        return False, "The Postgres migration contract is incomplete: " + "; ".join(failures) + "."
    return True, "Checked-in Postgres migrations declare every authority table, row-level security, and append-only audit trigger."


def _identity_configuration_is_secure(settings: Settings) -> bool:
    if not (
        settings.oidc_issuer
        and settings.oidc_audience
        and settings.oidc_jwks_url
        and settings.oidc_role_mapping
    ):
        return False
    # Keep the build-time gate dependency-free. Settings.from_env applies the
    # same URL, claim, and role-mapping shape checks used by the runtime
    # verifier; importing the runtime verifier here would require PyJWT during
    # a Vercel Node build before the Python function environment exists.
    return bool(
        settings.oidc_tenant_claim.strip()
        and settings.oidc_role_claim.strip()
        and settings.oidc_role_mapping
    )


def production_configuration_report() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        settings = Settings.from_env()
    except (TypeError, ValueError) as error:
        return {
            "schema_version": 1,
            "generated_at": generated_at,
            "configuration_verdict": "NO_GO",
            "authoritative_handover": "NOT_PROVEN",
            "checks": [
                ConfigurationCheck(
                    name="settings_loaded",
                    passed=False,
                    detail=str(error),
                ).as_dict(),
                _check(
                    "rate_limit_configured",
                    _rate_limit_configuration_is_secure(),
                    "Production request rate limiting has a positive request limit and window.",
                    "Set positive LOOPOS_RATE_LIMIT_REQUESTS and LOOPOS_RATE_LIMIT_WINDOW_SECONDS values.",
                ).as_dict(),
            ],
            "required_live_proofs": _required_live_proofs(),
        }

    bindings = operational_binding_status(settings)
    allowed_hosts = set(settings.allowed_http_hosts)
    ui_authority_hosts = _comma_separated_hosts("VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST")
    ui_allowed_hosts = _comma_separated_hosts("VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS")
    ui_endpoint_hosts = _configured_endpoint_hosts()
    ui_outbound_mode = _environment_value("VITE_LOOPOS_OUTBOUND_POLICY_MODE")
    ui_contract_declared = (
        _environment_value("VITE_LOOPOS_DEPLOYMENT_MODE").lower() == "enterprise"
        and _secure_ui_authority_url(_environment_value("VITE_LOOPOS_AUTHORITY_URL"), ui_authority_hosts)
        and _environment_value("VITE_LOOPOS_AUTH_MODE") == "bff-session"
        and _environment_value("VITE_LOOPOS_PERSISTENCE_MODE") == "api"
        and _environment_value("VITE_LOOPOS_AUDIT_MODE") == "server"
        and _environment_value("VITE_LOOPOS_CREDENTIAL_INJECTION_MODE") == "broker"
    )
    ui_outbound_matches = (
        ui_outbound_mode == settings.outbound_policy_mode
        and (
            (ui_outbound_mode == "deny_all" and not ui_allowed_hosts)
            or (
                ui_outbound_mode == "allowlist"
                and bool(ui_allowed_hosts)
                and ui_allowed_hosts <= allowed_hosts
            )
        )
    )
    ui_endpoints_constrained = (
        ui_endpoint_hosts is not None
        and ui_endpoint_hosts <= ui_allowed_hosts
        and ui_endpoint_hosts <= allowed_hosts
    )
    vercel_routing_passed, vercel_routing_detail = _vercel_routing_contract()
    vercel_ignore_passed, vercel_ignore_detail = _vercel_ignore_contract()
    security_headers_passed, security_headers_detail = _security_headers_contract()
    postgres_migration_passed, postgres_migration_detail = _postgres_migration_contract()
    checks = [
        _check(
            "development_auth_disabled",
            not settings.allow_dev_auth,
            "Development session issuance is disabled.",
            "Set LOOPOS_ALLOW_DEV_AUTH=false; development sessions cannot be used as production identity.",
        ),
        _check(
            "durable_postgres_configured",
            settings.storage_backend == "postgres" and _secure_postgres_dsn(settings.postgres_dsn),
            "The authority is configured for TLS-protected Postgres durability.",
            "Set LOOPOS_STORAGE_BACKEND=postgres and provide a Postgres DSN with sslmode=require, verify-ca, or verify-full.",
        ),
        _check(
            "rate_limit_configured",
            _rate_limit_configuration_is_secure(settings),
            "Production request rate limiting has a positive request limit and window.",
            "Set positive LOOPOS_RATE_LIMIT_REQUESTS and LOOPOS_RATE_LIMIT_WINDOW_SECONDS values.",
        ),
        _check(
            "postgres_migration_contract",
            postgres_migration_passed,
            postgres_migration_detail,
            postgres_migration_detail,
        ),
        _check(
            "production_identity_configured",
            _identity_configuration_is_secure(settings),
            "Complete HTTPS OIDC identity configuration is present.",
            "Configure the HTTPS OIDC issuer, audience, JWKS URL, tenant/role claims, and an explicit role mapping.",
        ),
        _check(
            "production_cors_restricted",
            _secure_cors_origins(settings.cors_origins, allow_local=settings.allow_dev_auth),
            "Every configured cross-origin UI origin uses approved HTTPS and can support the managed session exchange.",
            "Set LOOPOS_CORS_ORIGINS to only approved HTTPS origins, or an empty value for same-origin deployment.",
        ),
        _check(
            "outbound_policy_configured",
            _outbound_policy_valid(settings),
            "The outbound policy is structurally valid.",
            "Configure deny_all with no hosts or allowlist with valid hostname/IP entries.",
        ),
        _check(
            "audit_anchor_configured",
            bool(settings.audit_anchor_url and settings.audit_anchor_hmac_secret),
            "The external append-only audit anchor is configured.",
            "Configure LOOPOS_AUDIT_ANCHOR_URL and LOOPOS_AUDIT_ANCHOR_HMAC_SECRET together.",
        ),
        _check(
            "retention_evidence_configured",
            bindings["retention_verified"],
            "The retention binding has current immutable operational evidence.",
            "Configure the retention URL and current operational evidence URL, digest, and timestamp.",
        ),
        _check(
            "support_evidence_configured",
            bindings["support_verified"],
            "The support route has current immutable operational evidence.",
            "Configure LOOPOS_SUPPORT_CONTACT and current operational evidence.",
        ),
        _check(
            "outbound_policy_evidence_configured",
            bindings["outbound_policy_verified"],
            "The outbound policy has current immutable operational evidence.",
            "Configure deny_all or an exact host allowlist and bind it to current operational evidence.",
        ),
        _check(
            "backup_restore_evidence_configured",
            bindings["backup_restore_verified"],
            "A recent restore exercise is bound by HTTPS reference, digest, and timestamp.",
            "Configure a recent restore evidence URL, lowercase SHA-256 digest, and verification timestamp.",
        ),
        _check(
            "worker_dispatch_token_configured",
            bindings["worker_dispatch_verified"],
            "A minimum-32-byte worker dispatch token is configured.",
            "Configure LOOPOS_WORKER_TOKEN or CRON_SECRET with at least 32 bytes.",
        ),
        _check(
            "connector_credentials_allowlisted",
            _connector_credentials_allowlisted(settings),
            "Every configured connector credential belongs to an allowlisted host.",
            "Remove connector credentials for hosts not listed in LOOPOS_ALLOWED_HTTP_HOSTS.",
        ),
        _check(
            "credential_injection_broker",
            False,
            "An approved short-lived credential injection broker is integrated and independently verified.",
            "No credential injection broker is integrated in this release. Remove LOOPOS_CONNECTOR_BEARER_TOKENS_JSON and integrate the approved short-lived broker before production use.",
        ),
        _check(
            "static_connector_credentials_absent",
            _connector_credentials_are_brokered(settings),
            "No static connector credentials are present.",
            "Remove LOOPOS_CONNECTOR_BEARER_TOKENS_JSON; static connector credentials cannot be used in production.",
        ),
        _check(
            "enterprise_ui_contract_declared",
            ui_contract_declared,
            "The UI declares the secure enterprise authority, BFF session, API persistence, and server audit contract.",
            "Configure enterprise mode, the /api authority route or an allowlisted HTTPS authority URL, bff-session auth, API persistence, and server audit in VITE_LOOPOS_* variables.",
        ),
        _check(
            "ui_retention_binding_matches_authority",
            _environment_value("VITE_LOOPOS_RETENTION_POLICY_URL") == settings.retention_policy_url,
            "The UI retention reference matches the authority binding.",
            "VITE_LOOPOS_RETENTION_POLICY_URL must exactly match LOOPOS_RETENTION_POLICY_URL.",
        ),
        _check(
            "ui_support_binding_matches_authority",
            _environment_value("VITE_LOOPOS_SUPPORT_CONTACT") == settings.support_contact,
            "The UI support route matches the authority binding.",
            "VITE_LOOPOS_SUPPORT_CONTACT must exactly match LOOPOS_SUPPORT_CONTACT.",
        ),
        _check(
            "ui_outbound_binding_matches_authority",
            ui_outbound_matches,
            "The UI outbound mode and host set are constrained by the authority policy.",
            "The Vite outbound mode must match the authority mode, and every UI host must be authority-allowlisted.",
        ),
        _check(
            "ui_backup_restore_binding_matches_authority",
            _environment_value("VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL")
            == settings.backup_restore_evidence_url,
            "The UI restore evidence reference matches the authority binding.",
            "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL must exactly match LOOPOS_BACKUP_RESTORE_EVIDENCE_URL.",
        ),
        _check(
            "ui_optional_endpoints_constrained",
            ui_endpoints_constrained,
            "Every optional UI service endpoint uses HTTPS and belongs to both outbound allowlists.",
            "Optional Vite service endpoints must use credential-free HTTPS and be listed in both UI and authority host allowlists.",
        ),
        _check(
            "vercel_routing_contract",
            vercel_routing_passed,
            vercel_routing_detail,
            vercel_routing_detail,
        ),
        _check(
            "vercel_ignore_contract",
            vercel_ignore_passed,
            vercel_ignore_detail,
            vercel_ignore_detail,
        ),
        _check(
            "security_headers_contract",
            security_headers_passed,
            security_headers_detail,
            security_headers_detail,
        ),
    ]
    passed = all(check.passed for check in checks)
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "configuration_verdict": "READY_FOR_LIVE_VERIFICATION" if passed else "NO_GO",
        "authoritative_handover": "NOT_PROVEN",
        "checks": [check.as_dict() for check in checks],
        "required_live_proofs": _required_live_proofs(),
    }


def _required_live_proofs() -> list[str]:
    return [
        "deployed API routing and HTTPS reachability",
        "managed Postgres connectivity and tenant isolation",
        "two real OIDC identity assertions resolving to different tenants",
        "verified external audit-anchor delivery with zero backlog",
        "fresh worker dispatch heartbeat from the configured mode",
        "exact restore and operational evidence byte validation",
        "reversible production handover verifier GO report",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate LoopOS production configuration without printing secret values."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = production_configuration_report()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["configuration_verdict"] == "READY_FOR_LIVE_VERIFICATION" else 1


if __name__ == "__main__":
    sys.exit(main())
