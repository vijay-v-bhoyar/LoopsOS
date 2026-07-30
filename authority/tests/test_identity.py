from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from loopos_authority.config import Settings
from loopos_authority.identity import OIDCIdentityVerifier


class StaticJwksClient:
    def __init__(self, key) -> None:
        self.key = key

    def get_signing_key_from_jwt(self, _assertion: str):
        return self.key


class OIDCIdentityVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.verifier = OIDCIdentityVerifier(
            issuer="https://identity.example.com/",
            audience="loopos-production",
            jwks_url="https://identity.example.com/.well-known/jwks.json",
            tenant_claim="tenant_id",
            role_claim="groups",
            role_mapping={"loopos-approvers": "Approver", "loopos-auditors": "Auditor"},
            jwks_client=StaticJwksClient(self.private_key.public_key()),
        )

    def assertion(self, **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": "https://identity.example.com/",
            "aud": "loopos-production",
            "sub": "enterprise-user-42",
            "iat": now,
            "exp": now + 300,
            "tenant_id": "tenant-enterprise",
            "groups": ["employees", "loopos-approvers"],
            "name": "Enterprise Approver",
            "email": "approver@example.com",
            **overrides,
        }
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"})

    def test_verifies_standard_claims_and_maps_an_allowlisted_role(self) -> None:
        actor = self.verifier.verify(self.assertion())

        self.assertEqual(actor.tenant_id, "tenant-enterprise")
        self.assertEqual(actor.user_id, "enterprise-user-42")
        self.assertEqual(actor.role, "Approver")
        self.assertEqual(actor.email, "approver@example.com")

    def test_rejects_an_unmapped_or_ambiguous_role(self) -> None:
        with self.assertRaisesRegex(ValueError, "authorized LoopOS role"):
            self.verifier.verify(self.assertion(groups=["employees"]))
        with self.assertRaisesRegex(ValueError, "multiple LoopOS roles"):
            self.verifier.verify(self.assertion(groups=["loopos-approvers", "loopos-auditors"]))

    def test_rejects_the_wrong_audience(self) -> None:
        with self.assertRaises(jwt.InvalidAudienceError):
            self.verifier.verify(self.assertion(aud="another-application"))


class IdentityEnvironmentTests(unittest.TestCase):
    def test_partial_oidc_configuration_is_rejected(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LOOPOS_ALLOW_DEV_AUTH": "false",
                "LOOPOS_SESSION_HMAC_SECRET": "identity-environment-secret-at-least-thirty-two-bytes",
                "LOOPOS_OIDC_ISSUER": "https://identity.example.com/",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "OIDC configuration"):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
