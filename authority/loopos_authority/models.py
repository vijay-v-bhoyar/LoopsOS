from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


RiskTier = Literal["R0", "R1", "R2", "R3", "R4"]
UserRole = Literal["Executive", "Approver", "Operator", "Auditor"]
ReleaseInitiativeStatus = Literal["intake", "discovery", "planned", "executing", "validating", "blocked", "approved", "standardized", "retired"]
ConnectorSystem = Literal["jira", "github", "manual"]
ConnectorEventKind = Literal["issue", "pull_request", "commit", "check", "workflow", "release", "deployment", "manual_note"]
ConnectorVerificationStatus = Literal["session_authenticated", "verified_webhook"]


class Actor(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    user_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    role: UserRole


class DevSessionRequest(Actor):
    ttl_seconds: int = Field(default=3600, ge=60, le=28_800)


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    actor: Actor


class WorkspaceDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: dict[str, Any]

    @field_validator("document")
    @classmethod
    def document_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 1_000_000:
            raise ValueError("Workspace document exceeds 1,000,000 bytes.")
        return value


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

    @field_validator("release_assurance")
    @classmethod
    def release_assurance_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > 500_000:
            raise ValueError("Release assurance payload exceeds 500,000 bytes.")
        return value


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
    payload_hash: str
    payload: dict[str, Any]
    verification_status: ConnectorVerificationStatus
    delivery_id: str | None = None
    created_by: str
    created_at: str


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


class ReleaseProofPack(BaseModel):
    initiative_id: str
    tenant_id: str
    workspace_id: str
    release_name: str
    readiness_verdict: dict[str, Any]
    freshness_summary: dict[str, Any]
    source_event_ids: list[str]
    markdown: str
    markdown_hash: str
    generated_at: str


class ApprovalRequest(BaseModel):
    payload_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    decision_reason: str = Field(min_length=3, max_length=2_000)


class RunCommandResponse(BaseModel):
    run_id: str
    state: str
    runner_status: str


class RunRecord(BaseModel):
    run_id: str
    tenant_id: str
    workspace_id: str
    loop_id: str
    title: str
    trigger: str
    state: str
    runner_status: str
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
