from __future__ import annotations

import asyncio
import hashlib
import hmac

import httpx

from .store import AuthorityStore, canonical_json


class AuditAnchorDispatcher:
    def __init__(
        self,
        store: AuthorityStore,
        endpoint: str,
        hmac_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ):
        self.store = store
        self.endpoint = endpoint
        self.hmac_secret = hmac_secret
        self._drain_lock = asyncio.Lock()
        self.http = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    async def drain(self, limit: int = 100) -> int:
        async with self._drain_lock:
            delivered = 0
            for record in self.store.pending_audit_anchors(limit=limit):
                envelope = record["envelope"]
                body = canonical_json(envelope).encode("utf-8")
                signature = hmac.new(self.hmac_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
                try:
                    response = await self.http.post(
                        self.endpoint,
                        content=body,
                        headers={
                            "content-type": "application/json",
                            "x-loopos-event-id": envelope["event_id"],
                            "x-loopos-signature-256": f"sha256={signature}",
                        },
                    )
                    if response.status_code < 200 or response.status_code >= 300:
                        raise RuntimeError(f"Audit anchor returned HTTP {response.status_code}.")
                    self.store.mark_audit_anchor_delivered(envelope["event_id"])
                    delivered += 1
                except Exception as error:
                    self.store.record_audit_anchor_failure(
                        envelope["event_id"],
                        str(error) or error.__class__.__name__,
                    )
            return delivered

    async def close(self) -> None:
        await self.http.aclose()
