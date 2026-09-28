"""Audit outbox integrity and transport tests; no external network."""
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from loopos_authority.audit_anchor import AuditAnchorDispatcher
from loopos_authority.store import AuthorityStore, canonical_json
from loopos_authority.postgres_store import PostgresAuthorityStore, split_postgres_script
from loopos_authority.contracts import REQUIRED_AUDIT_TRIGGERS, REQUIRED_POSTGRES_TABLES, REQUIRED_RELEASE_POLICY_TRIGGERS
from test_connector_transport import Dialer, answers

SECRET = 'synthetic-audit-anchor-key-at-least-thirty-two-bytes'
ENDPOINT = 'https://audit.example.com/events'


class AuditAnchorSecurityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = AuthorityStore(Path(self.directory.name) / 'authority.sqlite', None)
        self.requests = []
        self.dispatcher = AuditAnchorDispatcher(self.store, ENDPOINT, SECRET,
            transport=httpx.MockTransport(self.respond))

    def respond(self, request):
        self.requests.append(request)
        return httpx.Response(202)

    async def asyncTearDown(self):
        await self.dispatcher.close()
        self.store.close()
        self.directory.cleanup()

    def event(self, tenant='tenant-a'):
        return self.store.append_event(tenant, None, 'SYNTHETIC_EVENT', None, 'actor', {'test': True})

    def overwrite(self, event, raw):
        self.store.connection.execute('UPDATE audit_anchor_outbox SET envelope_json = ? WHERE event_id = ?',
                                      (raw, event['event_id']))
        self.store.connection.commit()

    async def test_modified_envelope_is_not_signed_or_sent(self):
        event = self.event()
        self.overwrite(event, canonical_json({**event, 'payload_json': '{"test":false}'}))
        self.assertEqual(await self.dispatcher.drain(), 0)
        self.assertEqual(self.requests, [])
        pending = self.store.pending_audit_anchors(include_deferred=True)
        self.assertEqual(pending[0]['attempts'], 1)
        self.assertIn('audit event', pending[0]['last_error'])

    async def test_bad_json_does_not_stop_good_record_and_is_deferred(self):
        bad, good = self.event(), self.event('tenant-b')
        self.overwrite(bad, '{not valid JSON')
        self.assertEqual(await self.dispatcher.drain(), 1)
        self.assertEqual([request.headers['x-loopos-event-id'] for request in self.requests], [good['event_id']])
        self.assertEqual(self.store.audit_anchor_backlog('tenant-a'), 1)
        self.assertEqual(self.store.audit_anchor_backlog('tenant-b'), 0)
        self.assertEqual(self.store.pending_audit_anchors(), [])
        self.assertEqual(self.store.pending_audit_anchors(include_deferred=True)[0]['attempts'], 1)

    async def test_missing_or_wrong_event_identity_is_not_signed(self):
        for changes in ({'event_id': 'other'}, {'tenant_id': 'tenant-b'}, {'sequence': 99}, {'extra': 'untrusted'}):
            with self.subTest(changes=changes):
                event = self.event()
                self.overwrite(event, canonical_json({**event, **changes}))
                self.assertEqual(await self.dispatcher.drain(), 0)
        self.assertEqual(self.requests, [])

    async def test_nonobject_envelope_does_not_crash_batch(self):
        for value in ('null', '[]', '42'):
            with self.subTest(value=value):
                event = self.event()
                self.overwrite(event, value)
                self.assertEqual(await self.dispatcher.drain(), 0)
        self.assertEqual(self.requests, [])

    async def test_repaired_outbox_reuses_original_identity_and_exact_bytes(self):
        event = self.event()
        self.overwrite(event, '{}')
        self.assertEqual(await self.dispatcher.drain(), 0)
        # Simulate an authorized local repair from retained append-only source.
        # The dispatcher itself never rewrites or invents an audit event.
        self.overwrite(event, canonical_json(event))
        self.store.connection.execute("UPDATE audit_anchor_outbox SET next_attempt_at = '2000-01-01T00:00:00+00:00'")
        self.store.connection.commit()
        self.assertEqual(await self.dispatcher.drain(), 1)
        self.assertEqual(self.requests[0].content, canonical_json(event).encode())
        self.assertEqual(self.requests[0].headers['x-loopos-event-id'], event['event_id'])

    async def test_target_and_key_changes_cannot_reuse_old_delivery(self):
        self.event()
        self.assertEqual(await self.dispatcher.drain(), 1)
        original = self.dispatcher.delivery_binding
        self.assertTrue(self.store.audit_anchor_delivery_status(300, delivery_binding=original)['verified'])
        for epoch, endpoint, secret in ((2, ENDPOINT + '/new', SECRET), (3, ENDPOINT, SECRET + '-rotated')):
            with self.subTest(endpoint=endpoint, rotated=secret != SECRET):
                dispatcher = AuditAnchorDispatcher(self.store, endpoint, secret, transport=httpx.MockTransport(self.respond), epoch=epoch)
                try:
                    self.assertFalse(self.store.audit_anchor_delivery_status(300, delivery_binding=dispatcher.delivery_binding)['verified'])
                    # Rotation is not authority to replay old payloads to a new sink.
                    self.assertEqual(await dispatcher.drain(), 0)
                    event = self.event()
                    self.assertEqual(await dispatcher.drain(), 1)
                    self.assertTrue(self.store.audit_anchor_delivery_status(300, delivery_binding=dispatcher.delivery_binding)['verified'])
                    self.assertEqual(self.requests[-1].headers['x-loopos-event-id'], event['event_id'])
                finally:
                    await dispatcher.close()

    async def test_legacy_unbound_acknowledgment_cannot_satisfy_current_target(self):
        event = self.event()
        self.store.mark_audit_anchor_delivered(event['event_id'])
        self.assertFalse(self.store.audit_anchor_delivery_status(300, delivery_binding=self.dispatcher.delivery_binding)['verified'])
        self.assertEqual(self.store.audit_anchor_backlog(), 0)
        self.assertEqual(await self.dispatcher.drain(), 0)

    async def test_binding_is_tenant_scoped_and_survives_restart(self):
        self.event('tenant-a')
        await self.dispatcher.drain()
        binding = self.dispatcher.delivery_binding
        self.store.close()
        self.store = AuthorityStore(Path(self.directory.name) / 'authority.sqlite', None)
        self.dispatcher.store = self.store
        self.assertTrue(self.store.audit_anchor_delivery_status(300, 'tenant-a', binding)['verified'])
        self.assertFalse(self.store.audit_anchor_delivery_status(300, 'tenant-b', binding)['verified'])

    async def test_old_sqlite_schema_migrates_without_inventing_binding(self):
        event = self.event()
        self.store.mark_audit_anchor_delivered(event['event_id'])
        self.store.connection.execute('DROP INDEX idx_audit_anchor_delivery_binding')
        self.store.connection.execute('ALTER TABLE audit_anchor_outbox DROP COLUMN delivery_binding')
        self.store.connection.execute('ALTER TABLE audit_anchor_outbox DROP COLUMN delivery_epoch')
        self.store.close()
        self.store = AuthorityStore(Path(self.directory.name) / 'authority.sqlite', None)
        self.dispatcher.store = self.store
        row = self.store.connection.execute('SELECT * FROM audit_anchor_outbox').fetchone()
        self.assertEqual(row['event_id'], event['event_id'])
        self.assertIsNotNone(row['delivered_at'])
        self.assertIsNone(row['delivery_binding'])
        self.assertFalse(self.store.audit_anchor_delivery_status(300, delivery_binding=self.dispatcher.delivery_binding)['verified'])

    async def test_shared_fence_serializes_workers_and_cuts_off_stale_epoch(self):
        event = self.event()
        second_store = AuthorityStore(Path(self.directory.name) / 'authority.sqlite', None)
        entered = asyncio.Event()
        release = asyncio.Event()
        requests = []

        class BlockingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                requests.append(request)
                entered.set()
                await release.wait()
                return httpx.Response(202)

        old = AuditAnchorDispatcher(self.store, ENDPOINT, SECRET, transport=BlockingTransport(), epoch=1)
        new = AuditAnchorDispatcher(second_store, ENDPOINT + '/rotated', SECRET, transport=httpx.MockTransport(self.respond), epoch=2)
        try:
            old_drain = asyncio.create_task(old.drain(limit=1))
            await asyncio.wait_for(entered.wait(), timeout=2)
            self.assertEqual(await new.drain(limit=1), 0)
            status = second_store.audit_anchor_fence_status(2, new.delivery_binding)
            self.assertEqual(status['phase'], 'draining')
            self.assertEqual(status['active_epoch'], 1)
            self.assertEqual(status['pending_epoch'], 2)
            release.set()
            self.assertEqual(await old_drain, 1)
            self.assertEqual(len(requests), 1)
            self.assertEqual(await old.drain(limit=1), 0)
            self.assertEqual(len(requests), 1)

            next_event = second_store.append_event('tenant-b', None, 'AFTER_ROTATION', None, 'actor', {})
            self.assertEqual(await new.drain(limit=1), 1)
            self.assertEqual(self.requests[-1].headers['x-loopos-event-id'], next_event['event_id'])
            self.assertEqual(self.requests[-1].headers['x-loopos-anchor-epoch'], '2')
            self.assertEqual(second_store.audit_anchor_fence_status(2, new.delivery_binding)['phase'], 'active')
        finally:
            release.set()
            await old.close()
            await new.close()
            second_store.close()

    async def test_two_same_epoch_workers_cannot_admit_the_same_event_twice(self):
        self.event()
        second_store = AuthorityStore(Path(self.directory.name) / 'authority.sqlite', None)
        entered = asyncio.Event()
        release = asyncio.Event()
        sent = []

        class BlockingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                sent.append(request)
                entered.set()
                await release.wait()
                return httpx.Response(202)

        first = AuditAnchorDispatcher(self.store, ENDPOINT, SECRET, transport=BlockingTransport(), epoch=1)
        second = AuditAnchorDispatcher(second_store, ENDPOINT, SECRET, transport=httpx.MockTransport(self.respond), epoch=1)
        try:
            first_task = asyncio.create_task(first.drain(limit=1))
            await asyncio.wait_for(entered.wait(), timeout=2)
            self.assertEqual(await second.drain(limit=1), 0)
            self.assertEqual(len(sent), 1)
            release.set()
            self.assertEqual(await first_task, 1)
            self.assertEqual(len(sent), 1)
        finally:
            release.set()
            await first.close()
            await second.close()
            second_store.close()

    async def test_crashed_admission_stays_visible_and_blocks_epoch_change(self):
        event = self.event()
        self.assertTrue(self.store.prepare_audit_anchor_configuration(1, self.dispatcher.delivery_binding))
        attempt = self.store.claim_audit_anchor_attempt(event['event_id'], 1, self.dispatcher.delivery_binding)
        self.assertIsNotNone(attempt)
        new = AuditAnchorDispatcher(self.store, ENDPOINT + '/rotated', SECRET, transport=httpx.MockTransport(self.respond), epoch=2)
        try:
            self.assertEqual(await new.drain(limit=1), 0)
            status = self.store.audit_anchor_fence_status(2, new.delivery_binding, tenant_id='tenant-a', include_attempts=True)
            self.assertEqual(status['phase'], 'draining')
            self.assertEqual(status['unresolved_attempts'], 1)
            self.assertEqual(status['unresolved'][0]['attempt_id'], attempt['attempt_id'])
            self.assertEqual(status['unresolved'][0]['event_id'], event['event_id'])
            self.assertEqual(status['unresolved'][0]['state'], 'admitted')
            self.assertEqual(await new.drain(limit=1), 0)
            self.assertEqual(self.store.audit_anchor_fence_status(2, new.delivery_binding)['unresolved_attempts'], 1)
        finally:
            await new.close()

    async def test_uncertain_attempt_is_retained_and_blocks_rotation_until_same_id_retry(self):
        event = self.event()
        old = AuditAnchorDispatcher(self.store, ENDPOINT, SECRET,
            transport=httpx.MockTransport(lambda _request: (_ for _ in ()).throw(httpx.ReadTimeout('response lost'))), epoch=1)
        new = AuditAnchorDispatcher(self.store, ENDPOINT + '/rotated', SECRET,
            transport=httpx.MockTransport(self.respond), epoch=2)
        try:
            self.assertEqual(await old.drain(limit=1), 0)
            attempt = self.store.connection.execute("SELECT * FROM audit_anchor_attempts WHERE event_id = ?", (event['event_id'],)).fetchone()
            self.assertEqual(attempt['state'], 'uncertain')
            self.assertEqual(await new.drain(limit=1), 0)
            status = self.store.audit_anchor_fence_status(2, new.delivery_binding)
            self.assertEqual(status['phase'], 'draining')
            self.assertEqual(status['unresolved_attempts'], 1)
            self.store.connection.execute("UPDATE audit_anchor_outbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' WHERE event_id = ?", (event['event_id'],))
            self.store.connection.commit()
            old.http._transport = httpx.MockTransport(self.respond)
            self.assertEqual(await old.drain(limit=1), 1)
            self.assertEqual(self.store.audit_anchor_fence_status(2, new.delivery_binding)['phase'], 'active')
            self.assertEqual(self.requests[-1].headers['x-loopos-event-id'], event['event_id'])
            self.assertEqual(self.requests[-1].headers['x-loopos-anchor-epoch'], '1')
        finally:
            await old.close()
            await new.close()

    async def test_default_transport_denies_private_and_proxy_route_before_bytes(self):
        await self.dispatcher.close()
        dialer = Dialer()
        self.event()
        with patch.dict('os.environ', {'HTTPS_PROXY': 'http://untrusted.example:3128'}), \
             patch('httpcore.AnyIOBackend', return_value=dialer), \
             patch('anyio.getaddrinfo', new=AsyncMock(return_value=answers('127.0.0.1'))):
            self.dispatcher = AuditAnchorDispatcher(self.store, ENDPOINT, SECRET)
            self.assertEqual(await self.dispatcher.drain(), 0)
        self.assertEqual(dialer.calls, [])
        self.assertEqual(self.store.audit_anchor_backlog(), 1)

    async def test_constructor_rejects_insecure_configuration_without_transport_calls(self):
        for endpoint in ('https://audit.example.com/events?', 'https://audit.example.com/events#',
                         'https://user:password@audit.example.com/events', 'http://audit.example.com/events',
                         'https://127.0.0.1/events'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                AuditAnchorDispatcher(self.store, endpoint, SECRET, transport=httpx.MockTransport(self.respond))
        self.assertEqual(self.requests, [])

    async def test_postgres_migration_is_additive_and_replay_free(self):
        path = Path(__file__).resolve().parents[2] / 'supabase/migrations/20260921020000_audit_anchor_delivery_binding.sql'
        statements = split_postgres_script(path.read_text(encoding='utf-8'))
        self.assertEqual(len(statements), 3)
        self.assertIn("lock_timeout = '2s'", statements[0])
        self.assertIn("statement_timeout = '60s'", statements[1])
        self.assertIn('ADD COLUMN IF NOT EXISTS delivery_binding TEXT', statements[2])
        self.assertNotIn('UPDATE ', '\n'.join(statements))

    async def test_postgres_shared_fence_migration_creates_private_monotonic_control(self):
        path = Path(__file__).resolve().parents[2] / 'supabase/migrations/20260921030000_audit_anchor_shared_fence.sql'
        sql = path.read_text(encoding='utf-8')
        statements = split_postgres_script(sql)
        self.assertIn('ALTER TABLE audit_anchor_outbox ADD COLUMN IF NOT EXISTS delivery_epoch BIGINT', sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS audit_anchor_control', sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS audit_anchor_attempts', sql)
        self.assertIn("WHERE state = 'admitted'", sql)
        self.assertIn('ENABLE ROW LEVEL SECURITY', sql)
        self.assertIn('REVOKE ALL ON audit_anchor_control, audit_anchor_attempts', sql)
        self.assertNotIn('UPDATE audit_anchor_outbox', sql)
        self.assertGreaterEqual(len(statements), 10)

    async def test_postgres_admission_requires_delivery_binding_column(self):
        class Result:
            def __init__(self, rows): self.rows = rows
            def fetchall(self): return self.rows
        class Connection:
            has_binding = False
            def execute(self, sql):
                if 'information_schema.tables' in sql:
                    return Result([{'table_name': t} for t in REQUIRED_POSTGRES_TABLES])
                if 'pg_class' in sql:
                    return Result([{'relname': t} for t in REQUIRED_POSTGRES_TABLES])
                if 'pg_trigger' in sql:
                    if 'public.release_policy_control' in sql:
                        return Result([{'tgname': t} for t in REQUIRED_RELEASE_POLICY_TRIGGERS])
                    return Result([{'tgname': t} for t in REQUIRED_AUDIT_TRIGGERS])
                if 'information_schema.columns' in sql:
                    return Result([{'column_name': 'delivery_binding'}, {'column_name': 'delivery_epoch'}] if self.has_binding else [])
                raise AssertionError(sql)
        store = object.__new__(PostgresAuthorityStore)
        store.lock, store.connection = threading.RLock(), Connection()
        with self.assertRaisesRegex(RuntimeError, 'fencing migration is missing'):
            store.verify_schema()
        store.connection.has_binding = True
        store.verify_schema()


if __name__ == '__main__':
    unittest.main()
