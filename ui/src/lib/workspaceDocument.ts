import type { SavedWorkspace } from "../types";

const RISK_TIERS = ["R0", "R1", "R2", "R3", "R4"] as const;
const WORKFLOW_TYPES = [
  "new_feature",
  "release",
  "defect",
  "incident",
  "architecture_change",
  "compliance_ask",
  "ai_use_case",
  "vendor_change",
] as const;
const INITIATIVE_STATUSES = ["intake", "discovery", "planned", "executing", "validating", "blocked", "approved", "standardized", "retired"] as const;
const LOOP_RUN_STATUSES = ["not_started", "running", "blocked", "validated", "standardized"] as const;
const STEP_STATUSES = ["open", "done", "blocked"] as const;
const HANDOFF_STATUSES = ["open", "assigned", "closed", "blocked"] as const;
const RELEASE_MODES = ["local_draft", "shadow_release", "gated_release"] as const;
const EXTERNAL_SYSTEMS = ["jira", "github", "manual"] as const;
const EXTERNAL_OBJECT_TYPES = ["issue", "pull_request", "commit", "check", "workflow", "release", "deployment", "manual_note"] as const;
const RELEASE_GATE_STATUSES = ["passed", "gap", "review_required", "exception_active", "blocked"] as const;
const CONNECTOR_MODES = ["not_configured", "export_ready", "shadow_read", "gated_write"] as const;
const WRITE_SCOPES = ["none", "comment", "status_check", "issue_update"] as const;
const EVIDENCE_FRESHNESS = ["fresh", "stale", "missing"] as const;
const INPUT_SOURCE_STATUSES = ["processing", "ready_for_review", "accepted", "error"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.trim().length > 0;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || isString(value);
}

function isOneOf<T extends string>(value: unknown, values: readonly T[]): value is T {
  return isString(value) && values.includes(value as T);
}

function hasStringFields(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return fields.every((field) => isString(value[field]));
}

function isUseCase(value: unknown): boolean {
  return isRecord(value) && hasStringFields(value, [
    "title",
    "description",
    "environment",
    "aiScope",
    "dataSensitivity",
    "businessOutcome",
    "maturity",
    "constraints",
  ]);
}

function isExtractionWarning(value: unknown): boolean {
  return isRecord(value)
    && isOneOf(value.code, ["truncated", "encrypted", "image_only", "parser_warning", "unsupported"] as const)
    && isString(value.message);
}

function isInputSource(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.source_id)
    && isOneOf(value.kind, ["text", "document", "voice"] as const)
    && isString(value.label)
    && isString(value.mime_type)
    && isOneOf(value.status, INPUT_SOURCE_STATUSES)
    && isString(value.accepted_text)
    && isString(value.extraction_method)
    && typeof value.character_count === "number"
    && Number.isInteger(value.character_count)
    && value.character_count >= 0
    && isString(value.created_at)
    && Array.isArray(value.warnings)
    && value.warnings.every(isExtractionWarning)
    && typeof value.truncated === "boolean";
}

function isOwnerEvidenceEdit(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, [
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
    ]);
}

function isApproval(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["approval_id", "loop_id", "request_title", "requested_by", "requested_at", "approver", "evidence_summary", "decision_reason"])
    && isOneOf(value.status, ["Pending", "Approved", "Rejected"] as const)
    && isOneOf(value.risk_tier, RISK_TIERS)
    && isOptionalString(value.decided_at);
}

function isExecutionRecord(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["execution_id", "loop_id", "title", "correlation_id", "state", "evidence_refs", "owner", "created_at", "updated_at"])
    && isOneOf(value.risk_tier, RISK_TIERS)
    && isOneOf(value.validation_result, ["Not Run", "Passed", "Failed", "Inconclusive"] as const)
    && isOneOf(value.proof_state, ["Not Started", "Proof Green", "Proof Failed", "Effectiveness Pending", "Effectiveness Proven"] as const);
}

function isLoopRunStep(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["step_key", "label", "required_evidence", "required_owner", "output", "notes"])
    && isOneOf(value.status, STEP_STATUSES)
    && isStringArray(value.required_controls)
    && isOptionalString(value.completed_at);
}

function isLoopRun(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["run_id", "loop_id", "initiative_id", "current_step", "owner", "created_at", "updated_at"])
    && isOneOf(value.status, LOOP_RUN_STATUSES)
    && Array.isArray(value.step_records)
    && value.step_records.every(isLoopRunStep)
    && isStringArray(value.evidence_refs)
    && isOneOf(value.validation_result, ["Not Run", "Passed", "Failed", "Inconclusive"] as const);
}

function isEvidenceRecord(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["evidence_id", "loop_id", "label", "source", "created_at"])
    && isOneOf(value.freshness, EVIDENCE_FRESHNESS);
}

function isHandoff(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["handoff_id", "from_loop_id", "to_loop_id", "reason", "owner", "due_date", "evidence_ref"])
    && isOneOf(value.status, HANDOFF_STATUSES);
}

function isEffortSavingEstimate(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["initiative_id", "assumptions", "confidence_basis"])
    && ["meetings_avoided", "review_cycles_reduced", "evidence_items_reused", "hours_saved_estimate"].every((field) => typeof value[field] === "number" && Number.isFinite(value[field] as number));
}

function isExternalObjectRef(value: unknown): boolean {
    return isRecord(value)
    && hasStringFields(value, ["ref_id", "label", "observed_at", "evidence_hash"])
    && isOneOf(value.system, EXTERNAL_SYSTEMS)
    && isOneOf(value.object_type, EXTERNAL_OBJECT_TYPES)
    && typeof value.evidence_hash === "string"
    && /^[a-f0-9]{64}$/.test(value.evidence_hash)
    && isOptionalString(value.url);
}

function isEvidenceArtifact(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["artifact_id", "gate_id", "loop_id", "source_ref", "label"])
    && isOneOf(value.freshness, EVIDENCE_FRESHNESS)
    && typeof value.required === "boolean"
    && isOptionalString(value.observed_at);
}

function isGateDecision(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["decision_id", "gate_id", "decided_by", "decided_at", "basis"])
    && isOneOf(value.status, RELEASE_GATE_STATUSES)
    && isStringArray(value.source_ref_ids);
}

function isReleaseGate(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["gate_id", "label", "loop_id", "blocker"])
    && isStringArray(value.control_ids)
    && isStringArray(value.required_evidence)
    && isOneOf(value.status, RELEASE_GATE_STATUSES)
    && (value.last_decision === undefined || isGateDecision(value.last_decision));
}

function isConnectorInstallation(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["connector_id", "label", "trust_boundary"])
    && isOneOf(value.system, EXTERNAL_SYSTEMS)
    && isOneOf(value.mode, CONNECTOR_MODES)
    && isStringArray(value.required_for)
    && isOneOf(value.write_scope, WRITE_SCOPES);
}

function isRiskException(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["exception_id", "gate_id", "reason", "approver", "expires_at"])
    && isStringArray(value.compensating_controls)
    && isOneOf(value.status, ["active", "expired", "closed"] as const);
}

function isMetricObservation(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["metric_id", "label", "basis"])
    && typeof value.value === "number"
    && Number.isFinite(value.value)
    && isOneOf(value.unit, ["hours", "count", "percent"] as const)
    && isStringArray(value.source_ref_ids);
}

function isReleaseAssurance(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["profile_id", "initiative_id", "release_name"])
    && isOneOf(value.operating_mode, RELEASE_MODES)
    && Array.isArray(value.connectors)
    && value.connectors.every(isConnectorInstallation)
    && Array.isArray(value.external_refs)
    && value.external_refs.every(isExternalObjectRef)
    && Array.isArray(value.gates)
    && value.gates.every(isReleaseGate)
    && Array.isArray(value.evidence_artifacts)
    && value.evidence_artifacts.every(isEvidenceArtifact)
    && Array.isArray(value.decisions)
    && value.decisions.every(isGateDecision)
    && Array.isArray(value.exceptions)
    && value.exceptions.every(isRiskException)
    && Array.isArray(value.metric_observations)
    && value.metric_observations.every(isMetricObservation)
    && isStringArray(value.proof_pack_scope);
}

function isInitiative(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["id", "title", "description", "business_outcome", "maturity", "created_at", "updated_at"])
    && isOneOf(value.workflow_type, WORKFLOW_TYPES)
    && isOneOf(value.risk, RISK_TIERS)
    && isOneOf(value.status, INITIATIVE_STATUSES)
    && isStringArray(value.loop_bundle_ids)
    && Array.isArray(value.execution_records)
    && value.execution_records.every(isLoopRun)
    && Array.isArray(value.evidence_records)
    && value.evidence_records.every(isEvidenceRecord)
    && Array.isArray(value.approvals)
    && value.approvals.every(isApproval)
    && Array.isArray(value.handoffs)
    && value.handoffs.every(isHandoff)
    && isEffortSavingEstimate(value.roi_assumptions)
    && (value.release_assurance === undefined || isReleaseAssurance(value.release_assurance));
}

function isQuestionSuggestion(value: unknown): boolean {
  return isRecord(value)
    && hasStringFields(value, ["question_id", "question", "why_it_matters"])
    && isOneOf(value.target_field, ["title", "description", "environment", "aiScope", "dataSensitivity", "businessOutcome", "maturity", "constraints", "ownerEvidence", "approval", "execution"] as const)
    && isOneOf(value.source, ["LLM endpoint", "deterministic fallback"] as const);
}

export function isSavedWorkspaceDocument(value: unknown): value is SavedWorkspace {
  return isRecord(value)
    && isNonEmptyString(value.workspace_id)
    && isNonEmptyString(value.name)
    && isString(value.created_at)
    && isString(value.updated_at)
    && isNonEmptyString(value.owner_user_id)
    && isUseCase(value.use_case)
    && isStringArray(value.selected_loop_ids)
    && isString(value.action_plan_markdown)
    && Array.isArray(value.owner_evidence_edits)
    && value.owner_evidence_edits.every(isOwnerEvidenceEdit)
    && Array.isArray(value.approvals)
    && value.approvals.every(isApproval)
    && Array.isArray(value.execution_records)
    && value.execution_records.every(isExecutionRecord)
    && Array.isArray(value.initiatives)
    && value.initiatives.every(isInitiative)
    && Array.isArray(value.question_suggestions)
    && value.question_suggestions.every(isQuestionSuggestion)
    && Array.isArray(value.input_sources)
    && value.input_sources.every(isInputSource);
}
