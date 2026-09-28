"""Constrained HTTPS transport for the configured OIDC JWKS endpoint.

The configured identity provider is trusted configuration, but its network
path still needs destination controls. This client rejects redirects and
ambient proxies, validates DNS answers before dialing a numeric address, and
bounds the response size.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import math
import os
import queue
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWKError, PyJWKSetError


MAX_JWKS_RESPONSE_BYTES = 256_000
MAX_DNS_ANSWERS = 32
MAX_JWKS_DNS_RESOLUTION_SECONDS = 2.0
JWKS_DNS_RESOLVER_WORKERS = 2
JWKS_DNS_RESOLVER_QUEUE_SIZE = 4
UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS = 5.0


class _DnsLookupJob:
    def __init__(self, hostname: str, port: int) -> None:
        self.hostname = hostname
        self.port = port
        self.done = threading.Event()
        self.cancelled = threading.Event()
        self.addresses: list[tuple[int, int, int, str, tuple[Any, ...]]] | None = None
        self.error: Exception | None = None


class _BoundedDnsResolver:
    """Resolve names on a fixed daemon pool with bounded admission and waits.

    Python cannot cancel a system getaddrinfo call. A timed-out call may occupy
    one worker until the OS resolver returns, so both worker and waiting-task
    counts are fixed and saturation rejects new work closed.
    """

    def __init__(self, *, workers: int, queue_size: int) -> None:
        if workers < 1 or queue_size < 1:
            raise ValueError("JWKS DNS resolver limits must be positive.")
        self._queue: queue.Queue[_DnsLookupJob] = queue.Queue(maxsize=queue_size)
        for index in range(workers):
            threading.Thread(
                target=self._worker,
                name=f"loopos-jwks-dns-{index + 1}",
                daemon=True,
            ).start()

    def _worker(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job.cancelled.is_set():
                    continue
                try:
                    job.addresses = socket.getaddrinfo(
                        job.hostname,
                        job.port,
                        type=socket.SOCK_STREAM,
                    )
                except Exception as error:
                    job.error = error
                finally:
                    job.done.set()
            finally:
                self._queue.task_done()

    def resolve(
        self,
        hostname: str,
        port: int,
        *,
        timeout: float,
    ) -> list[tuple[int, int, int, str, tuple[Any, ...]]]:
        if not math.isfinite(timeout) or timeout <= 0:
            raise OSError("OIDC JWKS DNS resolution timeout must be finite and positive.")
        job = _DnsLookupJob(hostname, port)
        try:
            self._queue.put_nowait(job)
        except queue.Full as error:
            raise OSError("OIDC JWKS DNS resolver is at capacity.") from error

        if not job.done.wait(timeout) and not job.done.is_set():
            job.cancelled.set()
            raise OSError("OIDC JWKS DNS resolution timed out.")
        if job.error is not None:
            raise job.error
        if job.addresses is None:
            raise OSError("OIDC JWKS DNS resolver returned no result.")
        return job.addresses


_DNS_RESOLVER: _BoundedDnsResolver | None = None
_DNS_RESOLVER_LOCK = threading.Lock()
_DNS_RESOLVER_PID = os.getpid()


def _reset_dns_resolver_after_fork() -> None:
    """Discard inherited queue state because daemon workers do not survive fork."""
    global _DNS_RESOLVER, _DNS_RESOLVER_LOCK, _DNS_RESOLVER_PID
    _DNS_RESOLVER = None
    _DNS_RESOLVER_LOCK = threading.Lock()
    _DNS_RESOLVER_PID = os.getpid()


_register_at_fork = getattr(os, "register_at_fork", None)
if _register_at_fork is not None:
    _register_at_fork(after_in_child=_reset_dns_resolver_after_fork)


def _resolve_jwks_hostname(
    hostname: str,
    port: int,
    *,
    timeout: float,
) -> list[tuple[int, int, int, str, tuple[Any, ...]]]:
    global _DNS_RESOLVER, _DNS_RESOLVER_PID
    current_pid = os.getpid()
    with _DNS_RESOLVER_LOCK:
        if _DNS_RESOLVER is None or _DNS_RESOLVER_PID != current_pid:
            _DNS_RESOLVER = _BoundedDnsResolver(
                workers=JWKS_DNS_RESOLVER_WORKERS,
                queue_size=JWKS_DNS_RESOLVER_QUEUE_SIZE,
            )
            _DNS_RESOLVER_PID = current_pid
        resolver = _DNS_RESOLVER
    return resolver.resolve(hostname, port, timeout=timeout)


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _address_is_global(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and (
        address.ipv4_mapped is not None
        or address.sixtofour is not None
        or address.teredo is not None
        or address in ipaddress.IPv6Network("64:ff9b::/96")
        or address in ipaddress.IPv6Network("64:ff9b:1::/48")
    ):
        return False
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


def _validated_jwks_addresses(
    hostname: str,
    port: int,
    *,
    allowed_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    allow_localhost: bool,
    resolution_timeout: float = MAX_JWKS_DNS_RESOLUTION_SECONDS,
) -> list[tuple[int, int, int, str, tuple[Any, ...]]]:
    normalized = hostname.lower().rstrip(".")
    if allow_localhost and normalized == "localhost":
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))]
    if allow_localhost and normalized == "127.0.0.1":
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))]
    if allow_localhost and normalized == "::1":
        return [(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("::1", port, 0, 0))]

    try:
        literal = ipaddress.ip_address(normalized)
    except ValueError:
        answers = _resolve_jwks_hostname(
            normalized,
            port,
            timeout=min(resolution_timeout, MAX_JWKS_DNS_RESOLUTION_SECONDS),
        )
    else:
        family = socket.AF_INET6 if literal.version == 6 else socket.AF_INET
        sockaddr: tuple[Any, ...] = (str(literal), port, 0, 0) if literal.version == 6 else (str(literal), port)
        answers = [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)]

    unique: list[tuple[int, int, int, str, tuple[Any, ...]]] = []
    seen: set[tuple[int, str]] = set()
    for family, socktype, proto, canonname, sockaddr in answers:
        address_text = str(sockaddr[0]).split("%", 1)[0]
        address = ipaddress.ip_address(address_text)
        if (family, address_text) in seen:
            continue
        seen.add((family, address_text))
        explicitly_allowed = any(
            address.version == network.version and address in network
            for network in allowed_networks
        )
        if not _address_is_global(address) and not explicitly_allowed:
            raise OSError("OIDC JWKS DNS contains an address outside the approved network policy.")
        unique.append((family, socktype, proto, canonname, sockaddr))
        if len(unique) > MAX_DNS_ANSWERS:
            raise OSError("OIDC JWKS DNS returned too many addresses.")
    if not unique:
        raise OSError("OIDC JWKS hostname did not resolve to an approved address.")
    return unique


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        *,
        configured_host: str,
        configured_port: int,
        allowed_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
        allow_localhost: bool,
        **kwargs: Any,
    ) -> None:
        self._configured_host = configured_host
        self._configured_port = configured_port
        self._allowed_networks = allowed_networks
        self._allow_localhost = allow_localhost
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        if self._tunnel_host is not None:
            raise OSError("OIDC JWKS proxy tunnels are not supported.")
        hostname = self.host.lower().rstrip(".")
        if hostname != self._configured_host or self.port != self._configured_port:
            raise OSError("OIDC JWKS request origin differs from the configured endpoint.")
        addresses = _validated_jwks_addresses(
            hostname,
            self.port,
            allowed_networks=self._allowed_networks,
            allow_localhost=self._allow_localhost,
            resolution_timeout=(
                MAX_JWKS_DNS_RESOLUTION_SECONDS
                if self.timeout is None or self.timeout is socket._GLOBAL_DEFAULT_TIMEOUT
                else min(float(self.timeout), MAX_JWKS_DNS_RESOLUTION_SECONDS)
            ),
        )

        last_error: OSError | None = None
        for family, socktype, proto, _canonname, sockaddr in addresses:
            sock = socket.socket(family, socktype, proto)
            try:
                sock.settimeout(self.timeout)
                if self.source_address:
                    sock.bind(self.source_address)
                sock.connect(sockaddr)
                # The socket connects to a validated numeric sockaddr. TLS
                # authenticates the original configured host and SNI name.
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as error:
                last_error = error
                sock.close()
        raise last_error or OSError("OIDC JWKS endpoint has no usable address.")


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(
        self,
        *,
        configured_host: str,
        configured_port: int,
        allowed_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
        allow_localhost: bool,
    ) -> None:
        super().__init__(context=ssl.create_default_context())
        self.configured_host = configured_host
        self.configured_port = configured_port
        self.allowed_networks = allowed_networks
        self.allow_localhost = allow_localhost

    def https_open(self, req):
        connection = lambda host, **kwargs: _PinnedHTTPSConnection(
            host,
            configured_host=self.configured_host,
            configured_port=self.configured_port,
            allowed_networks=self.allowed_networks,
            allow_localhost=self.allow_localhost,
            **kwargs,
        )
        return self.do_open(connection, req, context=self._context)


class BoundedJwksClient(jwt.PyJWKClient):
    """PyJWT key cache with a pinned, non-redirecting, bounded fetch path."""

    def __init__(
        self,
        uri: str,
        *,
        allowed_networks: tuple[str, ...] = (),
        allow_localhost: bool = False,
        timeout: float = 5,
        lifespan: float = 300,
        cache_jwk_set: bool = True,
    ) -> None:
        parsed = urlsplit(uri)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("OIDC JWKS URL must use HTTPS and include a hostname.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or "\\" in uri:
            raise ValueError("OIDC JWKS URL must not contain credentials, query, fragment, or backslash.")
        try:
            port = parsed.port or 443
            networks = tuple(ipaddress.ip_network(item, strict=True) for item in allowed_networks)
        except ValueError as error:
            raise ValueError("OIDC JWKS endpoint or approved network is invalid.") from error
        if any(
            not network.is_private
            or network.is_loopback
            or network.is_link_local
            or network.is_multicast
            or network.is_reserved
            for network in networks
        ):
            raise ValueError("OIDC JWKS approved networks must be private unicast CIDRs.")

        super().__init__(uri, cache_jwk_set=cache_jwk_set, lifespan=lifespan, timeout=timeout)
        self._configured_host = parsed.hostname.lower().rstrip(".")
        self._allowed_networks = networks
        self._allow_localhost = allow_localhost
        self._unknown_kid_refresh_lock = threading.Lock()
        self._jwks_fetch_lock = threading.Lock()
        self._last_jwks_fetch_attempt_at: float | None = None
        # ProxyHandler({}) deliberately ignores HTTPS_PROXY/ALL_PROXY inherited
        # from the process environment. The endpoint host is the sole authority.
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _RejectRedirects(),
            _PinnedHTTPSHandler(
                configured_host=self._configured_host,
                configured_port=port,
                allowed_networks=self._allowed_networks,
                allow_localhost=self._allow_localhost,
            ),
        )

    def fetch_data(self) -> Any:
        with self._jwks_fetch_lock:
            now = time.monotonic()
            if (
                self._last_jwks_fetch_attempt_at is not None
                and now - self._last_jwks_fetch_attempt_at < UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS
            ):
                cached = self.jwk_set_cache.get() if self.jwk_set_cache is not None else None
                if cached is not None:
                    return cached
                raise PyJWKClientConnectionError("OIDC JWKS fetch is temporarily rate limited.")
            self._last_jwks_fetch_attempt_at = now
            request = urllib.request.Request(url=self.uri, headers=self.headers)
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    data = response.read(MAX_JWKS_RESPONSE_BYTES + 1)
                if len(data) > MAX_JWKS_RESPONSE_BYTES:
                    raise PyJWKClientConnectionError("OIDC JWKS response exceeds the configured size limit.")
                jwk_set = json.loads(data)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                raise PyJWKClientConnectionError("OIDC JWKS endpoint could not be fetched safely.") from error
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise PyJWKClientConnectionError("OIDC JWKS endpoint returned invalid JSON.") from error

            # Do not let an invalid response replace a usable cached key set.
            # The configured IdP is trusted configuration, but a broken or
            # compromised response must not create a cache-based auth outage.
            try:
                if not isinstance(jwk_set, dict) or not isinstance(jwk_set.get("keys"), list):
                    raise ValueError("JWKS payload must be an object with a keys array.")
                parsed = jwt.PyJWKSet.from_dict(jwk_set)
                signing_keys = [
                    key
                    for key in parsed.keys
                    if key.public_key_use in (None, "sig") and bool(key.key_id)
                ]
                if not signing_keys:
                    raise ValueError("JWKS payload contains no usable signing keys.")
            except (PyJWKError, PyJWKSetError, TypeError, ValueError, KeyError, UnicodeDecodeError) as error:
                raise PyJWKClientConnectionError("OIDC JWKS endpoint returned an invalid signing-key set.") from error

            if self.jwk_set_cache is not None:
                self.jwk_set_cache.put(jwk_set)
            return jwk_set

    def get_signing_key(self, kid: str):
        signing_keys = self.get_signing_keys()
        for signing_key in signing_keys:
            if signing_key.key_id == kid:
                return signing_key

        # PyJWT normally forces a fresh download for every unknown kid. Since
        # the kid is attacker-controlled before signature verification, bound
        # that network amplification while still allowing key rotation after a
        # short fail-closed cooldown.
        with self._unknown_kid_refresh_lock:
            signing_keys = self.get_signing_keys()
            for signing_key in signing_keys:
                if signing_key.key_id == kid:
                    return signing_key
            last_attempt = self._last_jwks_fetch_attempt_at
            if (
                last_attempt is not None
                and time.monotonic() - last_attempt < UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS
            ):
                raise PyJWKClientError("OIDC JWKS unknown-key refresh is temporarily rate limited.")
            signing_keys = self.get_signing_keys(refresh=True)
            for signing_key in signing_keys:
                if signing_key.key_id == kid:
                    return signing_key
        raise PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
