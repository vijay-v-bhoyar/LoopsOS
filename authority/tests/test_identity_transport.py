from __future__ import annotations

import base64
import ipaddress
import json
import os
import socket
import ssl
import tempfile
import threading
import time
import urllib.error
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import jwt
import loopos_authority.identity_transport as identity_transport
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from loopos_authority.identity import OIDCIdentityVerifier
from loopos_authority.identity_transport import (
    BoundedJwksClient,
    _BoundedDnsResolver,
    MAX_JWKS_RESPONSE_BYTES,
    UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS,
    _validated_jwks_addresses,
)


def _b64url_integer(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class IdentityTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.temp_path = Path(self.tempdir.name)
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = self.private_key.public_key().public_numbers()
        self.jwk = {
            "kty": "RSA",
            "use": "sig",
            "kid": "transport-test-key",
            "alg": "RS256",
            "n": _b64url_integer(public.n),
            "e": _b64url_integer(public.e),
        }
        self.counts = {"jwks": 0, "private": 0}
        self.redirect_to_private = False

        outer = self

        class PrivateHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                outer.counts["private"] += 1
                body = json.dumps({"keys": [outer.jwk]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args) -> None:
                return

        class JwksHandler(BaseHTTPRequestHandler):
            destination = ""

            def do_GET(self) -> None:
                outer.counts["jwks"] += 1
                if outer.redirect_to_private:
                    self.send_response(302)
                    self.send_header("Location", self.destination)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = json.dumps({"keys": [outer.jwk]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args) -> None:
                return

        self.private_server = ThreadingHTTPServer(("127.0.0.1", 0), PrivateHandler)
        self.addCleanup(self._stop_server, self.private_server)
        threading.Thread(target=self.private_server.serve_forever, daemon=True).start()
        JwksHandler.destination = f"http://127.0.0.1:{self.private_server.server_port}/internal-jwks"

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, hashes.SHA256())
        )
        self.cert_path = self.temp_path / "jwks-cert.pem"
        key_path = self.temp_path / "jwks-key.pem"
        self.cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        self.jwks_server = ThreadingHTTPServer(("127.0.0.1", 0), JwksHandler)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(str(self.cert_path), str(key_path))
        self.jwks_server.socket = server_context.wrap_socket(self.jwks_server.socket, server_side=True)
        self.addCleanup(self._stop_server, self.jwks_server)
        threading.Thread(target=self.jwks_server.serve_forever, daemon=True).start()
        self.jwks_url = f"https://localhost:{self.jwks_server.server_port}/jwks"

    @staticmethod
    def _stop_server(server: ThreadingHTTPServer) -> None:
        server.shutdown()
        server.server_close()

    def _verifier(self) -> OIDCIdentityVerifier:
        with patch.dict(os.environ, {"SSL_CERT_FILE": str(self.cert_path)}):
            return OIDCIdentityVerifier(
                issuer="https://issuer.example/",
                audience="loopsos-transport-test",
                jwks_url=self.jwks_url,
                tenant_claim="tenant_id",
                role_claim="groups",
                role_mapping={"loopos-approvers": "Approver"},
                allow_local_jwks=True,
            )

    def _assertion(self, *, kid: str = "transport-test-key") -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "https://issuer.example/",
                "aud": "loopsos-transport-test",
                "sub": "transport-test-user",
                "iat": now,
                "exp": now + 120,
                "tenant_id": "transport-test-tenant",
                "groups": ["loopos-approvers"],
            },
            self.private_key,
            algorithm="RS256",
            headers={"kid": kid},
        )

    def test_verifies_a_key_from_the_exact_local_jwks_endpoint_and_ignores_proxy_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SSL_CERT_FILE": str(self.cert_path),
                "HTTPS_PROXY": "http://127.0.0.1:9",
                "ALL_PROXY": "http://127.0.0.1:9",
                "NO_PROXY": "",
            },
        ):
            verifier = OIDCIdentityVerifier(
                issuer="https://issuer.example/",
                audience="loopsos-transport-test",
                jwks_url=self.jwks_url,
                tenant_claim="tenant_id",
                role_claim="groups",
                role_mapping={"loopos-approvers": "Approver"},
                allow_local_jwks=True,
            )
            actor = verifier.verify(self._assertion())

        self.assertEqual(actor.user_id, "transport-test-user")
        self.assertEqual(self.counts["jwks"], 1)
        self.assertEqual(self.counts["private"], 0)

    def test_rejects_redirect_to_private_destination(self) -> None:
        self.redirect_to_private = True
        verifier = self._verifier()

        with self.assertRaises(PyJWKClientConnectionError):
            verifier.verify(self._assertion())

        self.assertEqual(self.counts["jwks"], 1)
        self.assertEqual(self.counts["private"], 0)

    def test_rejects_mixed_public_and_private_dns_answers(self) -> None:
        answers = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ]
        with patch("loopos_authority.identity_transport.socket.getaddrinfo", return_value=answers):
            with self.assertRaisesRegex(OSError, "outside the approved network policy"):
                _validated_jwks_addresses(
                    "identity.example",
                    443,
                    allowed_networks=(),
                    allow_localhost=False,
                )

    def test_explicit_private_jwks_cidr_is_accepted_and_strictly_parsed(self) -> None:
        answers = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.23.4.5", 443))]
        with patch("loopos_authority.identity_transport.socket.getaddrinfo", return_value=answers):
            selected = _validated_jwks_addresses(
                "identity.internal",
                443,
                allowed_networks=(ipaddress.ip_network("10.23.0.0/16"),),
                allow_localhost=False,
            )
        self.assertEqual(selected[0][4][0], "10.23.4.5")

    def test_stalled_jwks_dns_fails_closed_at_a_hard_deadline(self) -> None:
        resolver_started = threading.Event()
        release_resolver = threading.Event()
        resolver_returned = threading.Event()

        def stalled_resolver(*_args, **_kwargs):
            resolver_started.set()
            release_resolver.wait(1)
            resolver_returned.set()
            return []

        started_at = time.monotonic()
        try:
            with patch("loopos_authority.identity_transport.socket.getaddrinfo", stalled_resolver):
                with self.assertRaisesRegex(OSError, "DNS resolution timed out"):
                    _validated_jwks_addresses(
                        "stalled.identity.example",
                        443,
                        allowed_networks=(),
                        allow_localhost=False,
                        resolution_timeout=0.05,
                    )
                elapsed = time.monotonic() - started_at
                self.assertTrue(resolver_started.is_set())
                self.assertLess(elapsed, 0.5)
        finally:
            release_resolver.set()
        self.assertTrue(resolver_returned.wait(1))

    def test_jwks_client_wraps_a_stalled_dns_deadline_as_a_safe_fetch_failure(self) -> None:
        client = BoundedJwksClient("https://stalled.identity.example/jwks", timeout=0.05)
        resolver_started = threading.Event()
        release_resolver = threading.Event()
        resolver_returned = threading.Event()

        def stalled_resolver(*_args, **_kwargs):
            resolver_started.set()
            release_resolver.wait(1)
            resolver_returned.set()
            return []

        started_at = time.monotonic()
        try:
            with patch("loopos_authority.identity_transport.socket.getaddrinfo", stalled_resolver):
                with self.assertRaisesRegex(PyJWKClientConnectionError, "could not be fetched safely"):
                    client.fetch_data()
                elapsed = time.monotonic() - started_at
                self.assertTrue(resolver_started.is_set())
                self.assertLess(elapsed, 0.5)
        finally:
            release_resolver.set()
        self.assertTrue(resolver_returned.wait(1))

    def test_jwks_dns_resolver_bounds_waiting_work_when_system_dns_stalls(self) -> None:
        resolver = _BoundedDnsResolver(workers=1, queue_size=1)
        resolver_started = threading.Event()
        release_resolver = threading.Event()
        results: dict[str, object] = {}
        expected = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))]
        calls = 0

        def partly_stalled_resolver(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                resolver_started.set()
                release_resolver.wait(1)
            return expected

        def run_lookup(name: str) -> None:
            try:
                results[name] = resolver.resolve(name, 443, timeout=1)
            except BaseException as error:
                results[name] = error

        with patch("loopos_authority.identity_transport.socket.getaddrinfo", partly_stalled_resolver):
            first = threading.Thread(target=run_lookup, args=("first.identity.example",), daemon=True)
            first.start()
            self.assertTrue(resolver_started.wait(1))

            second = threading.Thread(target=run_lookup, args=("second.identity.example",), daemon=True)
            second.start()
            deadline = time.monotonic() + 0.5
            while resolver._queue.qsize() != 1 and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(resolver._queue.qsize(), 1)
            with self.assertRaisesRegex(OSError, "resolver is at capacity"):
                resolver.resolve("third.identity.example", 443, timeout=1)

            release_resolver.set()
            first.join(timeout=1)
            second.join(timeout=1)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(results["first.identity.example"], expected)
        self.assertEqual(results["second.identity.example"], expected)

    def test_jwks_dns_resolver_is_recreated_after_a_worker_process_fork(self) -> None:
        original_resolver = identity_transport._DNS_RESOLVER
        original_lock = identity_transport._DNS_RESOLVER_LOCK
        original_pid = identity_transport._DNS_RESOLVER_PID
        expected = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))]

        class ResolverStub:
            def resolve(self, _hostname: str, _port: int, *, timeout: float):
                self.timeout = timeout
                return expected

        replacement = ResolverStub()
        try:
            with patch.object(identity_transport, "_BoundedDnsResolver", return_value=replacement) as create_resolver:
                with patch.object(identity_transport.os, "getpid", return_value=original_pid + 1000):
                    selected = identity_transport._resolve_jwks_hostname(
                        "identity.example",
                        443,
                        timeout=0.5,
                    )
                create_resolver.assert_called_once_with(
                    workers=identity_transport.JWKS_DNS_RESOLVER_WORKERS,
                    queue_size=identity_transport.JWKS_DNS_RESOLVER_QUEUE_SIZE,
                )
                self.assertEqual(replacement.timeout, 0.5)
                self.assertEqual(selected, expected)
        finally:
            identity_transport._DNS_RESOLVER = original_resolver
            identity_transport._DNS_RESOLVER_LOCK = original_lock
            identity_transport._DNS_RESOLVER_PID = original_pid

    def test_private_cidr_must_be_network_aligned(self) -> None:
        with self.assertRaisesRegex(ValueError, "endpoint or approved network is invalid"):
            BoundedJwksClient(self.jwks_url, allowed_networks=("10.23.4.5/16",))

    def test_unknown_kids_cannot_force_repeated_jwks_fetches(self) -> None:
        verifier = self._verifier()
        for _ in range(2):
            with self.assertRaises(PyJWKClientError):
                verifier.verify(self._assertion(kid="attacker-controlled-kid"))
        self.assertEqual(self.counts["jwks"], 1)

    def test_unknown_kid_can_refresh_after_cooldown_for_key_rotation(self) -> None:
        verifier = self._verifier()
        client = verifier.jwks_client
        with self.assertRaises(PyJWKClientError):
            verifier.verify(self._assertion(kid="rotated-key"))

        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = self.private_key.public_key().public_numbers()
        self.jwk = {
            "kty": "RSA",
            "use": "sig",
            "kid": "rotated-key",
            "alg": "RS256",
            "n": _b64url_integer(public.n),
            "e": _b64url_integer(public.e),
        }
        client._last_jwks_fetch_attempt_at = time.monotonic() - UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS - 1

        actor = verifier.verify(self._assertion(kid="rotated-key"))
        self.assertEqual(actor.user_id, "transport-test-user")
        self.assertEqual(self.counts["jwks"], 2)

    def test_caps_jwks_response_bytes(self) -> None:
        client = BoundedJwksClient(self.jwks_url, allow_localhost=True)

        class OversizedResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size: int) -> bytes:
                self.requested_bytes = size
                return b"x" * size

        response = OversizedResponse()
        with patch.object(client._opener, "open", return_value=response):
            with self.assertRaisesRegex(PyJWKClientConnectionError, "size limit"):
                client.fetch_data()
        self.assertEqual(response.requested_bytes, MAX_JWKS_RESPONSE_BYTES + 1)

    def test_rejects_invalid_jwks_shapes_before_caching(self) -> None:
        class SyntheticResponse:
            def __init__(self, body: bytes) -> None:
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                return self.body

        invalid_payloads = (
            b"[]",
            b"{not-json",
            b'{"keys": []}',
            b'{"keys": [{"kid": "broken", "use": "sig"}]}',
            b'{"keys": [{"kty": "RSA", "kid": "encryption-only", "use": "enc", "n": "AQAB", "e": "AQAB"}]}',
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                client = BoundedJwksClient(self.jwks_url, allow_localhost=True)
                response = SyntheticResponse(payload)
                with patch.object(client._opener, "open", return_value=response):
                    with self.assertRaises(PyJWKClientConnectionError):
                        client.fetch_data()
                self.assertIsNone(client.jwk_set_cache.get())

    def test_invalid_refresh_preserves_last_good_signing_key(self) -> None:
        class SyntheticResponse:
            def __init__(self, body: bytes) -> None:
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                return self.body

        client = BoundedJwksClient(self.jwks_url, allow_localhost=True)
        valid = json.dumps({"keys": [self.jwk]}).encode("utf-8")
        invalid = b'{"keys": []}'
        with patch.object(
            client._opener,
            "open",
            side_effect=(SyntheticResponse(valid), SyntheticResponse(invalid)),
        ) as opened:
            last_good = client.fetch_data()
            client._last_jwks_fetch_attempt_at = (
                time.monotonic() - UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS - 1
            )
            with self.assertRaises(PyJWKClientConnectionError):
                client.fetch_data()

            self.assertEqual(client.jwk_set_cache.get(), last_good)
            self.assertEqual(
                client.get_signing_keys()[0].key_id,
                "transport-test-key",
            )
            self.assertEqual(opened.call_count, 2)

    def test_failed_jwks_endpoint_cannot_be_hit_on_every_unknown_kid(self) -> None:
        client = BoundedJwksClient(self.jwks_url, allow_localhost=True)
        with patch.object(client._opener, "open", side_effect=urllib.error.URLError("synthetic outage")) as opened:
            with self.assertRaises(PyJWKClientConnectionError):
                client.get_signing_key("attacker-controlled-kid")
            with self.assertRaises(PyJWKClientConnectionError):
                client.get_signing_key("attacker-controlled-kid")
        self.assertEqual(opened.call_count, 1)


if __name__ == "__main__":
    unittest.main()
