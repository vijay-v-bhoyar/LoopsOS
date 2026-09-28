from __future__ import annotations

import asyncio
import hashlib
import hmac
import math
from urllib.parse import urlparse

import httpx

from .store import AuditAnchorFenceError, AuthorityStore, canonical_json
from .config import _validate_audit_anchor
from .connector_transport import ConnectorTransport


class AuditAnchorDispatcher:
    def __init__(
        self,
        store: AuthorityStore,
        endpoint: str,
        hmac_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
        allow_local_http: bool = False,
        epoch: int = 1,
    ):
        _validate_audit_anchor(endpoint, hmac_secret, allow_local_http=allow_local_http)
        if not endpoint or not hmac_secret:
            raise ValueError("An audit anchor endpoint and signing key are required.")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Audit anchor timeout must be positive and finite.")
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch <= 0 or epoch > 9_223_372_036_854_775_807:
            raise ValueError("Audit anchor epoch must be a positive 64-bit integer.")
        hostname = (urlparse(endpoint).hostname or '').lower()
        self.store = store
        self.endpoint = endpoint
        self.hmac_secret = hmac_secret
        self.epoch = epoch
        self.delivery_binding = hmac.new(
            hmac_secret.encode('utf-8'),
            b'loopos-audit-anchor-destination-v2\0' + str(epoch).encode('ascii') + b'\0' + endpoint.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        self._drain_lock = asyncio.Lock()
        self.http = httpx.AsyncClient(
            transport=transport if transport is not None else ConnectorTransport((hostname,), allow_local_http),
            trust_env=False,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    async def drain(self, limit: int = 100, tenant_id: str | None = None) -> int:
        async with self._drain_lock:
            try:
                if not self.store.prepare_audit_anchor_configuration(self.epoch, self.delivery_binding):
                    return 0
            except AuditAnchorFenceError:
                return 0
            delivered = 0
            for record in self.store.pending_audit_anchors(limit=limit, tenant_id=tenant_id, delivery_epoch=self.epoch):
                try:
                    attempt = self.store.claim_audit_anchor_attempt(record['event_id'], self.epoch, self.delivery_binding)
                except AuditAnchorFenceError:
                    break
                if attempt is None:
                    continue
                try:
                    # The mutable delivery queue is not authority to mint a new
                    # signed event. Reconstruct from the append-only source and
                    # reject corruption before any signature or network effect.
                    envelope = self.store.validated_audit_anchor_envelope(record)
                    body = canonical_json(envelope).encode("utf-8")
                    signing_message = b'loopos-audit-anchor-v2\n' + str(self.epoch).encode('ascii') + b'\n' + body
                    signature = hmac.new(self.hmac_secret.encode("utf-8"), signing_message, hashlib.sha256).hexdigest()
                    async with self.http.stream(
                        "POST",
                        self.endpoint,
                        content=body,
                        headers={
                            "content-type": "application/json",
                            "x-loopos-event-id": envelope["event_id"],
                            "x-loopos-anchor-epoch": str(self.epoch),
                            "x-loopos-signature-256": f"sha256={signature}",
                        },
                    ) as response:
                        if response.status_code < 200 or response.status_code >= 300:
                            raise RuntimeError(f"Audit anchor returned HTTP {response.status_code}.")
                    if self.store.finish_audit_anchor_attempt(attempt, outcome='delivered'):
                        delivered += 1
                except asyncio.CancelledError:
                    self.store.finish_audit_anchor_attempt(attempt, outcome='uncertain', detail='delivery was cancelled after transport admission')
                    raise
                except Exception as error:
                    outcome = 'not_sent' if isinstance(error, ValueError) else 'uncertain'
                    self.store.finish_audit_anchor_attempt(
                        attempt, outcome=outcome,
                        detail=str(error) or error.__class__.__name__,
                    )
            return delivered

    async def close(self) -> None:
        await self.http.aclose()
