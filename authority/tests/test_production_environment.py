from __future__ import annotations

import ast
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.verify_production_environment import _vercel_ignore_contract, main, production_configuration_report


def complete_production_environment() -> dict[str, str]:
    verified_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    return {
        "LOOPOS_ALLOW_DEV_AUTH": "false",
        "LOOPOS_RATE_LIMIT_REQUESTS": "120",
        "LOOPOS_RATE_LIMIT_WINDOW_SECONDS": "60",
        "LOOPOS_SESSION_HMAC_SECRET": "production-session-secret-that-is-at-least-thirty-two-bytes",
        "LOOPOS_STORAGE_BACKEND": "postgres",
        "LOOPOS_POSTGRES_DSN": "postgresql://loopos.example/authority?sslmode=require",
        "LOOPOS_OIDC_ISSUER": "https://identity.example.com/",
        "LOOPOS_OIDC_AUDIENCE": "loopos-production",
        "LOOPOS_OIDC_JWKS_URL": "https://identity.example.com/.well-known/jwks.json",
        "LOOPOS_OIDC_ROLE_MAPPING_JSON": '{"loopos-operators":"Operator"}',
        "LOOPOS_CORS_ORIGINS": "https://console.example.com",
        "LOOPOS_AUDIT_ANCHOR_URL": "https://audit.example.com/loopos/events",
        "LOOPOS_AUDIT_ANCHOR_HMAC_SECRET": "audit-anchor-secret-that-is-at-least-thirty-two-bytes",
        "LOOPOS_RETENTION_POLICY_URL": "https://policy.example.com/loopos-retention",
        "LOOPOS_SUPPORT_CONTACT": "loopos-operations@example.com",
        "LOOPOS_OUTBOUND_POLICY_MODE": "allowlist",
        "LOOPOS_ALLOWED_HTTP_HOSTS": "api.example.com",
        "LOOPOS_BACKUP_RESTORE_EVIDENCE_URL": "https://evidence.example.com/loopos/restore.json",
        "LOOPOS_BACKUP_RESTORE_EVIDENCE_SHA256": "a" * 64,
        "LOOPOS_BACKUP_RESTORE_VERIFIED_AT": verified_at,
        "LOOPOS_OPERATIONAL_EVIDENCE_URL": "https://evidence.example.com/loopos/operations.json",
        "LOOPOS_OPERATIONAL_EVIDENCE_SHA256": "b" * 64,
        "LOOPOS_OPERATIONAL_EVIDENCE_VERIFIED_AT": verified_at,
        "LOOPOS_WORKER_TOKEN": "production-worker-token-that-is-at-least-thirty-two-bytes",
        "LOOPOS_EXECUTION_WORKER_MODE": "external",
        "VITE_LOOPOS_DEPLOYMENT_MODE": "enterprise",
        "VITE_LOOPOS_ENVIRONMENT_NAME": "Production",
        "VITE_LOOPOS_AUTHORITY_URL": "/api",
        "VITE_LOOPOS_AUTH_MODE": "bff-session",
        "VITE_LOOPOS_PERSISTENCE_MODE": "api",
        "VITE_LOOPOS_AUDIT_MODE": "server",
        "VITE_LOOPOS_CREDENTIAL_INJECTION_MODE": "broker",
        "VITE_LOOPOS_RETENTION_POLICY_URL": "https://policy.example.com/loopos-retention",
        "VITE_LOOPOS_SUPPORT_CONTACT": "loopos-operations@example.com",
        "VITE_LOOPOS_OUTBOUND_POLICY_MODE": "allowlist",
        "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS": "api.example.com",
        "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL": "https://evidence.example.com/loopos/restore.json",
        "VITE_LOOPOS_LLM_ENDPOINT": "https://api.example.com/loopos",
    }


class ProductionEnvironmentVerifierTests(unittest.TestCase):
    def test_authority_template_covers_every_runtime_environment_name(self) -> None:
        config_path = Path("authority/loopos_authority/config.py")
        tree = ast.parse(config_path.read_text(encoding="utf-8"))
        environment_name = re.compile(r"^(?:LOOPOS_[A-Z0-9_]+|CRON_SECRET|VERCEL)$")
        runtime_names = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and environment_name.fullmatch(node.value)
        }
        template = Path("authority/.env.example").read_text(encoding="utf-8")

        self.assertEqual(sorted(name for name in runtime_names if name not in template), [])

    def test_empty_environment_fails_without_claiming_handover(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertEqual(report["authoritative_handover"], "NOT_PROVEN")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("development_auth_disabled", failed)
        self.assertIn("durable_postgres_configured", failed)
        self.assertIn("rate_limit_configured", failed)
        self.assertIn("production_identity_configured", failed)

    def test_invalid_startup_configuration_is_reported_without_secret_values(self) -> None:
        secret = "short"
        with patch.dict(
            "os.environ",
            {
                "VERCEL": "1",
                "LOOPOS_SESSION_HMAC_SECRET": secret,
            },
            clear=True,
        ):
            report = production_configuration_report()

        rendered = json.dumps(report)
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertNotIn(secret, rendered)
        self.assertIn("LOOPOS_SESSION_HMAC_SECRET", rendered)

    def test_complete_configuration_is_only_ready_for_live_verification(self) -> None:
        with patch.dict("os.environ", complete_production_environment(), clear=True):
            report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertEqual(report["authoritative_handover"], "NOT_PROVEN")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("credential_injection_broker", failed)
        self.assertTrue(next(check for check in report["checks"] if check["name"] == "rate_limit_configured")["passed"])
        self.assertIn("two real OIDC identity assertions resolving to different tenants", report["required_live_proofs"])
        self.assertIn("vercel_routing_contract", {check["name"] for check in report["checks"]})
        self.assertIn("vercel_ignore_contract", {check["name"] for check in report["checks"]})

    def test_malformed_rate_limit_configuration_fails_closed_with_named_check(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_RATE_LIMIT_REQUESTS"] = "0"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        rate_limit_check = next(check for check in report["checks"] if check["name"] == "rate_limit_configured")
        self.assertFalse(rate_limit_check["passed"])
        self.assertIn("LOOPOS_RATE_LIMIT_REQUESTS", rate_limit_check["detail"])

    def test_vercel_upload_ignore_requires_environment_pattern(self) -> None:
        import scripts.verify_production_environment as verifier

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(verifier, "REPO_ROOT", root):
                self.assertFalse(_vercel_ignore_contract()[0])
                (root / ".vercelignore").write_text("output\n", encoding="utf-8")
                self.assertFalse(_vercel_ignore_contract()[0])
                (root / ".vercelignore").write_text(".env*\n", encoding="utf-8")
                self.assertTrue(_vercel_ignore_contract()[0])

    def test_vercel_preflight_rejects_suffix_dropping_api_rewrite(self) -> None:
        import scripts.verify_production_environment as verifier

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api").mkdir()
            (root / "api" / "index.py").write_text("app = object()\n", encoding="utf-8")
            (root / "vercel.json").write_text(
                json.dumps({
                    "rewrites": [
                        {"source": "/api/:path*", "destination": "/api"},
                        {"source": "/((?!api(?:/|$)).*)", "destination": "/index.html"},
                    ]
                }),
                encoding="utf-8",
            )
            with patch.object(verifier, "REPO_ROOT", root), patch.dict("os.environ", complete_production_environment(), clear=True):
                report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("vercel_routing_contract", failed)

    def test_vercel_preflight_requires_nested_api_function_route(self) -> None:
        import scripts.verify_production_environment as verifier

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api").mkdir()
            (root / "api" / "index.py").write_text("app = object()\n", encoding="utf-8")
            (root / "vercel.json").write_text(
                json.dumps({
                    "rewrites": [
                        {"source": "/((?!api(?:/|$)).*)", "destination": "/index.html"},
                    ],
                }),
                encoding="utf-8",
            )
            with patch.object(verifier, "REPO_ROOT", root), patch.dict("os.environ", complete_production_environment(), clear=True):
                report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("vercel_routing_contract", failed)

    def test_security_headers_reject_scheme_wide_connect_src(self) -> None:
        import scripts.verify_production_environment as verifier

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api").mkdir()
            (root / "api" / "index.py").write_text("app = object()\n", encoding="utf-8")
            (root / "ui").mkdir()
            broad_csp = (
                "default-src 'self'; connect-src 'self' https:; "
                "script-src 'self'"
            )
            (root / "vercel.json").write_text(
                json.dumps({
                    "routes": [{"src": "/api(?:/.*)?", "dest": "/api/index.py"}],
                    "rewrites": [{"source": "/((?!api(?:/|$)).*)", "destination": "/index.html"}],
                    "headers": [{"source": "/(.*)", "headers": [{"key": "Content-Security-Policy", "value": broad_csp}]}],
                }),
                encoding="utf-8",
            )
            (root / "ui" / "nginx.conf").write_text(
                f'add_header Content-Security-Policy "{broad_csp}" always;\n',
                encoding="utf-8",
            )
            with patch.object(verifier, "REPO_ROOT", root), patch.dict("os.environ", complete_production_environment(), clear=True):
                report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("security_headers_contract", failed)

    def test_postgres_preflight_rejects_an_incomplete_migration_contract(self) -> None:
        import scripts.verify_production_environment as verifier

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api").mkdir()
            (root / "api" / "index.py").write_text("app = object()\n", encoding="utf-8")
            (root / "vercel.json").write_text(
                json.dumps({"rewrites": [{"source": "/((?!api(?:/|$)).*)", "destination": "/index.html"}]}),
                encoding="utf-8",
            )
            (root / "supabase" / "migrations").mkdir(parents=True)
            (root / "supabase" / "migrations" / "001-incomplete.sql").write_text(
                "create table if not exists runs (run_id text primary key);\n",
                encoding="utf-8",
            )
            with patch.object(verifier, "REPO_ROOT", root), patch.dict("os.environ", complete_production_environment(), clear=True):
                report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("postgres_migration_contract", failed)

    def test_blank_oidc_audience_fails_closed_before_live_verification(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_OIDC_AUDIENCE"] = "   "
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("settings_loaded", failed)

    def test_naive_evidence_timestamps_fail_closed(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_BACKUP_RESTORE_VERIFIED_AT"] = "2026-07-30T12:00:00"
        environment["LOOPOS_OPERATIONAL_EVIDENCE_VERIFIED_AT"] = "2026-07-30T12:00:00"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("retention_evidence_configured", failed)
        self.assertIn("backup_restore_evidence_configured", failed)

    def test_private_outbound_hosts_fail_closed_in_production(self) -> None:
        environment = complete_production_environment()
        environment.update({
            "LOOPOS_ALLOWED_HTTP_HOSTS": "127.0.0.1",
            "LOOPOS_CONNECTOR_BEARER_TOKENS_JSON": '{"127.0.0.1":"server-only-token"}',
            "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS": "127.0.0.1",
            "VITE_LOOPOS_LLM_ENDPOINT": "https://127.0.0.1/loopos",
        })
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("outbound_policy_configured", failed)
        self.assertIn("outbound_policy_evidence_configured", failed)
        self.assertIn("ui_optional_endpoints_constrained", failed)

    def test_private_cors_origin_fails_closed_in_production(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_CORS_ORIGINS"] = "https://127.0.0.1"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("production_cors_restricted", failed)

    def test_non_global_production_reference_hosts_fail_closed(self) -> None:
        for variable in (
            "LOOPOS_OIDC_ISSUER",
            "LOOPOS_OIDC_JWKS_URL",
            "LOOPOS_AUDIT_ANCHOR_URL",
            "LOOPOS_RETENTION_POLICY_URL",
            "LOOPOS_BACKUP_RESTORE_EVIDENCE_URL",
            "LOOPOS_OPERATIONAL_EVIDENCE_URL",
        ):
            with self.subTest(variable=variable):
                environment = complete_production_environment()
                environment[variable] = "https://100.64.0.1/reference"
                if variable == "LOOPOS_AUDIT_ANCHOR_URL":
                    environment["LOOPOS_AUDIT_ANCHOR_HMAC_SECRET"] = "audit-anchor-secret-that-is-at-least-thirty-two-bytes"
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                self.assertEqual(report["configuration_verdict"], "NO_GO")
                self.assertIn("settings_loaded", {check["name"] for check in report["checks"] if not check["passed"]})

    def test_localhost_suffixes_fail_closed_in_production(self) -> None:
        for variable in (
            "LOOPOS_OIDC_ISSUER",
            "LOOPOS_OIDC_JWKS_URL",
            "LOOPOS_AUDIT_ANCHOR_URL",
            "LOOPOS_RETENTION_POLICY_URL",
            "LOOPOS_BACKUP_RESTORE_EVIDENCE_URL",
            "LOOPOS_OPERATIONAL_EVIDENCE_URL",
        ):
            with self.subTest(variable=variable):
                environment = complete_production_environment()
                environment[variable] = "https://service.localhost/reference"
                if variable == "LOOPOS_AUDIT_ANCHOR_URL":
                    environment["LOOPOS_AUDIT_ANCHOR_HMAC_SECRET"] = "audit-anchor-secret-that-is-at-least-thirty-two-bytes"
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                self.assertEqual(report["configuration_verdict"], "NO_GO")
                self.assertIn("settings_loaded", {check["name"] for check in report["checks"] if not check["passed"]})

        environment = complete_production_environment()
        environment.update({
            "LOOPOS_ALLOWED_HTTP_HOSTS": "service.localhost",
            "LOOPOS_CONNECTOR_BEARER_TOKENS_JSON": '{"service.localhost":"server-side-token"}',
            "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS": "service.localhost",
            "VITE_LOOPOS_LLM_ENDPOINT": "https://service.localhost/loopos",
        })
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("outbound_policy_configured", failed)
        self.assertIn("outbound_policy_evidence_configured", failed)
        self.assertIn("ui_optional_endpoints_constrained", failed)

    def test_production_postgres_requires_encrypted_transport(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_POSTGRES_DSN"] = "postgresql://loopos.example/authority?sslmode=disable"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("durable_postgres_configured", failed)

    def test_production_postgres_rejects_invalid_keyword_dsn_port(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_POSTGRES_DSN"] = "host=loopos.example port=not-a-number dbname=authority sslmode=require"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("durable_postgres_configured", failed)

    def test_production_postgres_accepts_quoted_keyword_dsn_port(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_POSTGRES_DSN"] = "host=loopos.example port='5432' dbname=authority sslmode=require"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertTrue(next(check for check in report["checks"] if check["name"] == "durable_postgres_configured")["passed"])
        self.assertFalse(next(check for check in report["checks"] if check["name"] == "credential_injection_broker")["passed"])

    def test_unallowlisted_connector_credential_fails_closed(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_CONNECTOR_BEARER_TOKENS_JSON"] = '{"unapproved.example.com":"server-side-token"}'
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("connector_credentials_allowlisted", failed)

    def test_static_connector_credential_fails_closed_until_a_broker_is_integrated(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_CONNECTOR_BEARER_TOKENS_JSON"] = '{"api.example.com":"server-side-token"}'
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("credential_injection_broker", failed)

    def test_production_webhook_secrets_must_be_tenant_scoped_and_long_enough(self) -> None:
        for raw in (
            '{"github":"short-webhook-secret"}',
            '{"tenant-api:github":"short-webhook-secret"}',
            '{":github":"webhook-secret-that-is-at-least-thirty-two-bytes"}',
            '{"tenant-api:unknown":"webhook-secret-that-is-at-least-thirty-two-bytes"}',
        ):
            with self.subTest(raw=raw):
                environment = complete_production_environment()
                environment["LOOPOS_WEBHOOK_SECRETS_JSON"] = raw
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                self.assertEqual(report["configuration_verdict"], "NO_GO")
                failed = {check["name"] for check in report["checks"] if not check["passed"]}
                self.assertIn("settings_loaded", failed)

    def test_malformed_http_allowlist_fails_closed(self) -> None:
        environment = complete_production_environment()
        environment.update({
            "LOOPOS_ALLOWED_HTTP_HOSTS": "api.example.com/path",
            "LOOPOS_CONNECTOR_BEARER_TOKENS_JSON": "{}",
            "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS": "api.example.com/path",
            "VITE_LOOPOS_LLM_ENDPOINT": "",
        })
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertTrue({"outbound_policy_evidence_configured", "ui_outbound_binding_matches_authority"} & failed)

    def test_mismatched_ui_and_authority_bindings_fail_closed(self) -> None:
        environment = complete_production_environment()
        environment.update({
            "VITE_LOOPOS_RETENTION_POLICY_URL": "https://wrong.example/retention",
            "VITE_LOOPOS_SUPPORT_CONTACT": "wrong-team@example.com",
            "VITE_LOOPOS_OUTBOUND_POLICY_MODE": "deny_all",
            "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS": "unapproved.example.com",
            "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL": "https://wrong.example/restore.json",
        })
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("ui_retention_binding_matches_authority", failed)
        self.assertIn("ui_support_binding_matches_authority", failed)
        self.assertIn("ui_outbound_binding_matches_authority", failed)
        self.assertIn("ui_backup_restore_binding_matches_authority", failed)
        self.assertIn("ui_optional_endpoints_constrained", failed)

    def test_insecure_or_unallowlisted_optional_ui_endpoint_fails_closed(self) -> None:
        environment = complete_production_environment()
        environment["VITE_LOOPOS_LLM_ENDPOINT"] = "http://api.example.com/loopos"
        with patch.dict("os.environ", environment, clear=True):
            insecure = production_configuration_report()

        environment["VITE_LOOPOS_LLM_ENDPOINT"] = "https://unknown.example.com/loopos"
        with patch.dict("os.environ", environment, clear=True):
            unallowlisted = production_configuration_report()

        for report in (insecure, unallowlisted):
            failed = {check["name"] for check in report["checks"] if not check["passed"]}
            self.assertEqual(report["configuration_verdict"], "NO_GO")
            self.assertIn("ui_optional_endpoints_constrained", failed)

    def test_protocol_relative_or_backslash_normalized_authority_url_fails_closed(self) -> None:
        for authority_url in ("//untrusted.example/api", "/\\\\untrusted.example/api"):
            environment = complete_production_environment()
            environment["VITE_LOOPOS_AUTHORITY_URL"] = authority_url
            with patch.dict("os.environ", environment, clear=True):
                report = production_configuration_report()

            failed = {check["name"] for check in report["checks"] if not check["passed"]}
            self.assertEqual(report["configuration_verdict"], "NO_GO")
            self.assertIn("enterprise_ui_contract_declared", failed)

    def test_remote_authority_requires_a_browser_host_allowlist(self) -> None:
        environment = complete_production_environment()
        environment.update({
            "VITE_LOOPOS_AUTHORITY_URL": "https://authority.example.com/api",
            "VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST": "other.example.com",
        })
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertEqual(report["configuration_verdict"], "NO_GO")
        self.assertIn("enterprise_ui_contract_declared", failed)

    def test_remote_authority_rejects_local_or_non_global_ip_hosts(self) -> None:
        for authority_url, host in (
            ("https://127.0.0.1/api", "127.0.0.1"),
            ("https://100.64.0.1/api", "100.64.0.1"),
        ):
            with self.subTest(authority_url=authority_url):
                environment = complete_production_environment()
                environment.update({
                    "VITE_LOOPOS_AUTHORITY_URL": authority_url,
                    "VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST": host,
                })
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                failed = {check["name"] for check in report["checks"] if not check["passed"]}
                self.assertEqual(report["configuration_verdict"], "NO_GO")
                self.assertIn("enterprise_ui_contract_declared", failed)

    def test_same_origin_authority_must_target_vercel_api_route(self) -> None:
        for authority_url in ("/wrong-route", "/api/v1"):
            with self.subTest(authority_url=authority_url):
                environment = complete_production_environment()
                environment["VITE_LOOPOS_AUTHORITY_URL"] = authority_url
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                failed = {check["name"] for check in report["checks"] if not check["passed"]}
                self.assertEqual(report["configuration_verdict"], "NO_GO")
                self.assertIn("enterprise_ui_contract_declared", failed)

    def test_remote_authority_must_target_api_route(self) -> None:
        for authority_url in (
            "https://authority.example.com/wrong-route",
            "https://authority.example.com/api/v1",
        ):
            with self.subTest(authority_url=authority_url):
                environment = complete_production_environment()
                environment.update({
                    "VITE_LOOPOS_AUTHORITY_URL": authority_url,
                    "VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST": "authority.example.com",
                })
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                failed = {check["name"] for check in report["checks"] if not check["passed"]}
                self.assertEqual(report["configuration_verdict"], "NO_GO")
                self.assertIn("enterprise_ui_contract_declared", failed)

    def test_malformed_or_credential_bearing_production_urls_fail_closed(self) -> None:
        cases = [
            (
                "audit_anchor",
                {"LOOPOS_AUDIT_ANCHOR_URL": "https://user:pass@audit.example.com/loopos/events"},
                "settings_loaded",
            ),
            (
                "cors_origin",
                {"LOOPOS_CORS_ORIGINS": "https://console.example.com\\\\evil.example"},
                "production_cors_restricted",
            ),
            (
                "restore_reference",
                {
                    "LOOPOS_BACKUP_RESTORE_EVIDENCE_URL": "https://evidence.example.com\\\\evil.example/restore.json",
                    "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL": "https://evidence.example.com\\\\evil.example/restore.json",
                },
                "settings_loaded",
            ),
        ]
        for name, overrides, failed_name in cases:
            with self.subTest(name=name):
                environment = complete_production_environment()
                environment.update(overrides)
                with patch.dict("os.environ", environment, clear=True):
                    report = production_configuration_report()

                failed = {check["name"] for check in report["checks"] if not check["passed"]}
                self.assertEqual(report["configuration_verdict"], "NO_GO")
                self.assertIn(failed_name, failed)

    def test_malformed_oidc_port_fails_closed_during_settings_load(self) -> None:
        environment = complete_production_environment()
        environment["LOOPOS_OIDC_ISSUER"] = "https://identity.example.com:bad/"
        with patch.dict("os.environ", environment, clear=True):
            report = production_configuration_report()

        self.assertEqual(report["configuration_verdict"], "NO_GO")
        failed = {check["name"] for check in report["checks"] if not check["passed"]}
        self.assertIn("settings_loaded", failed)

    def test_cli_writes_non_secret_report_and_sets_exit_code(self) -> None:
        environment = complete_production_environment()
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "production-configuration.json"
            stdout = StringIO()
            with patch.dict("os.environ", environment, clear=True), redirect_stdout(stdout):
                exit_code = main(["--output", str(output)])

            self.assertEqual(exit_code, 1)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["configuration_verdict"], "NO_GO")
            self.assertNotIn(environment["LOOPOS_SESSION_HMAC_SECRET"], stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
