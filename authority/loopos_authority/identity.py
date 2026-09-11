from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import jwt

from .models import Actor, UserRole


def _https_url(value: str, label: str) -> str:
    try:
        parsed = urlparse(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid HTTPS URL.") from error
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{label} must use a valid port.") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "\\" in value
    ):
        raise ValueError(f"{label} must be an HTTPS URL without credentials, query, fragment, or backslash.")
    return value


def _claim_name(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be a non-blank claim name.")
    return normalized


class OIDCIdentityVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        tenant_claim: str,
        role_claim: str,
        role_mapping: dict[str, UserRole],
        jwks_client: Any | None = None,
    ) -> None:
        self.issuer = _https_url(issuer, "OIDC issuer")
        if not isinstance(audience, str) or not audience.strip():
            raise ValueError("OIDC audience must be a non-blank value.")
        self.audience = audience.strip()
        self.tenant_claim = _claim_name(tenant_claim, "OIDC tenant claim")
        self.role_claim = _claim_name(role_claim, "OIDC role claim")
        self.role_mapping = role_mapping
        self.jwks_client = jwks_client or jwt.PyJWKClient(
            _https_url(jwks_url, "OIDC JWKS URL"),
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
        )

    def verify(self, assertion: str) -> Actor:
        signing_key = self.jwks_client.get_signing_key_from_jwt(assertion)
        claims = jwt.decode(
            assertion,
            key=signing_key,
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["aud", "exp", "iat", "iss", "sub"]},
        )
        tenant_id = claims.get(self.tenant_claim)
        if not isinstance(tenant_id, str) or not tenant_id:
            raise ValueError("Identity assertion does not contain a valid tenant claim.")
        role_values = claims.get(self.role_claim, [])
        if isinstance(role_values, str):
            role_values = [role_values]
        if not isinstance(role_values, list) or not all(isinstance(value, str) for value in role_values):
            raise ValueError("Identity assertion role claim must be a string or string array.")
        mapped_roles = {self.role_mapping[value] for value in role_values if value in self.role_mapping}
        if not mapped_roles:
            raise ValueError("Identity assertion does not grant an authorized LoopOS role.")
        if len(mapped_roles) > 1:
            raise ValueError("Identity assertion maps to multiple LoopOS roles.")
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise ValueError("Identity assertion subject is invalid.")
        email = claims.get("email")
        if email is not None and not isinstance(email, str):
            raise ValueError("Identity assertion email claim is invalid.")
        name = claims.get("name") or email or subject
        if not isinstance(name, str):
            raise ValueError("Identity assertion name claim is invalid.")
        return Actor(
            tenant_id=tenant_id,
            user_id=subject,
            name=name,
            email=email,
            role=mapped_roles.pop(),
        )
