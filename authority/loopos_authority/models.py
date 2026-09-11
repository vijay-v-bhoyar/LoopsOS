from __future__ import annotations

import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


RiskTier = Literal["R0", "R1", "R2", "R3", "R4"]
UserRole = Literal["Executive", "Approver", "Operator", "Auditor"]
RunState = Literal[
    "TRIGGERED", "QUALIFIED", "INPUT_INCOMPLETE", "BLOCKED", "OBSERVED", "DIAGNOSED",
    "INPUT_STALE", "INPUT_CONFLICTED", "INPUT_UNTRUSTED", "PRIORITIZED", "PLANNED",
    "PAUSED", "AUTHORIZED", "ACTION_IN_PROGRESS", "ACTION_APPLIED", "VALIDATION_FAILED",
    "ROLLED_BACK", "VALIDATION_PASSED", "PROOF_GREEN", "PROOF_FAILED", "EFFECTIVENESS_PENDING",
    "EFFECTIVENESS_PROVEN", "EFFECTIVENESS_FAILED", "INSUFFICIENT_EVIDENCE", "CONDITIONAL_ACTIVE",
    "CONDITIONAL_EXPIRED", "RETIRED",
]
RunnerStatus = Literal["idle", "queued", "running", "awaiting_approval", "awaiting_effectiveness", "completed", "failed", "rolled_back"]
ReleaseInitiativeStatus = Literal["intake", "discovery", "planned", "executing", "validating", "blocked", "approved", "standardized", "retired"]
ConnectorSystem = Literal["jira", "github", "manual"]
ConnectorEventKind = Literal["issue", "pull_request", "commit", "check", "workflow", "release", "deployment", "manual_note"]
ConnectorVerificationStatus = Literal["session_authenticated", "verified_webhook"]
SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _workspace_record(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object.")
    return value


def _workspace_strings(value: dict[str, Any], fields: tuple[str, ...], path: str, *, non_empty: bool = False) -> None:
    for field in fields:
        item = value.get(field)
        if not isinstance(item, str) or (non_empty and not item.strip()):
            raise ValueError(f"{path}.{field} must be a {'non-empty ' if non_empty else ''}string.")


def _workspace_optional_string(value: dict[str, Any], field: str, path: str) -> None:
    if field in value and value[field] is not None and not isinstance(value[field], str):
        raise ValueError(f"{path}.{field} must be a string when present.")


def _workspace_enum(value: dict[str, Any], field: str, allowed: tuple[str, ...], path: str) -> None:
    if value.get(field) not in allowed:
        raise ValueError(f"{path}.{field} is not an allowed value.")


def _workspace_strings_array(value: dict[str, Any], field: str, path: str) -> None:
    items = value.get(field)
    if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
        raise ValueError(f"{path}.{field} must be an array of non-empty strings.")


def _workspace_array(value: dict[str, Any], field: str, path: str, validator) -> None:
    items = value.get(field)
    if not isinstance(items, list):
        raise ValueError(f"{path}.{field} must be an array.")
    for index, item in enumerate(items):
        validator(item, f"{path}.{field}[{index}]")


def _validate_workspace_use_case(value: Any, path: str) -> None:
    _workspace_strings(_workspace_record(value, path), (
        "title",
        "description",
        "environment",
        "aiScope",
        "dataSensitivity",
        "businessOutcome",
        "maturity",
        "constraints",
    ), path)


def _validate_workspace_warning(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_enum(record, "code", ("truncated", "encrypted", "image_only", "parser_warning", "unsupported"), path)
    _workspace_strings(record, ("message",), path)


def _validate_workspace_input_source(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("source_id", "label", "mime_type", "accepted_text", "extraction_method", "created_at"), path, non_empty=True)
    _workspace_enum(record, "kind", ("text", "document", "voice"), path)
    _workspace_enum(record, "status", ("processing", "ready_for_review", "accepted", "error"), path)
    character_count = record.get("character_count")
    if not isinstance(character_count, int) or isinstance(character_count, bool) or character_count < 0:
        raise ValueError(f"{path}.character_count must be a non-negative integer.")
    if not isinstance(record.get("truncated"), bool):
        raise ValueError(f"{path}.truncated must be boolean.")
    _workspace_array(record, "warnings", path, _validate_workspace_warning)


def _validate_workspace_owner_evidence(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, (
        "edit_id",
        "loop_id",
        "owner_ref",
        "policy_owner",
        "gate_owner",
        "risk_owner",
        "evidence_ref",
        "authoritative_location",
        "freshness_policy",
        "retention_policy",
        "edited_by",
        "edited_at",
    ), path)


def _validate_workspace_approval(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("approval_id", "loop_id", "request_title", "requested_by", "requested_at", "approver", "evidence_summary", "decision_reason"), path)
    _workspace_enum(record, "status", ("Pending", "Approved", "Rejected"), path)
    _workspace_enum(record, "risk_tier", ("R0", "R1", "R2", "R3", "R4"), path)
    _workspace_optional_string(record, "decided_at", path)


def _validate_workspace_execution(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("execution_id", "loop_id", "title", "correlation_id", "state", "evidence_refs", "owner", "created_at", "updated_at"), path)
    _workspace_enum(record, "risk_tier", ("R0", "R1", "R2", "R3", "R4"), path)
    _workspace_enum(record, "validation_result", ("Not Run", "Passed", "Failed", "Inconclusive"), path)
    _workspace_enum(record, "proof_state", ("Not Started", "Proof Green", "Proof Failed", "Effectiveness Pending", "Effectiveness Proven"), path)


def _validate_workspace_step(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("step_key", "label", "required_evidence", "required_owner", "output", "notes"), path)
    _workspace_enum(record, "status", ("open", "done", "blocked"), path)
    _workspace_strings_array(record, "required_controls", path)
    _workspace_optional_string(record, "completed_at", path)


def _validate_workspace_run(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("run_id", "loop_id", "initiative_id", "current_step", "owner", "created_at", "updated_at"), path)
    _workspace_enum(record, "status", ("not_started", "running", "blocked", "validated", "standardized"), path)
    _workspace_array(record, "step_records", path, _validate_workspace_step)
    _workspace_strings_array(record, "evidence_refs", path)
    _workspace_enum(record, "validation_result", ("Not Run", "Passed", "Failed", "Inconclusive"), path)


def _validate_workspace_evidence(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("evidence_id", "loop_id", "label", "source", "created_at"), path)
    _workspace_enum(record, "freshness", ("fresh", "stale", "missing"), path)


def _validate_workspace_handoff(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("handoff_id", "from_loop_id", "to_loop_id", "reason", "owner", "due_date", "evidence_ref"), path)
    _workspace_enum(record, "status", ("open", "assigned", "closed", "blocked"), path)


def _validate_workspace_roi(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("initiative_id", "assumptions", "confidence_basis"), path)
    for field in ("meetings_avoided", "review_cycles_reduced", "evidence_items_reused", "hours_saved_estimate"):
        item = record.get(field)
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{path}.{field} must be a finite number.")


def _validate_workspace_external_ref(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("ref_id", "label", "observed_at", "evidence_hash"), path)
    _workspace_enum(record, "system", ("jira", "github", "manual"), path)
    _workspace_enum(record, "object_type", ("issue", "pull_request", "commit", "check", "workflow", "release", "deployment", "manual_note"), path)
    _workspace_optional_string(record, "url", path)
    if SHA256_HEX_PATTERN.fullmatch(record["evidence_hash"]) is None:
        raise ValueError(f"{path}.evidence_hash must be a lowercase SHA-256 hex digest.")


def _validate_workspace_artifact(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("artifact_id", "gate_id", "loop_id", "source_ref", "label"), path)
    _workspace_enum(record, "freshness", ("fresh", "stale", "missing"), path)
    if not isinstance(record.get("required"), bool):
        raise ValueError(f"{path}.required must be boolean.")
    _workspace_optional_string(record, "observed_at", path)


def _validate_workspace_decision(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("decision_id", "gate_id", "decided_by", "decided_at", "basis"), path)
    _workspace_enum(record, "status", ("passed", "gap", "review_required", "exception_active", "blocked"), path)
    _workspace_strings_array(record, "source_ref_ids", path)


def _validate_workspace_gate(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("gate_id", "label", "loop_id", "blocker"), path)
    _workspace_strings_array(record, "control_ids", path)
    _workspace_strings_array(record, "required_evidence", path)
    _workspace_enum(record, "status", ("passed", "gap", "review_required", "exception_active", "blocked"), path)
    if "last_decision" in record and record["last_decision"] is not None:
        _validate_workspace_decision(record["last_decision"], f"{path}.last_decision")


def _validate_workspace_connector(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("connector_id", "label", "trust_boundary"), path)
    _workspace_enum(record, "system", ("jira", "github", "manual"), path)
    _workspace_enum(record, "mode", ("not_configured", "export_ready", "shadow_read", "gated_write"), path)
    _workspace_strings_array(record, "required_for", path)
    _workspace_enum(record, "write_scope", ("none", "comment", "status_check", "issue_update"), path)


def _validate_workspace_exception(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("exception_id", "gate_id", "reason", "approver", "expires_at"), path)
    _workspace_strings_array(record, "compensating_controls", path)
    _workspace_enum(record, "status", ("active", "expired", "closed"), path)


def _validate_workspace_metric(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("metric_id", "label", "basis"), path)
    item = record.get("value")
    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
        raise ValueError(f"{path}.value must be a finite number.")
    _workspace_enum(record, "unit", ("hours", "count", "percent"), path)
    _workspace_strings_array(record, "source_ref_ids", path)


def _validate_workspace_release_assurance(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("profile_id", "initiative_id", "release_name"), path, non_empty=True)
    _workspace_enum(record, "operating_mode", ("local_draft", "shadow_release", "gated_release"), path)
    _workspace_array(record, "connectors", path, _validate_workspace_connector)
    _workspace_array(record, "external_refs", path, _validate_workspace_external_ref)
    _workspace_array(record, "gates", path, _validate_workspace_gate)
    _workspace_array(record, "evidence_artifacts", path, _validate_workspace_artifact)
    _workspace_array(record, "decisions", path, _validate_workspace_decision)
    _workspace_array(record, "exceptions", path, _validate_workspace_exception)
    _workspace_array(record, "metric_observations", path, _validate_workspace_metric)
    _workspace_strings_array(record, "proof_pack_scope", path)

    limits = {
        "connectors": 20,
        "external_refs": 200,
        "gates": 200,
        "evidence_artifacts": 500,
        "decisions": 500,
        "exceptions": 200,
        "metric_observations": 200,
        "proof_pack_scope": 100,
    }
    for field, limit in limits.items():
        if len(record[field]) > limit:
            raise ValueError(f"{path}.{field} exceeds the {limit}-item limit.")

    def require_unique_ids(field: str, id_field: str) -> set[str]:
        ids = [item[id_field] for item in record[field]]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{path}.{field} IDs must be unique.")
        return set(ids)

    require_unique_ids("connectors", "connector_id")
    external_ref_ids = require_unique_ids("external_refs", "ref_id")
    gate_ids = require_unique_ids("gates", "gate_id")
    require_unique_ids("evidence_artifacts", "artifact_id")
    require_unique_ids("decisions", "decision_id")
    require_unique_ids("exceptions", "exception_id")
    require_unique_ids("metric_observations", "metric_id")

    decisions_by_gate: dict[str, dict[str, Any]] = {}
    for index, decision in enumerate(record["decisions"]):
        gate_id = decision["gate_id"]
        if gate_id not in gate_ids:
            raise ValueError(f"{path}.decisions[{index}].gate_id must reference a release gate.")
        if gate_id in decisions_by_gate:
            raise ValueError(f"{path}.decisions must contain at most one current decision per gate.")
        decisions_by_gate[gate_id] = decision

    for index, gate in enumerate(record["gates"]):
        gate_id = gate["gate_id"]
        last_decision = gate.get("last_decision")
        decision = last_decision or decisions_by_gate.get(gate_id)
        if decision is None:
            raise ValueError(f"{path}.gates[{index}] must have a current human decision.")
        if decision["gate_id"] != gate_id or decision["status"] != gate["status"]:
            raise ValueError(f"{path}.gates[{index}] decision must match the current gate status.")
        if any(ref_id not in external_ref_ids for ref_id in decision["source_ref_ids"]):
            raise ValueError(f"{path}.gates[{index}] decision references an unknown external object.")
        if last_decision is not None and last_decision["decision_id"] != decision["decision_id"]:
            raise ValueError(f"{path}.gates[{index}].last_decision must match the current gate decision.")

    for field in ("evidence_artifacts", "exceptions"):
        for index, item in enumerate(record[field]):
            if item["gate_id"] not in gate_ids:
                raise ValueError(f"{path}.{field}[{index}].gate_id must reference a release gate.")
    for index, item in enumerate(record["evidence_artifacts"]):
        if item["source_ref"] not in external_ref_ids:
            raise ValueError(f"{path}.evidence_artifacts[{index}].source_ref must reference an external object.")
    for index, item in enumerate(record["metric_observations"]):
        if any(ref_id not in external_ref_ids for ref_id in item["source_ref_ids"]):
            raise ValueError(f"{path}.metric_observations[{index}] references an unknown external object.")
    return record


def validate_release_assurance(value: Any) -> dict[str, Any]:
    return _validate_workspace_release_assurance(value, "release_assurance")


def _validate_workspace_initiative(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("id", "title", "description", "business_outcome", "maturity", "created_at", "updated_at"), path)
    _workspace_enum(record, "workflow_type", ("new_feature", "release", "defect", "incident", "architecture_change", "compliance_ask", "ai_use_case", "vendor_change"), path)
    _workspace_enum(record, "risk", ("R0", "R1", "R2", "R3", "R4"), path)
    _workspace_enum(record, "status", ("intake", "discovery", "planned", "executing", "validating", "blocked", "approved", "standardized", "retired"), path)
    _workspace_strings_array(record, "loop_bundle_ids", path)
    _workspace_array(record, "execution_records", path, _validate_workspace_run)
    _workspace_array(record, "evidence_records", path, _validate_workspace_evidence)
    _workspace_array(record, "approvals", path, _validate_workspace_approval)
    _workspace_array(record, "handoffs", path, _validate_workspace_handoff)
    _validate_workspace_roi(record.get("roi_assumptions"), f"{path}.roi_assumptions")
    if "release_assurance" in record and record["release_assurance"] is not None:
        _validate_workspace_release_assurance(record["release_assurance"], f"{path}.release_assurance")


def _validate_workspace_question(value: Any, path: str) -> None:
    record = _workspace_record(value, path)
    _workspace_strings(record, ("question_id", "question", "why_it_matters"), path)
    _workspace_enum(record, "target_field", ("title", "description", "environment", "aiScope", "dataSensitivity", "businessOutcome", "maturity", "constraints", "ownerEvidence", "approval", "execution"), path)
    _workspace_enum(record, "source", ("LLM endpoint", "deterministic fallback"), path)


def validate_workspace_document(value: Any) -> dict[str, Any]:
    record = _workspace_record(value, "document")
    _workspace_strings(record, ("workspace_id", "name", "created_at", "updated_at", "owner_user_id"), "document", non_empty=True)
    _validate_workspace_use_case(record.get("use_case"), "document.use_case")
    _workspace_strings_array(record, "selected_loop_ids", "document")
    _workspace_strings(record, ("action_plan_markdown",), "document")
    _workspace_array(record, "owner_evidence_edits", "document", _validate_workspace_owner_evidence)
    _workspace_array(record, "approvals", "document", _validate_workspace_approval)
    _workspace_array(record, "execution_records", "document", _validate_workspace_execution)
    _workspace_array(record, "initiatives", "document", _validate_workspace_initiative)
    _workspace_array(record, "question_suggestions", "document", _validate_workspace_question)
    _workspace_array(record, "input_sources", "document", _validate_workspace_input_source)
    return record


class Actor(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    user_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    role: UserRole


class DevSessionRequest(Actor):
    ttl_seconds: int = Field(default=3600, ge=60, le=28_800)


ENTERPRISE_SESSION_MAX_SECONDS = 900


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(ge=1, le=28_800)
    actor: Actor


class EnterpriseSessionResponse(SessionResponse):
    expires_in: int = Field(ge=1, le=ENTERPRISE_SESSION_MAX_SECONDS)


class WorkspaceDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: dict[str, Any]

    @field_validator("document")
    @classmethod
    def document_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 1_000_000:
            raise ValueError("Workspace document exceeds 1,000,000 bytes.")
        return validate_workspace_document(value)


class WorkspaceRecord(BaseModel):
    workspace_id: str
    tenant_id: str
    revision: int
    document: dict[str, Any]
    document_hash: str
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str

    @field_validator("document")
    @classmethod
    def document_matches_contract(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_workspace_document(value)


class EvidenceRequest(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    kind: Literal["workspace_snapshot", "http_json"]
    source_ref: str = Field(min_length=1, max_length=2_000)
    content: dict[str, Any] | None = None
    freshness_seconds: int = Field(default=3600, ge=1, le=31_536_000)

    @field_validator("content")
    @classmethod
    def content_is_bounded(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 200_000:
            raise ValueError("Evidence content exceeds 200,000 bytes.")
        return value


class ToolAction(BaseModel):
    tool: Literal["record_action", "http_json_action"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=200)
    external_effect: bool = False

    @field_validator("arguments")
    @classmethod
    def arguments_are_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 100_000:
            raise ValueError("Tool arguments exceed 100,000 bytes.")
        return value

    @model_validator(mode="after")
    def external_effect_matches_tool_authority(self) -> "ToolAction":
        if self.tool == "http_json_action" and not self.external_effect:
            raise ValueError("http_json_action is always an external-effect action.")
        if self.tool == "record_action" and self.external_effect:
            raise ValueError("record_action cannot be declared as an external-effect action.")
        return self


class ProbeSpec(BaseModel):
    probe_id: str = Field(min_length=1, max_length=120)
    kind: Literal["json_equals", "evidence_present", "http_json_equals"]
    target: Literal["action_output", "evidence"] = "action_output"
    path: str = Field(default="", max_length=500)
    expected: Any = None
    endpoint: HttpUrl | None = None

    @model_validator(mode="after")
    def connected_probe_requires_endpoint(self) -> "ProbeSpec":
        if self.kind == "http_json_equals" and self.endpoint is None:
            raise ValueError("http_json_equals requires an endpoint.")
        return self


class EnterpriseRuntimeContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_decision_ref: str = Field(min_length=1, max_length=240)
    sandbox_profile_ref: str = Field(min_length=1, max_length=240)
    idempotency_scope: Literal["tenant_workflow_tool_payload"]
    evidence_refs: list[str] = Field(min_length=1, max_length=20)


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: list[EvidenceRequest] = Field(min_length=1, max_length=20)
    action: ToolAction
    validation_probes: list[ProbeSpec] = Field(min_length=1, max_length=20)
    effectiveness_probes: list[ProbeSpec] = Field(min_length=1, max_length=20)
    rollback: ToolAction | None = None
    enterprise_context: EnterpriseRuntimeContext | None = None
    max_attempts: int = Field(default=3, ge=1, le=5)
    observation_delay_seconds: int = Field(default=0, ge=0, le=604_800)

    @model_validator(mode="after")
    def rollback_required_for_external_effect(self) -> "ExecutionPlan":
        if self.action.external_effect and self.rollback is None:
            raise ValueError("An external-effect action requires a rollback or compensating action contract.")
        return self


class CreateRunRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=160)
    loop_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=240)
    trigger: str = Field(min_length=1, max_length=2_000)
    requested_risk_tier: RiskTier = "R1"
    plan: ExecutionPlan


class CreateReleaseInitiativeRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4_000)
    workflow_type: Literal["release", "new_feature", "defect", "incident", "architecture_change", "compliance_ask", "ai_use_case", "vendor_change"] = "release"
    business_outcome: str = Field(min_length=1, max_length=2_000)
    maturity: str = Field(min_length=1, max_length=120)
    risk_tier: RiskTier = "R2"
    status: ReleaseInitiativeStatus = "planned"
    release_name: str = Field(min_length=1, max_length=240)
    loop_bundle_ids: list[str] = Field(min_length=1, max_length=30)
    source_event_ids: list[str] = Field(default_factory=list, max_length=100)
    release_assurance: dict[str, Any]

    @field_validator("loop_bundle_ids")
    @classmethod
    def loop_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Loop bundle IDs must be unique.")
        return value

    @field_validator("source_event_ids")
    @classmethod
    def source_event_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Source connector event IDs must be unique.")
        return value

    @field_validator("release_assurance")
    @classmethod
    def release_assurance_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 500_000:
            raise ValueError("Release assurance payload exceeds 500,000 bytes.")
        return validate_release_assurance(value)


class ConnectorEventRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=160)
    system: ConnectorSystem
    event_kind: ConnectorEventKind
    external_id: str = Field(min_length=1, max_length=300)
    label: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2_000)
    observed_at: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any]
    verification_status: ConnectorVerificationStatus = "session_authenticated"
    delivery_id: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def verified_webhook_requires_delivery_id(self) -> "ConnectorEventRequest":
        if self.verification_status == "verified_webhook" and not self.delivery_id:
            raise ValueError("Provider-verified connector events require a provider delivery identifier.")
        return self

    @field_validator("payload")
    @classmethod
    def payload_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 500_000:
            raise ValueError("Connector event payload exceeds 500,000 bytes.")
        return value

    @field_validator("url")
    @classmethod
    def url_has_no_embedded_credentials(cls, value: str | None) -> str | None:
        if value and "@" in value.split("://", 1)[-1].split("/", 1)[0]:
            raise ValueError("Connector event URL cannot contain embedded credentials.")
        return value


class RecordReleaseInitiativeRequest(BaseModel):
    initiative: CreateReleaseInitiativeRequest
    connector_events: list[ConnectorEventRequest] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def evidence_matches_initiative_workspace(self) -> "RecordReleaseInitiativeRequest":
        mismatched = sorted({event.workspace_id for event in self.connector_events if event.workspace_id != self.initiative.workspace_id})
        if mismatched:
            raise ValueError("All connector evidence must belong to the release initiative workspace.")
        if self.initiative.source_event_ids:
            raise ValueError("Atomic release recording derives source event IDs from the submitted connector evidence.")
        return self


class ConnectorEventRecord(BaseModel):
    connector_event_id: str
    tenant_id: str
    workspace_id: str
    system: ConnectorSystem
    event_kind: ConnectorEventKind
    external_id: str
    label: str
    url: str | None = None
    observed_at: str
    payload_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, Any]
    verification_status: ConnectorVerificationStatus
    delivery_id: str | None = None
    created_by: str
    created_at: str


class RecordReleaseInitiativeResponse(BaseModel):
    initiative: "ReleaseInitiativeRecord"
    connector_events: list[ConnectorEventRecord]


class ReleaseInitiativeRecord(BaseModel):
    initiative_id: str
    tenant_id: str
    workspace_id: str
    title: str
    description: str
    workflow_type: str
    business_outcome: str
    maturity: str
    risk_tier: RiskTier
    status: ReleaseInitiativeStatus
    release_name: str
    loop_bundle_ids: list[str]
    source_event_ids: list[str]
    release_assurance: dict[str, Any]
    freshness_summary: dict[str, Any] = Field(default_factory=dict)
    readiness_verdict: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: str
    updated_at: str

    @field_validator("release_assurance")
    @classmethod
    def release_assurance_matches_contract(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_release_assurance(value)


class ReleaseProofPack(BaseModel):
    initiative_id: str
    tenant_id: str
    workspace_id: str
    release_name: str
    readiness_verdict: dict[str, Any]
    freshness_summary: dict[str, Any]
    source_event_ids: list[str]
    markdown: str
    markdown_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    generated_at: str


class ApprovalRequest(BaseModel):
    payload_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    decision_reason: str = Field(min_length=3, max_length=2_000)


class RunCommandResponse(BaseModel):
    run_id: str
    state: RunState
    runner_status: RunnerStatus


class ApprovalCommandResponse(BaseModel):
    approval_id: str
    status: Literal["approved"]


class RejectionCommandResponse(BaseModel):
    decision_id: str
    status: Literal["rejected"]


class KillSwitchRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2_000)


class KillSwitchStatus(BaseModel):
    tenant_id: str
    scope: Literal["tenant"] = "tenant"
    active: bool
    activation_id: str | None = None
    reason: str | None = None
    actor_id: str | None = None
    activated_at: str | None = None
    deactivated_at: str | None = None
    deactivated_by: str | None = None
    deactivation_reason: str | None = None
    semantics: Literal["pre_dispatch_block_and_in_flight_interrupt"] = "pre_dispatch_block_and_in_flight_interrupt"


class RunRecord(BaseModel):
    run_id: str
    tenant_id: str
    workspace_id: str
    loop_id: str
    title: str
    trigger: str
    state: RunState
    runner_status: RunnerStatus
    risk_tier: RiskTier
    requires_approval: bool
    payload_hash: str
    plan: ExecutionPlan
    attempt: int
    created_by: str
    created_at: str
    updated_at: str
    last_error: str | None = None
    output: dict[str, Any] | None = None
    recovery_of: str | None = None
    effectiveness_due_at: str | None = None


class AuditVerification(BaseModel):
    tenant_id: str
    valid: bool
    event_count: int
    first_invalid_sequence: int | None = None
