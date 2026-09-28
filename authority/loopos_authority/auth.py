from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Protocol

from .models import Actor


class InvalidSession(ValueError):
    pass


class IdentityVerifier(Protocol):
    def verify(self, assertion: str) -> Actor:
        ...


class SessionRegistry(Protocol):
    def register_session(
        self,
        tenant_id: str,
        user_id: str,
        role: str,
        jti: str,
        issued_at: int,
        expires_at: int,
    ) -> None:
        ...

    def is_session_revoked(self, jti: str) -> bool:
        ...

    def revoke_session(self, jti: str, reason: str) -> None:
        ...


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SessionSigner:
    def __init__(self, secret: str, registry: SessionRegistry | None = None):
        self.secret = secret.encode("utf-8")
        self.registry = registry

    def issue(self, actor: Actor, ttl_seconds: int) -> str:
        header = {"alg": "HS256", "typ": "LOOPOS"}
        now = int(time.time())
        jti = str(uuid.uuid4())
        expires_at = now + ttl_seconds
        payload = {
            "iss": "loopos-authority",
            "sub": actor.user_id,
            "tenant": actor.tenant_id,
            "name": actor.name,
            "email": actor.email,
            "role": actor.role,
            "iat": now,
            "exp": expires_at,
            "jti": jti,
        }
        unsigned = f"{_encode(json.dumps(header, separators=(',', ':')).encode())}.{_encode(json.dumps(payload, separators=(',', ':')).encode())}"
        signature = _encode(hmac.new(self.secret, unsigned.encode("ascii"), hashlib.sha256).digest())
        token = f"{unsigned}.{signature}"
        if self.registry is not None:
            self.registry.register_session(actor.tenant_id, actor.user_id, actor.role, jti, now, expires_at)
        return token

    def verify(self, token: str) -> Actor:
        try:
            header_part, payload_part, signature_part = token.split(".")
            unsigned = f"{header_part}.{payload_part}"
            expected = hmac.new(self.secret, unsigned.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _decode(signature_part)):
                raise InvalidSession("Session signature is invalid.")
            header = json.loads(_decode(header_part))
            payload: dict[str, Any] = json.loads(_decode(payload_part))
            if header.get("alg") != "HS256" or payload.get("iss") != "loopos-authority":
                raise InvalidSession("Session issuer or algorithm is invalid.")
            if int(payload.get("exp", 0)) <= int(time.time()):
                raise InvalidSession("Session has expired.")
            jti = payload.get("jti")
            if not isinstance(jti, str) or not jti:
                raise InvalidSession("Session identifier is missing.")
            if self.registry is not None and self.registry.is_session_revoked(jti):
                raise InvalidSession("Session has been revoked.")
            return Actor(
                tenant_id=payload["tenant"],
                user_id=payload["sub"],
                name=payload["name"],
                email=payload.get("email"),
                role=payload["role"],
            )
        except InvalidSession:
            raise
        except Exception as error:
            raise InvalidSession("Session token is malformed.") from error

    def revoke(self, token: str, reason: str = "user_requested") -> None:
        if self.registry is None:
            raise InvalidSession("Session revocation is not configured.")
        try:
            _header, payload_part, _signature = token.split(".")
            payload = json.loads(_decode(payload_part))
            jti = payload.get("jti")
            if not isinstance(jti, str) or not jti:
                raise InvalidSession("Session identifier is missing.")
            self.verify(token)
        except InvalidSession:
            raise
        except Exception as error:
            raise InvalidSession("Session token is malformed.") from error
        self.registry.revoke_session(jti, reason)
