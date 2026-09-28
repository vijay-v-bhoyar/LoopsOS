"""Direct connector transport: authorize DNS results at the TCP boundary.

The URL remains the original origin for TLS verification, SNI and HTTP Host.
Only the socket destination becomes a validated numeric address. No ambient
proxy or second hostname lookup is permitted to select that destination.
"""
from __future__ import annotations

from contextlib import contextmanager
import ipaddress
import socket
from typing import Any

import anyio
import httpcore
import httpx

from .network_policy import is_public_global_address


class ConnectorAddressDenied(httpx.TransportError):
    """A terminal policy denial, deliberately not a retryable NetworkError."""


def global_address(address: str) -> bool:
    return is_public_global_address(address)


class ConnectorNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, allowed_hosts: tuple[str, ...], allow_dev_auth: bool,
                 backend: httpcore.AsyncNetworkBackend | None = None):
        self.allowed_hosts = frozenset(allowed_hosts)
        self.allow_dev_auth = allow_dev_auth
        self.backend = backend if backend is not None else httpcore.AnyIOBackend()

    async def connect_tcp(self, host: str, port: int, timeout: float | None = None,
                          local_address: str | None = None, socket_options: Any = None):
        hostname = host.lower()
        if hostname not in self.allowed_hosts:
            raise ConnectorAddressDenied('Connector socket host is not allowlisted.')
        local_development = self.allow_dev_auth and hostname in {'localhost', '127.0.0.1'}
        try:
            # One shared deadline covers resolution and every candidate. A long
            # DNS answer list must not multiply the configured connect timeout.
            with anyio.fail_after(timeout):
                if local_development:
                    addresses = ['127.0.0.1']
                else:
                    try:
                        literal = ipaddress.ip_address(hostname)
                    except ValueError:
                        answers = await anyio.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
                        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
                    else:
                        addresses = [str(literal)]
                    if not addresses or any(not global_address(address) for address in addresses):
                        raise ConnectorAddressDenied('Connector DNS must contain only global addresses.')
                last_error = None
                for address in addresses:
                    try:
                        return await self.backend.connect_tcp(
                            address, port, timeout=timeout, local_address=local_address,
                            socket_options=socket_options,
                        )
                    except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                        # Retry another validated address only before any TLS or
                        # HTTP bytes; never fall back to the unresolved hostname.
                        last_error = error
                raise last_error or httpcore.ConnectError('Connector has no usable address.')
        except TimeoutError as error:
            raise httpcore.ConnectTimeout('Connector resolution/connect deadline exceeded.') from error
        except socket.gaierror as error:
            raise httpcore.ConnectError('Connector hostname cannot be resolved.') from error

    async def connect_unix_socket(self, path: str, timeout: float | None = None,
                                  socket_options: Any = None):
        raise ConnectorAddressDenied('Connector Unix sockets are not supported.')

    async def sleep(self, seconds: float) -> None:
        await anyio.sleep(seconds)


@contextmanager
def _http_errors():
    # Public exception types preserve the ToolRegistry retry/outcome contract.
    try:
        yield
    except (httpcore.TimeoutException, httpcore.NetworkError, httpcore.ProtocolError,
            httpcore.ProxyError, httpcore.UnsupportedProtocol) as error:
        for name in ('ConnectTimeout', 'ReadTimeout', 'WriteTimeout', 'PoolTimeout',
                     'ConnectError', 'ReadError', 'WriteError', 'CloseError',
                     'LocalProtocolError', 'RemoteProtocolError', 'ProxyError',
                     'UnsupportedProtocol'):
            if isinstance(error, getattr(httpcore, name)):
                raise getattr(httpx, name)(str(error)) from error
        raise httpx.TransportError(str(error)) from error


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        with _http_errors():
            async for chunk in self.stream:
                yield chunk

    async def aclose(self) -> None:
        with _http_errors():
            await self.stream.aclose()


class ConnectorTransport(httpx.AsyncBaseTransport):
    def __init__(self, allowed_hosts: tuple[str, ...], allow_dev_auth: bool,
                 backend: httpcore.AsyncNetworkBackend | None = None):
        self.allow_local = allow_dev_auth
        self.pool = httpcore.AsyncConnectionPool(
            network_backend=ConnectorNetworkBackend(allowed_hosts, allow_dev_auth, backend),
            ssl_context=httpcore.default_ssl_context(),
            max_connections=20, max_keepalive_connections=10, retries=0,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # ToolRegistry validates the full endpoint before issuing credentials.
        # Enforce scheme here too if the transport is used directly.
        is_local = request.url.host in {'localhost', '127.0.0.1'}
        if request.url.scheme != 'https' and not (request.url.scheme == 'http' and is_local and self.allow_local):
            raise ConnectorAddressDenied('Connector transport requires HTTPS.')
        with _http_errors():
            response = await self.pool.handle_async_request(httpcore.Request(
                method=request.method,
                url=httpcore.URL(scheme=request.url.raw_scheme, host=request.url.raw_host,
                                 port=request.url.port, target=request.url.raw_path),
                headers=request.headers.raw, content=request.stream,
                extensions={**request.extensions, 'sni_hostname': request.url.host},
            ))
        return httpx.Response(response.status, headers=response.headers,
                              stream=_ResponseStream(response.stream), extensions=response.extensions)

    async def aclose(self) -> None:
        with _http_errors():
            await self.pool.aclose()
