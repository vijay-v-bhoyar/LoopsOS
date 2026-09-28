"""Socket-boundary regressions: deterministic DNS and streams, no network."""
import asyncio
from pathlib import Path
import socket
import ssl
import unittest
from unittest.mock import AsyncMock, patch

import httpcore
import httpx

from loopos_authority.config import Settings
from loopos_authority.connector_transport import (
    ConnectorAddressDenied, ConnectorNetworkBackend, ConnectorTransport,
)
from loopos_authority.tools import RetryableToolFailure, TerminalToolFailure, ToolRegistry


def answers(*addresses):
    return [(socket.AF_INET6 if ':' in address else socket.AF_INET, socket.SOCK_STREAM,
             socket.IPPROTO_TCP, '', (address, 443)) for address in addresses]


class Stream(httpcore.AsyncNetworkStream):
    def __init__(self, failure=None):
        self.writes = []
        self.sni = None
        self.context = None
        self.closed = False
        self.read_count = 0
        self.failure = failure

    async def read(self, max_bytes, timeout=None):
        if self.failure:
            raise self.failure
        self.read_count += 1
        return (b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{"ok":true}'
                if self.read_count == 1 else b'')

    async def write(self, buffer, timeout=None):
        self.writes.append(buffer)

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.context, self.sni = ssl_context, server_hostname
        return self

    async def aclose(self):
        self.closed = True

    def get_extra_info(self, name):
        return None


class Dialer(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.calls = []
        self.streams = []
        self.fail_first = False
        self.read_failure = None

    async def connect_tcp(self, host, port, **kwargs):
        self.calls.append((host, port))
        if self.fail_first and len(self.calls) == 1:
            raise httpcore.ConnectError('simulated first-address failure')
        stream = Stream(self.read_failure)
        self.streams.append(stream)
        return stream


class ConnectorTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_dns_is_resolved_once_and_numeric_destination_is_used(self):
        dialer = Dialer()
        backend = ConnectorNetworkBackend(('connector.example',), False, dialer)
        with patch('anyio.getaddrinfo', new=AsyncMock(side_effect=[answers('93.184.216.34'), answers('127.0.0.1')])) as dns:
            await backend.connect_tcp('connector.example', 443, timeout=1)
        self.assertEqual(dns.await_count, 1)
        self.assertEqual(dialer.calls, [('93.184.216.34', 443)])

    async def test_all_dns_answers_must_be_global_before_any_dial(self):
        for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '100.64.0.1',
                        '224.0.0.1', '0.0.0.0', '::1', 'fc00::1', 'fe80::1',
                        '::ffff:127.0.0.1', 'fe80::1%3', 'not-an-ip',
                        '64:ff9b::7f00:1', '64:ff9b:1::a00:1', '2002:7f00:1::',
                        '2001:0:4136:e378:8000:63bf:3fff:fdd2',
                        '100::1', '100:0:0:1::1', '2001:2::1', '2001:10::1',
                        '2001:1::4', '2001:db8::1', '2001:ffff::1', '2a20::1',
                        '2d00::1', '3ffe::1', '3fff::1', '5f00::1'):
            with self.subTest(address=address):
                dialer = Dialer()
                backend = ConnectorNetworkBackend(('connector.example',), False, dialer)
                with patch('anyio.getaddrinfo', new=AsyncMock(return_value=answers('93.184.216.34', address))):
                    with self.assertRaises(ConnectorAddressDenied):
                        await backend.connect_tcp('connector.example', 443, timeout=1)
                self.assertEqual(dialer.calls, [])

    async def test_iana_globally_reachable_ipv6_assignments_remain_usable(self):
        for address in ('2001:1::1', '2001:3::1', '2001:4:112::1',
                        '2001:20::1', '2001:30::1', '2606:4700:4700::1111'):
            with self.subTest(address=address):
                dialer = Dialer()
                backend = ConnectorNetworkBackend(('connector.example',), False, dialer)
                with patch('anyio.getaddrinfo', new=AsyncMock(return_value=answers(address))):
                    await backend.connect_tcp('connector.example', 443, timeout=1)
                self.assertEqual(dialer.calls, [(address, 443)])

    async def test_empty_dns_answer_is_denied(self):
        dialer = Dialer()
        with patch('anyio.getaddrinfo', new=AsyncMock(return_value=[])):
            with self.assertRaises(ConnectorAddressDenied):
                await ConnectorNetworkBackend(('connector.example',), False, dialer).connect_tcp('connector.example', 443)
        self.assertEqual(dialer.calls, [])

    async def test_unallowlisted_name_is_denied_without_resolution(self):
        with patch('anyio.getaddrinfo', new=AsyncMock()) as dns:
            with self.assertRaises(ConnectorAddressDenied):
                await ConnectorNetworkBackend((), False).connect_tcp('connector.example', 443)
        dns.assert_not_awaited()

    async def test_literal_private_address_is_denied_even_if_allowlisted(self):
        with patch('anyio.getaddrinfo', new=AsyncMock()) as dns:
            with self.assertRaises(ConnectorAddressDenied):
                await ConnectorNetworkBackend(('127.0.0.1',), False).connect_tcp('127.0.0.1', 443)
        dns.assert_not_awaited()

    async def test_literal_public_ipv6_is_pinned_without_dns(self):
        dialer = Dialer()
        address = '2606:4700:4700::1111'
        with patch('anyio.getaddrinfo', new=AsyncMock()) as dns:
            await ConnectorNetworkBackend((address,), False, dialer).connect_tcp(address, 443)
        dns.assert_not_awaited()
        self.assertEqual(dialer.calls, [(address, 443)])

    async def test_local_development_is_numeric_and_requires_exact_allowlist(self):
        dialer = Dialer()
        with patch('anyio.getaddrinfo', new=AsyncMock()) as dns:
            await ConnectorNetworkBackend(('localhost',), True, dialer).connect_tcp('localhost', 80)
            with self.assertRaises(ConnectorAddressDenied):
                await ConnectorNetworkBackend((), True, dialer).connect_tcp('localhost', 80)
        dns.assert_not_awaited()
        self.assertEqual(dialer.calls, [('127.0.0.1', 80)])

    async def test_fallback_uses_only_already_validated_numeric_candidates(self):
        dialer = Dialer()
        dialer.fail_first = True
        with patch('anyio.getaddrinfo', new=AsyncMock(return_value=answers('93.184.216.34', '1.1.1.1'))) as dns:
            await ConnectorNetworkBackend(('connector.example',), False, dialer).connect_tcp('connector.example', 443)
        self.assertEqual(dns.await_count, 1)
        self.assertEqual(dialer.calls, [('93.184.216.34', 443), ('1.1.1.1', 443)])

    async def test_resolution_is_bounded_by_connect_timeout(self):
        async def slow(*args, **kwargs):
            await asyncio.sleep(60)
        with patch('anyio.getaddrinfo', side_effect=slow):
            with self.assertRaises(httpcore.ConnectTimeout):
                await ConnectorNetworkBackend(('connector.example',), False).connect_tcp('connector.example', 443, timeout=0.01)

    async def test_dns_failure_maps_to_connect_error(self):
        with patch('anyio.getaddrinfo', new=AsyncMock(side_effect=socket.gaierror('synthetic'))):
            with self.assertRaises(httpcore.ConnectError):
                await ConnectorNetworkBackend(('connector.example',), False).connect_tcp('connector.example', 443)

    async def test_unix_socket_is_denied(self):
        with self.assertRaises(ConnectorAddressDenied):
            await ConnectorNetworkBackend((), False).connect_unix_socket('/unused')

    async def test_original_sni_host_and_certificate_verification_preserved(self):
        dialer = Dialer()
        transport = ConnectorTransport(('connector.example',), False, dialer)
        with patch('anyio.getaddrinfo', new=AsyncMock(return_value=answers('93.184.216.34'))):
            async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
                response = await client.get('https://connector.example:8443/read', extensions={'sni_hostname': 'wrong.example'})
        self.assertEqual(response.json(), {'ok': True})
        self.assertEqual(dialer.calls, [('93.184.216.34', 8443)])
        stream = dialer.streams[0]
        self.assertEqual(stream.sni, 'connector.example')
        self.assertTrue(stream.context.check_hostname)
        self.assertEqual(stream.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertIn(b'Host: connector.example:8443', b''.join(stream.writes))
        self.assertTrue(stream.closed)

    async def test_each_new_connection_revalidates_dns(self):
        dialer = Dialer()
        with patch('anyio.getaddrinfo', new=AsyncMock(side_effect=[answers('93.184.216.34'), answers('127.0.0.1')])):
            async with httpx.AsyncClient(transport=ConnectorTransport(('connector.example',), False, dialer), trust_env=False) as client:
                self.assertEqual((await client.get('https://connector.example/read')).status_code, 200)
                with self.assertRaises(ConnectorAddressDenied):
                    await client.get('https://connector.example/read')
        self.assertEqual(len(dialer.calls), 1)

    async def test_stream_failure_preserves_httpx_retry_type(self):
        dialer = Dialer()
        dialer.read_failure = httpcore.ReadTimeout('synthetic timeout')
        with patch('anyio.getaddrinfo', new=AsyncMock(return_value=answers('93.184.216.34'))):
            async with httpx.AsyncClient(transport=ConnectorTransport(('connector.example',), False, dialer), trust_env=False) as client:
                with self.assertRaises(httpx.ReadTimeout):
                    await client.get('https://connector.example/read')

    async def test_plain_http_denied_outside_exact_local_development(self):
        for host, development in [('connector.example', True), ('localhost', False)]:
            dialer = Dialer()
            async with httpx.AsyncClient(transport=ConnectorTransport((host,), development, dialer), trust_env=False) as client:
                with self.assertRaises(ConnectorAddressDenied):
                    await client.get(f'http://{host}/read')
            self.assertEqual(dialer.calls, [])

    async def test_registry_rebinding_is_terminal_and_ambient_proxy_is_ignored(self):
        settings = Settings(Path('.'), Path('unused.db'), 'synthetic-secret', True,
                            ('connector.example',), (), max_retry_attempts=3)
        dialer = Dialer()
        with patch.dict('os.environ', {'HTTPS_PROXY': 'http://untrusted-proxy.example:3128'}), \
             patch('loopos_authority.tools.EffectBudget'), \
             patch('socket.getaddrinfo', return_value=answers('93.184.216.34')), \
             patch('anyio.getaddrinfo', new=AsyncMock(side_effect=[answers('93.184.216.34'), answers('127.0.0.1')])) as dns, \
             patch('httpcore.AnyIOBackend', return_value=dialer):
            tools = ToolRegistry(settings, None)
            try:
                with self.assertRaises(TerminalToolFailure):
                    await tools._get_json('https://connector.example/read')
            finally:
                await tools.close()
        self.assertEqual(dns.await_count, 2)
        self.assertEqual(dialer.calls, [])

    async def test_registry_initial_dns_timeout_is_bounded_without_blocking_loop(self):
        settings = Settings(Path('.'), Path('unused.db'), 'synthetic-secret', True,
                            ('connector.example',), (), http_timeout_seconds=0.02)
        async def slow(*args, **kwargs):
            await asyncio.sleep(60)
        ticks = []
        async def heartbeat():
            await asyncio.sleep(0.001)
            ticks.append(True)
        with patch('loopos_authority.tools.EffectBudget'), patch('anyio.getaddrinfo', side_effect=slow):
            tools = ToolRegistry(settings, None)
            try:
                with self.assertRaisesRegex(RetryableToolFailure, 'DNS validation timed out'):
                    await asyncio.gather(tools._get_json('https://connector.example/read'), heartbeat())
            finally:
                await tools.close()
        self.assertEqual(ticks, [True])

    async def test_actual_local_development_socket_uses_default_transport(self):
        received = []
        async def handler(reader, writer):
            received.append(await reader.readuntil(b'\r\n\r\n'))
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{"ok":true}')
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with httpx.AsyncClient(transport=ConnectorTransport(('localhost',), True), trust_env=False) as client:
                self.assertEqual((await client.get(f'http://localhost:{port}/read')).json(), {'ok': True})
        finally:
            server.close()
            await server.wait_closed()
        self.assertIn(f'Host: localhost:{port}'.encode(), received[0])


if __name__ == '__main__':
    unittest.main()
