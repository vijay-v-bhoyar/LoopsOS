"""Regenerate closed schema assets from these reviewed definitions; no external writes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = {"type": "string", "minLength": 1, "maxLength": 4096}
ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$"}
SHA = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
TIME = {"type": "integer", "minimum": 0}
BOOL = {"type": "boolean"}
NUMBER = {"type": "number", "minimum": 0}


def enum(*values): return {"enum": list(values)}
def array(item=TEXT, minimum=0): return {"type": "array", "items": item, "minItems": minimum, "uniqueItems": True}
def mapping(item): return {"type": "object", "additionalProperties": item}
def obj(properties, optional=()):
    return {"type": "object", "properties": properties, "required": [k for k in properties if k not in optional], "additionalProperties": False}


LIMITS = obj({k: NUMBER for k in (
    "max_detection_seconds", "max_task_error_rate", "max_cohort_loss", "max_stop_seconds",
    "max_unknown_effects", "max_monitor_blind_seconds", "max_review_miss_rate", "max_backlog",
    "max_total_exposure", "max_reconciliation_seconds", "max_eval_delta", "min_samples")})

SUBJECT = obj({"schema": enum("enterprise-subject/v1"), "product": ID, "tenant": ID,
    "environment": enum("ISOLATED_TEST", "SANDBOX", "PRODUCTION"), "workflow": ID,
    "autonomy": {"type": "integer", "minimum": 0, "maximum": 5}, "frontier": enum("ON", "OFF", "UNKNOWN"),
    "manifest": obj({k: SHA for k in ("source", "deployed", "config", "model", "prompt", "tools", "corpus", "memory", "consent", "enforcement")}),
    "provider_identity": TEXT, "permissions": array(TEXT), "data_classes": array(TEXT, 1), "jurisdictions": array(TEXT, 1)})

PROFILE = obj({"schema": enum("enterprise-profile/v1"), "id": ID, "version": enum("1.0.0"),
    "kind": enum("cross-industry", "insurance"), "exposure": enum("ISOLATED_TEST", "SHADOW", "RESTRICTED_READ", "HUMAN_EXECUTED", "BOUNDED_AUTONOMY"),
    "required_proof": enum("FIXTURE", "ENTERPRISE"), "limits": LIMITS,
    "max_repairs": {"type": "integer", "minimum": 1, "maximum": 3},
    "max_events": {"type": "integer", "minimum": 1, "maximum": 100000},
    "run_seconds": {"type": "integer", "minimum": 1}, "max_evidence_age": {"type": "integer", "minimum": 1},
    "waiver_days": {"type": "integer", "minimum": 1, "maximum": 90},
    "nonwaivable_cases": array(ID), "principals": array(ID, 1), "operations": array(TEXT),
    "waiver_compensations": mapping(array(ID, 1)),
    "enterprise_prerequisites": array(ID, 1)})

ISSUER = obj({"public_key": TEXT, "principal": ID, "organization_unit": ID,
    "owners": array({"type": "integer", "minimum": 0, "maximum": 12}),
    "roles": array(enum("collector", "challenger", "risk-executive", "operator", "help-adapter"), 1),
    "test_only": BOOL, "valid_from": TIME, "valid_until": TIME})
TRUST = obj({"schema": enum("enterprise-trust/v1"), "epoch": TIME, "issued_at": TIME, "expires_at": TIME,
    "max_ttl_seconds": {"type": "integer", "minimum": 1}, "evidence_not_before": TIME,
    "issuers": mapping(ISSUER), "approved_profiles": array(SHA, 1), "revoked_profiles": array(SHA),
    "revoked_issuers": array(ID), "revoked_invocations": array(ID), "approved_verifiers": array(SHA, 1)})

ENVELOPE = obj({"schema": enum("enterprise-envelope/v1"), "issuer": ID, "signature": TEXT,
    "body": obj({"purpose": enum("evidence", "risk", "challenge", "waiver", "resume", "help", "operation"),
        "principal": ID, "subject_sha": SHA, "profile_sha": SHA, "run_id": ID,
        "invocation_id": ID, "nonce": ID, "issued_at": TIME, "expires_at": TIME,
        "payload": {"type": "object"}})})
CASE = obj({"case_id": ID, "outcome": enum("PASS", "FAIL", "NOT_RUN", "INCONCLUSIVE", "UNTESTABLE"),
    "observations": mapping({"type": ["number", "boolean", "string"]}),
    "raw_sha": SHA, "reason": TEXT})
EVIDENCE = obj({"schema": enum("enterprise-evidence/v1"), "owner": {"type": "integer", "minimum": 0, "maximum": 12},
    "generation": {"type": "integer", "minimum": 0},
    "proof": enum("FIXTURE", "ENTERPRISE"), "verifier_sha": SHA, "case_manifest_sha": SHA,
    "observed_at": TIME, "scope": enum("APPLICABLE", "NOT_APPLICABLE"), "cases": array(CASE),
    "trial_ids": array(ID), "all_dispatched_trials": array(ID), "raw_manifest": mapping(SHA),
    "limitations": array(TEXT, 1), "dependencies": array(TEXT), "operational_claims": array(ID),
    "model_evidence_expires_at": TIME, "risks": array(ID)})

RISK = obj({"schema": enum("enterprise-risk/v1"), "id": ID, "owner": {"type": "integer", "minimum": 0, "maximum": 12},
    "subject_sha": SHA, "requirement_ids": array(ID, 1), "campaign_ids": array(ID), "accountable": ID,
    "challenger": ID, "mechanism": TEXT, "population": TEXT, "impact": enum("LOW", "MEDIUM", "HIGH", "CRITICAL"),
    "knowledge": enum("OBSERVED", "RESEARCH_SUPPORTED", "HYPOTHESIS", "UNKNOWN"),
    "evidence": enum("VERIFIED_CURRENT", "FAILED", "MISSING", "STALE", "INCONCLUSIVE", "UNTESTABLE"),
    "treatment": enum("OPEN", "IN_PROGRESS", "IMPLEMENTED_UNVERIFIED", "MITIGATED_VERIFIED", "EXPLICITLY_UNADDRESSED", "CLOSED"),
    "acceptance": enum("NONE", "REQUESTED", "VALID", "EXPIRED", "REVOKED"),
    "gate_effect": enum("BLOCK", "RESTRICT", "PERMIT_WITH_VALID_ACCEPTANCE", "NONE_WITH_CURRENT_EVIDENCE"),
    "exposure": {"type": ["number", "null"], "minimum": 0}, "exposure_units": TEXT, "likelihood_basis": TEXT,
    "reason_unaddressed": TEXT, "controls": array(TEXT), "evidence_refs": array(SHA), "counterevidence": array(TEXT),
    "dependencies": array(TEXT), "next_action": TEXT, "review_at": TIME, "reopen_triggers": array(TEXT, 1)})

REVIEW = obj({"schema": enum("enterprise-review/v1"), "manifest_sha": SHA,
    "decision": enum("APPROVE", "VETO"), "conflicts": array(TEXT), "limitations": array(TEXT, 1),
    "findings": array(ID), "criterion_ids": array(ID, 1), "resolves_vetoes": array(SHA)})
WAIVER = obj({"schema": enum("enterprise-waiver/v1"), "risk_id": ID, "risk_sha": SHA,
    "case_ids": array(ID, 1), "compensating_evidence": array(SHA, 1), "exposure_limit": NUMBER,
    "scope": TEXT, "reason": TEXT})
OPERATION = obj({"schema": enum("enterprise-operation/v1"), "action": enum("RESUME", "CANCEL", "SUSPEND", "REPAIR", "MODE_OBSERVED", "MIGRATE"),
    "expected_state_sha": SHA, "reason": TEXT, "references": array(SHA), "risk_id": TEXT,
    "patch_sha": SHA, "observed_mode": enum("UNKNOWN", "DISABLED", "ISOLATED_TEST", "SHADOW", "RESTRICTED_READ", "HUMAN_EXECUTED", "BOUNDED_AUTONOMY")})
HELP = obj({"schema": enum("enterprise-help/v1"), "id": ID, "risk_id": ID, "destination": ID,
    "request": TEXT, "evidence_refs": array(SHA), "risk_while_waiting": TEXT, "deadline": TIME,
    "wake_condition": TEXT, "status": enum("DRAFT", "DELIVERED", "ACKNOWLEDGED", "RESOLVED", "DEAD_LETTER"),
    "attempts": {"type": "integer", "minimum": 0, "maximum": 3}, "delivery_reference": TEXT})
SCHEDULE = obj({"schema": enum("enterprise-schedule/v1"), "id": ID, "due": TIME,
    "interval_seconds": {"type": "integer", "minimum": 1}, "max_dispatches": {"type": "integer", "minimum": 1, "maximum": 1000},
    "max_failures": {"type": "integer", "minimum": 1, "maximum": 3},
    "lease_seconds": {"type": "integer", "minimum": 1, "maximum": 300}})

if __name__ == "__main__":
    for name in ("subject", "profile", "trust", "envelope", "evidence", "risk", "review", "waiver", "operation", "help", "schedule"):
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **globals()[name.upper()]}
        path = ROOT / "schemas" / (name + ".schema.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
