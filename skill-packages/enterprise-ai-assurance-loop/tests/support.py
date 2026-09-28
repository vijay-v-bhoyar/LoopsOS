"""Synthetic attestations for testing the verifier, never product evidence."""
import copy
import hashlib
import secrets
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from enterprise_assurance.catalog import catalog, applicable
from enterprise_assurance.common import PACKAGE, bundle_digest, digest, encoded, read
from enterprise_assurance.engine import Engine
from enterprise_assurance.trust import seal
import base64


class Fixture:
    def __init__(self, root, product="insurance", enterprise=False):
        self.root = Path(root); self.time = 10000
        self.profile = read(PACKAGE / "profiles" / "local-insurance.json")
        self.profile["id"] = "test-" + product
        self.subject = {"schema": "enterprise-subject/v1", "product": product, "tenant": "synthetic-tenant",
            "environment": "PRODUCTION" if enterprise else "ISOLATED_TEST", "workflow": "synthetic-journey",
            "autonomy": 2 if product != "knowledge" else 0, "frontier": "ON" if product == "agentic" else "OFF",
            "manifest": {key: digest([key, product]) for key in ("source", "deployed", "config", "model", "prompt", "tools", "corpus", "memory", "consent", "enforcement")},
            "provider_identity": "SYNTHETIC_ONLY", "permissions": ["fixture-only"], "data_classes": ["synthetic"], "jurisdictions": ["fixture-jurisdiction"]}
        if enterprise:
            self.profile["exposure"] = "BOUNDED_AUTONOMY"; self.profile["required_proof"] = "ENTERPRISE"
        self.keys = {role: Ed25519PrivateKey.generate() for role in ("collector", "challenger", "executive", "operator", "help")}
        self.trust = {"schema": "enterprise-trust/v1", "epoch": 1, "issued_at": self.time - 10,
            "expires_at": self.time + 7200, "max_ttl_seconds": 3600, "evidence_not_before": 0,
            "approved_profiles": [digest(self.profile)], "revoked_profiles": [], "revoked_issuers": [],
            "revoked_invocations": [], "approved_verifiers": [bundle_digest()], "issuers": {}}
        roles = {"collector": "collector", "challenger": "challenger", "executive": "risk-executive", "operator": "operator", "help": "help-adapter"}
        for role, key in self.keys.items():
            self.trust["issuers"][role] = {"public_key": base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode(),
                "principal": role + "-principal", "organization_unit": role + "-unit", "roles": [roles[role]],
                "owners": list(range(13)) if role == "collector" else [], "test_only": True,
                "valid_from": self.time - 10, "valid_until": self.time + 7200}
        self.engine = Engine(self.root / "state.sqlite", self.trust, digest(self.trust), clock=lambda: self.time)
        self.plan = self.engine.admit("test-run", self.subject, self.profile, "test-goal", ["acceptance"], "codex-product-build-loop")

    def sign(self, purpose, payload, role="collector", expires=None):
        body = {"purpose": purpose, "principal": self.trust["issuers"][role]["principal"],
            "subject_sha": digest(self.subject), "profile_sha": digest(self.profile), "run_id": "test-run",
            "invocation_id": secrets.token_hex(16), "nonce": self.plan["nonce"], "issued_at": self.time,
            "expires_at": expires or self.time + 1800, "payload": payload}
        return seal(body, role, self.keys[role])

    def evidence(self, owner_id, fail=False):
        owner = catalog()[owner_id]
        applies = applicable(owner_id, self.subject)
        cases, blobs = [], {}
        for case in owner["cases"] if applies else []:
            observations = {m["field"]: m.get("expected", 0) for m in case["metrics"]}
            if fail and not cases:
                metric = case["metrics"][0]
                if "expected" in metric:
                    value = metric["expected"]
                    observations[metric["field"]] = not value if type(value) is bool else value + 1
                else: observations[metric["field"]] = self.profile["limits"][metric["limit"]] + 1
            raw = encoded({"proof": "SYNTHETIC_INPUT_TO_VERIFIER", "case": case["id"], "observations": observations})
            sha = hashlib.sha256(raw).hexdigest(); blobs[sha] = raw
            cases.append({"case_id": case["id"], "outcome": "FAIL" if fail and not cases else "PASS", "observations": observations,
                          "raw_sha": sha, "reason": "Synthetic verifier acceptance fixture, not a live product test."})
        payload = {"schema": "enterprise-evidence/v1", "owner": owner_id, "proof": "FIXTURE", "verifier_sha": bundle_digest(),
            "generation": self.engine.inspect("test-run")["run"]["evidence_generation"],
            "case_manifest_sha": digest(owner["cases"]), "observed_at": self.time, "scope": "APPLICABLE" if applies else "NOT_APPLICABLE",
            "cases": cases, "trial_ids": ["synthetic-1", "synthetic-2"] if applies else [],
            "all_dispatched_trials": ["synthetic-1", "synthetic-2"] if applies else [], "raw_manifest": {str(i): s for i, s in enumerate(blobs)},
            "limitations": ["Synthetic observations test the verifier; no product control is established."],
            "dependencies": ["local-test-only"], "operational_claims": [], "model_evidence_expires_at": self.time + 1800, "risks": []}
        return self.sign("evidence", payload), blobs

    def populate(self):
        for owner in range(13):
            envelope, blobs = self.evidence(owner)
            self.engine.ingest("test-run", envelope, blobs)

    def review(self, decision="APPROVE"):
        return self.sign("challenge", {"schema": "enterprise-review/v1", "manifest_sha": self.engine.inspect("test-run")["manifest_sha"],
            "decision": decision, "conflicts": [], "limitations": ["Synthetic organizational roles, not real second-line assurance."],
            "findings": [], "criterion_ids": ["acceptance"], "resolves_vetoes": []}, "challenger")

    def risk(self, risk_id="risk-1", case="QUALITY-DENOMINATOR"):
        return {"schema": "enterprise-risk/v1", "id": risk_id, "owner": 1, "subject_sha": digest(self.subject),
            "requirement_ids": [case], "campaign_ids": [], "accountable": "owner-one", "challenger": "independent-person",
            "mechanism": "Synthetic known-unaddressed issue", "population": "synthetic customers", "impact": "HIGH",
            "knowledge": "HYPOTHESIS", "evidence": "MISSING", "treatment": "EXPLICITLY_UNADDRESSED", "acceptance": "NONE",
            "gate_effect": "BLOCK", "exposure": None, "exposure_units": "synthetic loss units", "likelihood_basis": "unknown",
            "reason_unaddressed": "Provider observability unavailable in fixture", "controls": [], "evidence_refs": [],
            "counterevidence": [], "dependencies": [], "next_action": "Obtain independent observation", "review_at": self.time + 1000,
            "reopen_triggers": ["provider change"]}

    def operation(self, action, risk_id="none", patch_sha=None):
        return self.sign("operation", {"schema": "enterprise-operation/v1", "action": action,
            "expected_state_sha": self.engine.inspect("test-run")["state_sha"], "reason": "Synthetic operational test",
            "references": [], "risk_id": risk_id, "patch_sha": patch_sha or digest("no patch"), "observed_mode": "UNKNOWN"}, "operator")
