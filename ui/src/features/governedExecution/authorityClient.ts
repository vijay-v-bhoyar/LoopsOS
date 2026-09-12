import type { EnterpriseUser, ReleaseAssuranceProfile, SavedWorkspace } from "../../types";
import { deploymentPosture, isUnsafeAuthorityHostname, type AuthorityConfigurationContract, type DeploymentMode } from "../../lib/deployment";
import { allowedHostsForConfiguredEndpoint, assertAllowedEndpoint } from "../../lib/secureRequest";
import { isSavedWorkspaceDocument } from "../../lib/workspaceDocument";
import type { ApprovalCommandResponse, AuditVerification, AuthorityEvent, AuthoritySession, ConnectorEventInput, ConnectorEventRecord, CreateGovernedRun, CreateReleaseInitiative, GovernedExecutionPlan, GovernedRun, GovernedRunState, GovernedRunnerStatus, KillSwitchStatus, RecordReleaseInitiativeResponse, RejectionCommandResponse, ReleaseInitiativeRecord, ReleaseProofPack, RunCommandResponse } from "./types";

const CONFIGURED_AUTHORITY_BASE = (import.meta.env.VITE_LOOPOS_AUTHORITY_URL as string | undefined)?.trim() || "/api";

export class AuthorityError extends Error {
  constructor(message: string, readonly status?: number, readonly requestId?: string) {
    super(message);
  }
}

export interface AuthorityWorkspaceRecord {
  workspace_id: string;
  tenant_id: string;
  revision: number;
  document: SavedWorkspace;
  document_hash: string;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export function resolveAuthorityBase(
  configuredBase: string | undefined,
  allowedHosts: string[],
  baseOrigin = window.location.origin,
): string {
  const endpoint = (configuredBase?.trim() || "/api").replace(/\/$/, "") || "/";
  const url = assertAllowedEndpoint(endpoint, allowedHosts, baseOrigin);
  const currentOrigin = new URL(baseOrigin).origin;
  if (url.origin === currentOrigin) return url.pathname.replace(/\/$/, "") || "";
  return url.toString().replace(/\/$/, "");
}

function authorityBase(): string {
  const allowedHosts = deploymentPosture.mode === "enterprise"
    ? deploymentPosture.authorityAllowedHosts
    : allowedHostsForConfiguredEndpoint(CONFIGURED_AUTHORITY_BASE);
  try {
    return resolveAuthorityBase(CONFIGURED_AUTHORITY_BASE, allowedHosts);
  } catch (error) {
    const detail = error instanceof Error ? error.message : "The configured authority origin is invalid.";
    throw new AuthorityError(`Authority endpoint is invalid: ${detail}`);
  }
}

export interface AuthorityReadiness {
  status: "ready";
  development_auth: boolean;
  rate_limit_configured: boolean;
  storage_backend: string;
  production_identity: boolean;
  credential_injection_broker_verified: boolean;
  audit_anchor_configured: boolean;
  audit_anchor_backlog: number;
  audit_anchor_delivery_verified: boolean;
  audit_anchor_delivery_fresh: boolean;
  audit_anchor_last_delivered_at: string | null;
  execution_job_backlog: number;
  execution_worker_dispatch: {
    verified: boolean;
    source: "internal" | "external";
    observed_at: string;
    age_seconds: number;
    detail: Record<string, unknown>;
  };
  operational_bindings: {
    retention_verified: boolean;
    support_verified: boolean;
    outbound_policy_verified: boolean;
    backup_restore_verified: boolean;
    worker_dispatch_verified: boolean;
  };
  configuration_contract: AuthorityConfigurationContract;
  backup_restore_evidence: {
    url: string | null;
    sha256: string | null;
    verified_at: string | null;
  };
  operational_evidence: {
    url: string | null;
    sha256: string | null;
    verified_at: string | null;
    binding_fingerprint: string;
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isIsoTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || !value.trim() || !Number.isFinite(Date.parse(value))) return false;
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value.trim());
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isCredentialFreeHttpsUrl(value: unknown): value is string {
  if (!isNonEmptyString(value) || value.includes("\\")) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:"
      && Boolean(url.hostname)
      && !isUnsafeAuthorityHostname(url.hostname)
      && !url.username
      && !url.password
      && !url.search
      && !url.hash;
  } catch {
    return false;
  }
}

function isAuthorityRole(value: unknown): value is EnterpriseUser["role"] {
  return value === "Executive" || value === "Approver" || value === "Operator" || value === "Auditor";
}

function isExternalSystem(value: unknown): boolean {
  return value === "jira" || value === "github" || value === "manual";
}

function isExternalObjectType(value: unknown): boolean {
  return value === "issue"
    || value === "pull_request"
    || value === "commit"
    || value === "check"
    || value === "workflow"
    || value === "release"
    || value === "deployment"
    || value === "manual_note";
}

function isReleaseGateStatus(value: unknown): boolean {
  return value === "passed"
    || value === "gap"
    || value === "review_required"
    || value === "exception_active"
    || value === "blocked";
}

function isConnectorMode(value: unknown): boolean {
  return value === "not_configured" || value === "export_ready" || value === "shadow_read" || value === "gated_write";
}

function isExternalObjectRef(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.ref_id)
    && isExternalSystem(value.system)
    && isExternalObjectType(value.object_type)
    && isNonEmptyString(value.label)
    && (value.url === undefined || isNonEmptyString(value.url))
    && isIsoTimestamp(value.observed_at)
    && isSha256(value.evidence_hash);
}

function isEvidenceArtifact(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.artifact_id)
    && isNonEmptyString(value.gate_id)
    && isNonEmptyString(value.loop_id)
    && isNonEmptyString(value.source_ref)
    && isNonEmptyString(value.label)
    && (value.freshness === "fresh" || value.freshness === "stale" || value.freshness === "missing")
    && typeof value.required === "boolean"
    && (value.observed_at === undefined || isIsoTimestamp(value.observed_at));
}

function isGateDecision(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.decision_id)
    && isNonEmptyString(value.gate_id)
    && isReleaseGateStatus(value.status)
    && isNonEmptyString(value.decided_by)
    && isIsoTimestamp(value.decided_at)
    && isNonEmptyString(value.basis)
    && isStringArray(value.source_ref_ids);
}

function isReleaseGate(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.gate_id)
    && isNonEmptyString(value.label)
    && isNonEmptyString(value.loop_id)
    && isStringArray(value.control_ids)
    && isStringArray(value.required_evidence)
    && isReleaseGateStatus(value.status)
    && isNonEmptyString(value.blocker)
    && (value.last_decision === undefined || isGateDecision(value.last_decision));
}

function isConnectorInstallation(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.connector_id)
    && isExternalSystem(value.system)
    && isConnectorMode(value.mode)
    && isNonEmptyString(value.label)
    && isStringArray(value.required_for)
    && (value.write_scope === "none" || value.write_scope === "comment" || value.write_scope === "status_check" || value.write_scope === "issue_update")
    && isNonEmptyString(value.trust_boundary);
}

function isRiskException(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.exception_id)
    && isNonEmptyString(value.gate_id)
    && isNonEmptyString(value.reason)
    && isNonEmptyString(value.approver)
    && isIsoTimestamp(value.expires_at)
    && isStringArray(value.compensating_controls)
    && (value.status === "active" || value.status === "expired" || value.status === "closed");
}

function isMetricObservation(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.metric_id)
    && isNonEmptyString(value.label)
    && typeof value.value === "number"
    && Number.isFinite(value.value)
    && (value.unit === "hours" || value.unit === "count" || value.unit === "percent")
    && isNonEmptyString(value.basis)
    && isStringArray(value.source_ref_ids);
}

function isSha256(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}

function isNullableSha256(value: unknown): value is string | null {
  return value === null || isSha256(value);
}

function isRiskTier(value: unknown): boolean {
  return value === "R0" || value === "R1" || value === "R2" || value === "R3" || value === "R4";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isNonEmptyString);
}

function isIntegerRecord(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every(isNonNegativeInteger);
}

function isFreshnessSummary(value: unknown): boolean {
  if (value === undefined) return true;
  if (!isRecord(value)
    || (value.status !== undefined && value.status !== "fresh" && value.status !== "stale" && value.status !== "missing")
    || (value.policy !== undefined && !isNonEmptyString(value.policy))
    || (value.max_age_seconds !== undefined && !isNonNegativeInteger(value.max_age_seconds))
    || (value.evaluated_at !== undefined && !isIsoTimestamp(value.evaluated_at))
    || (value.source_event_count !== undefined && !isNonNegativeInteger(value.source_event_count))
    || (value.verified_webhook_count !== undefined && !isNonNegativeInteger(value.verified_webhook_count))
    || (value.session_authenticated_count !== undefined && !isNonNegativeInteger(value.session_authenticated_count))
    || (value.stale_event_ids !== undefined && !isStringArray(value.stale_event_ids))
    || (value.invalid_observed_at_event_ids !== undefined && !isStringArray(value.invalid_observed_at_event_ids))
    || (value.oldest_observed_at !== undefined && !(value.oldest_observed_at === null || isIsoTimestamp(value.oldest_observed_at)))
    || (value.newest_observed_at !== undefined && !(value.newest_observed_at === null || isIsoTimestamp(value.newest_observed_at)))) {
    return false;
  }
  return true;
}

function isReadinessVerdict(value: unknown): boolean {
  if (value === undefined) return true;
  return isRecord(value)
    && (value.verdict === undefined || value.verdict === "GO" || value.verdict === "NO_GO" || value.verdict === "REVIEW_REQUIRED")
    && (value.evaluated_at === undefined || isIsoTimestamp(value.evaluated_at))
    && (value.policy === undefined || isNonEmptyString(value.policy))
    && (value.gate_status_counts === undefined || isIntegerRecord(value.gate_status_counts))
    && (value.failing_reasons === undefined || isStringArray(value.failing_reasons))
    && (value.review_reasons === undefined || isStringArray(value.review_reasons));
}

function isReleaseAssuranceProfile(value: unknown): value is ReleaseAssuranceProfile {
  return isRecord(value)
    && isNonEmptyString(value.profile_id)
    && isNonEmptyString(value.initiative_id)
    && isNonEmptyString(value.release_name)
    && (value.operating_mode === "local_draft" || value.operating_mode === "shadow_release" || value.operating_mode === "gated_release")
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

function isReleaseWorkflowType(value: unknown): boolean {
  return value === "new_feature"
    || value === "release"
    || value === "defect"
    || value === "incident"
    || value === "architecture_change"
    || value === "compliance_ask"
    || value === "ai_use_case"
    || value === "vendor_change";
}

function isReleaseInitiativeStatus(value: unknown): boolean {
  return value === "intake"
    || value === "discovery"
    || value === "planned"
    || value === "executing"
    || value === "validating"
    || value === "blocked"
    || value === "approved"
    || value === "standardized"
    || value === "retired";
}

function isReleaseInitiativeRecord(value: unknown): value is ReleaseInitiativeRecord {
  return isRecord(value)
    && isNonEmptyString(value.initiative_id)
    && isNonEmptyString(value.tenant_id)
    && isNonEmptyString(value.workspace_id)
    && isNonEmptyString(value.title)
    && isNonEmptyString(value.description)
    && isReleaseWorkflowType(value.workflow_type)
    && isNonEmptyString(value.business_outcome)
    && isNonEmptyString(value.maturity)
    && isRiskTier(value.risk_tier)
    && isReleaseInitiativeStatus(value.status)
    && isNonEmptyString(value.release_name)
    && isStringArray(value.loop_bundle_ids)
    && isStringArray(value.source_event_ids)
    && isReleaseAssuranceProfile(value.release_assurance)
    && isFreshnessSummary(value.freshness_summary)
    && isReadinessVerdict(value.readiness_verdict)
    && isNonEmptyString(value.created_by)
    && isIsoTimestamp(value.created_at)
    && isIsoTimestamp(value.updated_at);
}

function isConnectorSystem(value: unknown): boolean {
  return value === "jira" || value === "github" || value === "manual";
}

function isConnectorEventKind(value: unknown): boolean {
  return value === "issue"
    || value === "pull_request"
    || value === "commit"
    || value === "check"
    || value === "workflow"
    || value === "release"
    || value === "deployment"
    || value === "manual_note";
}

function isConnectorEventRecord(value: unknown): value is ConnectorEventRecord {
  return isRecord(value)
    && isNonEmptyString(value.connector_event_id)
    && isNonEmptyString(value.tenant_id)
    && isNonEmptyString(value.workspace_id)
    && isConnectorSystem(value.system)
    && isConnectorEventKind(value.event_kind)
    && isNonEmptyString(value.external_id)
    && isNonEmptyString(value.label)
    && isNullableString(value.url)
    && isIsoTimestamp(value.observed_at)
    && isSha256(value.payload_hash)
    && isRecord(value.payload)
    && (value.verification_status === "session_authenticated" || value.verification_status === "verified_webhook")
    && isNullableString(value.delivery_id)
    && isNonEmptyString(value.created_by)
    && isIsoTimestamp(value.created_at);
}

function isRecordReleaseInitiativeResponse(value: unknown): value is RecordReleaseInitiativeResponse {
  return isRecord(value)
    && isReleaseInitiativeRecord(value.initiative)
    && Array.isArray(value.connector_events)
    && value.connector_events.every(isConnectorEventRecord);
}

function isReleaseProofPack(value: unknown): value is ReleaseProofPack {
  return isRecord(value)
    && isNonEmptyString(value.initiative_id)
    && isNonEmptyString(value.tenant_id)
    && isNonEmptyString(value.workspace_id)
    && isNonEmptyString(value.release_name)
    && isRecord(value.readiness_verdict)
    && isReadinessVerdict(value.readiness_verdict)
    && isRecord(value.freshness_summary)
    && isFreshnessSummary(value.freshness_summary)
    && isStringArray(value.source_event_ids)
    && typeof value.markdown === "string"
    && isSha256(value.markdown_hash)
    && isIsoTimestamp(value.generated_at);
}

async function sha256Hex(value: string): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new AuthorityError("The browser cannot verify authority proof-pack integrity.");
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function isAuditVerification(value: unknown): value is AuditVerification {
  return isRecord(value)
    && isNonEmptyString(value.tenant_id)
    && typeof value.valid === "boolean"
    && isNonNegativeInteger(value.event_count)
    && (value.first_invalid_sequence === undefined || value.first_invalid_sequence === null || isNonNegativeInteger(value.first_invalid_sequence));
}

function isRunCommandResponse(value: unknown): value is RunCommandResponse {
  return isRecord(value)
    && isNonEmptyString(value.run_id)
    && isGovernedRunState(value.state)
    && isGovernedRunnerStatus(value.runner_status);
}

function isRunCommandResponseForRun(value: unknown, runId: string): value is RunCommandResponse {
  return isRunCommandResponse(value) && value.run_id === runId;
}

function isKillSwitchStatus(value: unknown, tenantId: string): value is KillSwitchStatus {
  return isRecord(value)
    && value.tenant_id === tenantId
    && value.scope === "tenant"
    && typeof value.active === "boolean"
    && (value.activation_id === null || isNonEmptyString(value.activation_id))
    && (value.reason === null || typeof value.reason === "string")
    && (value.actor_id === null || isNonEmptyString(value.actor_id))
    && (value.activated_at === null || isIsoTimestamp(value.activated_at))
    && (value.deactivated_at === null || isIsoTimestamp(value.deactivated_at))
    && (value.deactivated_by === null || isNonEmptyString(value.deactivated_by))
    && (value.deactivation_reason === null || typeof value.deactivation_reason === "string")
    && value.semantics === "pre_dispatch_block_and_in_flight_interrupt";
}

function isApprovalCommandResponse(value: unknown): value is ApprovalCommandResponse {
  return isRecord(value) && isNonEmptyString(value.approval_id) && value.status === "approved";
}

function isRejectionCommandResponse(value: unknown): value is RejectionCommandResponse {
  return isRecord(value) && isNonEmptyString(value.decision_id) && value.status === "rejected";
}

function isAuthorityWorkspaceRecord(value: unknown): value is AuthorityWorkspaceRecord {
  return isRecord(value)
    && isNonEmptyString(value.workspace_id)
    && isNonEmptyString(value.tenant_id)
    && isNonNegativeInteger(value.revision)
    && value.revision > 0
    && isSavedWorkspaceDocument(value.document)
    && value.document.workspace_id === value.workspace_id
    && isSha256(value.document_hash)
    && isNonEmptyString(value.created_by)
    && isNonEmptyString(value.updated_by)
    && isNonEmptyString(value.created_at)
    && isNonEmptyString(value.updated_at);
}

function isAuthorityWorkspaceRecordForWorkspace(value: unknown, workspaceId: string): value is AuthorityWorkspaceRecord {
  return isAuthorityWorkspaceRecord(value) && value.workspace_id === workspaceId;
}

function isNullableRecord(value: unknown): value is Record<string, unknown> | null {
  return value === null || isRecord(value);
}

function isExecutionAction(value: unknown): boolean {
  if (!isRecord(value)
    || (value.tool !== "record_action" && value.tool !== "http_json_action")
    || !isRecord(value.arguments)
    || !isNonEmptyString(value.idempotency_key)
    || typeof value.external_effect !== "boolean") {
    return false;
  }
  return value.tool === "http_json_action" ? value.external_effect : !value.external_effect;
}

function isExecutionProbe(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value.probe_id)
    && (value.kind === "json_equals" || value.kind === "evidence_present" || value.kind === "http_json_equals")
    && (value.target === undefined || value.target === "action_output" || value.target === "evidence")
    && typeof value.path === "string"
    && (value.endpoint === undefined || value.endpoint === null || isNonEmptyString(value.endpoint));
}

function isGovernedExecutionPlan(value: unknown): value is GovernedExecutionPlan {
  if (!isRecord(value)
    || !Array.isArray(value.evidence)
    || value.evidence.length < 1
    || value.evidence.length > 20
    || !Array.isArray(value.validation_probes)
    || value.validation_probes.length < 1
    || value.validation_probes.length > 20
    || !Array.isArray(value.effectiveness_probes)
    || value.effectiveness_probes.length < 1
    || value.effectiveness_probes.length > 20
    || !isExecutionAction(value.action)
    || (value.rollback !== undefined && value.rollback !== null && !isExecutionAction(value.rollback))
    || (value.enterprise_context !== undefined && value.enterprise_context !== null && !isRecord(value.enterprise_context))
    || typeof value.max_attempts !== "number"
    || !Number.isInteger(value.max_attempts)
    || value.max_attempts < 1
    || value.max_attempts > 5
    || typeof value.observation_delay_seconds !== "number"
    || !Number.isInteger(value.observation_delay_seconds)
    || value.observation_delay_seconds < 0
    || value.observation_delay_seconds > 604_800) {
    return false;
  }

  const evidenceValid = value.evidence.every((item) => isRecord(item)
    && isNonEmptyString(item.evidence_id)
    && (item.kind === "workspace_snapshot" || item.kind === "http_json")
    && isNonEmptyString(item.source_ref)
    && (item.content === undefined || isNullableRecord(item.content))
    && typeof item.freshness_seconds === "number"
    && Number.isInteger(item.freshness_seconds)
    && item.freshness_seconds >= 1);
  const probesValid = [...value.validation_probes, ...value.effectiveness_probes].every(isExecutionProbe);
  const context = value.enterprise_context;
  const contextValid = context === undefined
    || context === null
    || (isRecord(context)
      && isNonEmptyString(context.policy_decision_ref)
      && isNonEmptyString(context.sandbox_profile_ref)
      && context.idempotency_scope === "tenant_workflow_tool_payload"
      && isStringArray(context.evidence_refs));
  return evidenceValid && probesValid && contextValid;
}

function isGovernedRunState(value: unknown): value is GovernedRunState {
  return value === "TRIGGERED"
    || value === "QUALIFIED"
    || value === "INPUT_INCOMPLETE"
    || value === "BLOCKED"
    || value === "OBSERVED"
    || value === "DIAGNOSED"
    || value === "INPUT_STALE"
    || value === "INPUT_CONFLICTED"
    || value === "INPUT_UNTRUSTED"
    || value === "PRIORITIZED"
    || value === "PLANNED"
    || value === "PAUSED"
    || value === "AUTHORIZED"
    || value === "ACTION_IN_PROGRESS"
    || value === "ACTION_APPLIED"
    || value === "VALIDATION_FAILED"
    || value === "ROLLED_BACK"
    || value === "VALIDATION_PASSED"
    || value === "PROOF_GREEN"
    || value === "PROOF_FAILED"
    || value === "EFFECTIVENESS_PENDING"
    || value === "EFFECTIVENESS_PROVEN"
    || value === "EFFECTIVENESS_FAILED"
    || value === "INSUFFICIENT_EVIDENCE"
    || value === "CONDITIONAL_ACTIVE"
    || value === "CONDITIONAL_EXPIRED"
    || value === "RETIRED";
}

function isGovernedRunnerStatus(value: unknown): value is GovernedRunnerStatus {
  return value === "idle"
    || value === "queued"
    || value === "running"
    || value === "awaiting_approval"
    || value === "awaiting_effectiveness"
    || value === "completed"
    || value === "failed"
    || value === "rolled_back";
}

function isGovernedRun(value: unknown): value is GovernedRun {
  return isRecord(value)
    && isNonEmptyString(value.run_id)
    && isNonEmptyString(value.tenant_id)
    && isNonEmptyString(value.workspace_id)
    && isNonEmptyString(value.loop_id)
    && isNonEmptyString(value.title)
    && isNonEmptyString(value.trigger)
    && isGovernedRunState(value.state)
    && isGovernedRunnerStatus(value.runner_status)
    && isRiskTier(value.risk_tier)
    && typeof value.requires_approval === "boolean"
    && isSha256(value.payload_hash)
    && isGovernedExecutionPlan(value.plan)
    && typeof value.attempt === "number"
    && Number.isInteger(value.attempt)
    && value.attempt >= 0
    && isNonEmptyString(value.created_by)
    && isNonEmptyString(value.created_at)
    && isNonEmptyString(value.updated_at)
    && (value.last_error === undefined || isNullableString(value.last_error))
    && (value.output === undefined || isNullableRecord(value.output))
    && (value.recovery_of === undefined || isNullableString(value.recovery_of))
    && (value.effectiveness_due_at === undefined || isNullableString(value.effectiveness_due_at));
}

function isGovernedRunForWorkspace(value: unknown, workspaceId: string): value is GovernedRun {
  return isGovernedRun(value) && value.workspace_id === workspaceId;
}

function isAuthoritySessionWithin(value: unknown, maxExpiresIn: number): value is AuthoritySession {
  if (!isRecord(value)
    || !isNonEmptyString(value.access_token)
    || value.token_type !== "bearer"
    || typeof value.expires_in !== "number"
    || !Number.isInteger(value.expires_in)
    || value.expires_in <= 0
    || value.expires_in > maxExpiresIn) {
    return false;
  }

  const actor = value.actor;
  return isRecord(actor)
    && isNonEmptyString(actor.tenant_id)
    && isNonEmptyString(actor.user_id)
    && isNonEmptyString(actor.name)
    && (actor.email === undefined || isNullableString(actor.email))
    && isAuthorityRole(actor.role);
}

function isAuthorityEvent(value: unknown, runId: string, tenantId: string): value is AuthorityEvent {
  return isRecord(value)
    && isNonNegativeInteger(value.sequence)
    && value.sequence > 0
    && value.tenant_id === tenantId
    && value.run_id === runId
    && isNonEmptyString(value.event_id)
    && isNonEmptyString(value.event_type)
    && isNullableString(value.state)
    && isNonEmptyString(value.actor_id)
    && isNonEmptyString(value.created_at)
    && isSha256(value.event_hash)
    && isSha256(value.previous_hash)
    && isRecord(value.payload);
}

function isAuthorityReadiness(value: unknown): value is AuthorityReadiness {
  if (!isRecord(value)
    || value.status !== "ready"
    || value.development_auth !== false
    || value.rate_limit_configured !== true
    || typeof value.storage_backend !== "string"
    || value.storage_backend !== "postgres"
    || typeof value.production_identity !== "boolean"
    || value.production_identity !== true
    || typeof value.credential_injection_broker_verified !== "boolean"
    || value.credential_injection_broker_verified !== true
    || typeof value.audit_anchor_configured !== "boolean"
    || value.audit_anchor_configured !== true
    || !isNonNegativeInteger(value.audit_anchor_backlog)
    || value.audit_anchor_backlog !== 0
    || typeof value.audit_anchor_delivery_verified !== "boolean"
    || value.audit_anchor_delivery_verified !== true
    || typeof value.audit_anchor_delivery_fresh !== "boolean"
    || value.audit_anchor_delivery_fresh !== true
    || !isIsoTimestamp(value.audit_anchor_last_delivered_at)
    || !isNonNegativeInteger(value.execution_job_backlog)
    || value.execution_job_backlog !== 0) {
    return false;
  }

  const worker = value.execution_worker_dispatch;
  if (!isRecord(worker)
    || worker.verified !== true
    || (worker.source !== "internal" && worker.source !== "external")
    || !isIsoTimestamp(worker.observed_at)
    || typeof worker.age_seconds !== "number"
    || !Number.isFinite(worker.age_seconds)
    || worker.age_seconds < 0
    || !isRecord(worker.detail)) {
    return false;
  }

  const bindings = value.operational_bindings;
  if (!isRecord(bindings)
    || bindings.retention_verified !== true
    || bindings.support_verified !== true
    || bindings.outbound_policy_verified !== true
    || bindings.backup_restore_verified !== true
    || bindings.worker_dispatch_verified !== true) {
    return false;
  }

  const restoreEvidence = value.backup_restore_evidence;
  const operationalEvidence = value.operational_evidence;
  const configurationContract = value.configuration_contract;
  return isRecord(restoreEvidence)
    && isCredentialFreeHttpsUrl(restoreEvidence.url)
    && isSha256(restoreEvidence.sha256)
    && isIsoTimestamp(restoreEvidence.verified_at)
    && isRecord(operationalEvidence)
    && isCredentialFreeHttpsUrl(operationalEvidence.url)
    && isSha256(operationalEvidence.sha256)
    && isIsoTimestamp(operationalEvidence.verified_at)
    && isSha256(operationalEvidence.binding_fingerprint)
    && isRecord(configurationContract)
    && isStringArray(configurationContract.allowed_http_hosts)
    && (configurationContract.outbound_policy_mode === null
      || configurationContract.outbound_policy_mode === "allowlist"
      || configurationContract.outbound_policy_mode === "deny_all")
    && isCredentialFreeHttpsUrl(configurationContract.retention_policy_url)
    && isNonEmptyString(configurationContract.support_contact)
    && isCredentialFreeHttpsUrl(configurationContract.backup_restore_evidence_url)
    && restoreEvidence.url === configurationContract.backup_restore_evidence_url;
}

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 15_000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await awaitWithAbort(fetch(`${authorityBase()}${path}`, {
      ...options,
      headers: { "x-request-id": `ui-${crypto.randomUUID()}`, ...options.headers },
      cache: "no-store",
      credentials: options.credentials ?? "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    }), controller.signal);
    let payload: unknown = {};
    try {
      payload = await awaitWithAbort(response.json(), controller.signal);
    } catch (error) {
      if (controller.signal.aborted) throw error;
    }
    if (!response.ok) {
      const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : `Authority returned ${response.status}.`;
      throw new AuthorityError(detail, response.status, response.headers.get("x-request-id") || undefined);
    }
    return payload as T;
  } catch (error) {
    if (controller.signal.aborted) throw new AuthorityError(`Authority request timed out after ${timeoutMs} ms.`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function requestAbortError(): DOMException {
  return new DOMException("The authority request was aborted.", "AbortError");
}

async function awaitWithAbort<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) throw requestAbortError();
  let onAbort: (() => void) | undefined;
  const aborted = new Promise<never>((_resolve, reject) => {
    onAbort = () => reject(requestAbortError());
    signal.addEventListener("abort", onAbort, { once: true });
  });
  try {
    return await Promise.race([operation, aborted]);
  } finally {
    if (onAbort) signal.removeEventListener("abort", onAbort);
  }
}

async function readStreamChunk(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  signal?: AbortSignal,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  if (!signal) return reader.read();
  return awaitWithAbort(reader.read(), signal);
}

function authorized(token: string, init: RequestInit = {}): RequestInit {
  return { ...init, headers: { ...init.headers, authorization: `Bearer ${token}` } };
}

async function requestAuthoritySession(path: string, options: RequestInit, maxExpiresIn = 28_800): Promise<AuthoritySession> {
  const payload = await request<unknown>(path, options);
  if (!isAuthoritySessionWithin(payload, maxExpiresIn)) {
    throw new AuthorityError("Authority returned an invalid session response.");
  }
  return payload;
}

async function requestValidated<T>(
  path: string,
  options: RequestInit,
  isValid: (value: unknown) => value is T,
  message: string,
): Promise<T> {
  const payload = await request<unknown>(path, options);
  if (!isValid(payload)) throw new AuthorityError(message);
  return payload;
}

async function requestNoContent(path: string, options: RequestInit = {}, timeoutMs = 15_000): Promise<void> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await awaitWithAbort(fetch(`${authorityBase()}${path}`, {
      ...options,
      headers: { "x-request-id": `ui-${crypto.randomUUID()}`, ...options.headers },
      cache: "no-store",
      credentials: options.credentials ?? "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    }), controller.signal);
    if (!response.ok) {
      let payload: unknown = {};
      try {
        payload = await awaitWithAbort(response.json(), controller.signal);
      } catch (error) {
        if (controller.signal.aborted) throw error;
      }
      const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : `Authority returned ${response.status}.`;
      throw new AuthorityError(detail, response.status, response.headers.get("x-request-id") || undefined);
    }
    if (response.status !== 204) {
      throw new AuthorityError("Authority returned an invalid delete response.", response.status);
    }
  } catch (error) {
    if (controller.signal.aborted) throw new AuthorityError(`Authority request timed out after ${timeoutMs} ms.`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function createDevelopmentSession(user: EnterpriseUser): Promise<AuthoritySession> {
  return requestAuthoritySession("/v1/dev/sessions", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ tenant_id: "local-evaluation", user_id: user.user_id, name: user.name, role: user.role, ttl_seconds: 3600 }),
  });
}

export async function createEnterpriseSession(): Promise<AuthoritySession> {
  return requestAuthoritySession("/v1/sessions", {
    method: "POST",
    credentials: "include",
  }, 900);
}

export async function createAuthoritySession(
  user: EnterpriseUser,
  mode: DeploymentMode = deploymentPosture.mode,
): Promise<AuthoritySession> {
  return mode === "enterprise" ? createEnterpriseSession() : createDevelopmentSession(user);
}

export async function getKillSwitchStatus(token: string, tenantId: string): Promise<KillSwitchStatus> {
  return requestValidated<KillSwitchStatus>(
    "/v1/controls/kill-switch",
    authorized(token),
    (value): value is KillSwitchStatus => isKillSwitchStatus(value, tenantId),
    "Authority returned invalid kill-switch status.",
  );
}

export async function activateKillSwitch(token: string, reason: string, tenantId: string): Promise<KillSwitchStatus> {
  return requestValidated<KillSwitchStatus>(
    "/v1/controls/kill-switch",
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
    (value): value is KillSwitchStatus => isKillSwitchStatus(value, tenantId) && value.active,
    "Authority returned invalid kill-switch activation status.",
  );
}

export async function deactivateKillSwitch(token: string, reason: string, tenantId: string): Promise<KillSwitchStatus> {
  return requestValidated<KillSwitchStatus>(
    "/v1/controls/kill-switch/deactivate",
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
    (value): value is KillSwitchStatus => isKillSwitchStatus(value, tenantId) && !value.active,
    "Authority returned invalid kill-switch deactivation status.",
  );
}

export async function getAuthorityReadiness(): Promise<AuthorityReadiness> {
  const payload = await request<unknown>("/health/ready");
  if (!isAuthorityReadiness(payload)) {
    throw new AuthorityError("Authority returned an invalid readiness response.");
  }
  return payload;
}

export async function listAuthorityWorkspaces(token: string): Promise<AuthorityWorkspaceRecord[]> {
  return requestValidated<AuthorityWorkspaceRecord[]>(
    "/v1/workspaces",
    authorized(token),
    (value): value is AuthorityWorkspaceRecord[] => Array.isArray(value) && value.every(isAuthorityWorkspaceRecord),
    "Authority returned invalid workspace data.",
  );
}

export async function createAuthorityWorkspace(token: string, workspace: SavedWorkspace): Promise<AuthorityWorkspaceRecord> {
  return requestValidated<AuthorityWorkspaceRecord>(
    `/v1/workspaces/${encodeURIComponent(workspace.workspace_id)}`,
    authorized(token, {
      method: "PUT",
      headers: { "content-type": "application/json", "if-none-match": "*" },
      body: JSON.stringify({ document: workspace }),
    }),
    (value): value is AuthorityWorkspaceRecord => isAuthorityWorkspaceRecordForWorkspace(value, workspace.workspace_id),
    "Authority returned invalid workspace data.",
  );
}

export async function updateAuthorityWorkspace(token: string, workspace: SavedWorkspace, revision: number): Promise<AuthorityWorkspaceRecord> {
  return requestValidated<AuthorityWorkspaceRecord>(
    `/v1/workspaces/${encodeURIComponent(workspace.workspace_id)}`,
    authorized(token, {
      method: "PUT",
      headers: { "content-type": "application/json", "if-match": `"${revision}"` },
      body: JSON.stringify({ document: workspace }),
    }),
    (value): value is AuthorityWorkspaceRecord => isAuthorityWorkspaceRecordForWorkspace(value, workspace.workspace_id),
    "Authority returned invalid workspace data.",
  );
}

export async function deleteAuthorityWorkspace(token: string, workspaceId: string, revision: number): Promise<void> {
  await requestNoContent(`/v1/workspaces/${encodeURIComponent(workspaceId)}`, authorized(token, {
    method: "DELETE",
    headers: { "if-match": `"${revision}"` },
  }));
}

export async function listGovernedRuns(token: string, workspaceId: string, tenantId: string): Promise<GovernedRun[]> {
  return requestValidated<GovernedRun[]>(
    `/v1/runs?workspace_id=${encodeURIComponent(workspaceId)}`,
    authorized(token),
    (value): value is GovernedRun[] => Array.isArray(value) && value.every((run) => isGovernedRunForWorkspace(run, workspaceId) && run.tenant_id === tenantId),
    "Authority returned invalid governed run data.",
  );
}

export async function listReleaseInitiatives(token: string, workspaceId: string, tenantId: string): Promise<ReleaseInitiativeRecord[]> {
  return requestValidated<ReleaseInitiativeRecord[]>(
    `/v1/release-initiatives?workspace_id=${encodeURIComponent(workspaceId)}`,
    authorized(token),
    (value): value is ReleaseInitiativeRecord[] => Array.isArray(value)
      && value.every((initiative) => isReleaseInitiativeRecord(initiative) && initiative.workspace_id === workspaceId && initiative.tenant_id === tenantId),
    "Authority returned invalid release initiative data.",
  );
}

export async function listConnectorEvents(token: string, workspaceId: string, tenantId: string): Promise<ConnectorEventRecord[]> {
  return requestValidated<ConnectorEventRecord[]>(
    `/v1/connector-events?workspace_id=${encodeURIComponent(workspaceId)}`,
    authorized(token),
    (value): value is ConnectorEventRecord[] => Array.isArray(value)
      && value.every((event) => isConnectorEventRecord(event) && event.workspace_id === workspaceId && event.tenant_id === tenantId),
    "Authority returned invalid connector event data.",
  );
}

export async function getGovernedRun(token: string, runId: string, tenantId: string): Promise<GovernedRun> {
  return requestValidated<GovernedRun>(
    `/v1/runs/${encodeURIComponent(runId)}`,
    authorized(token),
    (value): value is GovernedRun => isGovernedRun(value) && value.tenant_id === tenantId,
    "Authority returned invalid governed run data.",
  );
}

export async function createGovernedRun(token: string, input: CreateGovernedRun, tenantId: string): Promise<GovernedRun> {
  return requestValidated<GovernedRun>(
    "/v1/runs",
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": `create-${crypto.randomUUID()}` },
      body: JSON.stringify(input),
    }),
    (value): value is GovernedRun => isGovernedRunForWorkspace(value, input.workspace_id) && value.tenant_id === tenantId,
    "Authority returned invalid governed run data.",
  );
}

export async function createReleaseInitiative(token: string, input: CreateReleaseInitiative, tenantId: string): Promise<ReleaseInitiativeRecord> {
  return requestValidated<ReleaseInitiativeRecord>(
    "/v1/release-initiatives",
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": `release-${input.workspace_id}-${input.release_name}`.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 180) },
      body: JSON.stringify(input),
    }),
    (value): value is ReleaseInitiativeRecord => isReleaseInitiativeRecord(value) && value.workspace_id === input.workspace_id && value.tenant_id === tenantId,
    "Authority returned invalid release initiative data.",
  );
}

export async function recordReleaseInitiative(token: string, input: CreateReleaseInitiative, connectorEvents: ConnectorEventInput[], tenantId: string): Promise<RecordReleaseInitiativeResponse> {
  const response = await requestValidated<RecordReleaseInitiativeResponse>(
    "/v1/release-initiatives/record",
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json", "idempotency-key": `release-${input.workspace_id}-${input.release_name}`.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 180) },
      body: JSON.stringify({ initiative: input, connector_events: connectorEvents }),
    }),
    (value): value is RecordReleaseInitiativeResponse => isRecordReleaseInitiativeResponse(value)
      && value.initiative.workspace_id === input.workspace_id
      && value.initiative.tenant_id === tenantId
      && value.connector_events.every((event) => event.workspace_id === input.workspace_id && event.tenant_id === tenantId),
    "Authority returned invalid atomic release initiative data.",
  );
  if (response.initiative.source_event_ids.length !== response.connector_events.length) {
    throw new AuthorityError("Authority returned an incomplete atomic release evidence binding.");
  }
  return response;
}

export async function getReleaseProofPack(token: string, initiativeId: string, tenantId: string): Promise<ReleaseProofPack> {
  const proofPack = await requestValidated<ReleaseProofPack>(
    `/v1/release-initiatives/${encodeURIComponent(initiativeId)}/proof-pack`,
    authorized(token),
    (value): value is ReleaseProofPack => isReleaseProofPack(value) && value.initiative_id === initiativeId && value.tenant_id === tenantId,
    "Authority returned invalid release proof pack data.",
  );
  if ((await sha256Hex(proofPack.markdown)) !== proofPack.markdown_hash) {
    throw new AuthorityError("Authority returned a release proof pack with an invalid content hash.");
  }
  return proofPack;
}

export async function recordConnectorEvent(token: string, input: ConnectorEventInput, tenantId: string): Promise<ConnectorEventRecord> {
  return requestValidated<ConnectorEventRecord>(
    "/v1/connector-events",
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
    (value): value is ConnectorEventRecord => isConnectorEventRecord(value) && value.workspace_id === input.workspace_id && value.tenant_id === tenantId,
    "Authority returned invalid connector event data.",
  );
}

export async function startGovernedRun(token: string, runId: string): Promise<RunCommandResponse> {
  return requestValidated<RunCommandResponse>(
    `/v1/runs/${encodeURIComponent(runId)}/start`,
    authorized(token, { method: "POST" }),
    (value): value is RunCommandResponse => isRunCommandResponseForRun(value, runId),
    "Authority returned invalid start response.",
  );
}

export async function approveGovernedRun(token: string, run: GovernedRun, reason: string): Promise<ApprovalCommandResponse> {
  return requestValidated<ApprovalCommandResponse>(
    `/v1/runs/${encodeURIComponent(run.run_id)}/approve`,
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ payload_hash: run.payload_hash, decision_reason: reason }),
    }),
    isApprovalCommandResponse,
    "Authority returned invalid approval response.",
  );
}

export async function rejectGovernedRun(token: string, run: GovernedRun, reason: string): Promise<RejectionCommandResponse> {
  return requestValidated<RejectionCommandResponse>(
    `/v1/runs/${encodeURIComponent(run.run_id)}/reject`,
    authorized(token, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ payload_hash: run.payload_hash, decision_reason: reason }),
    }),
    isRejectionCommandResponse,
    "Authority returned invalid rejection response.",
  );
}

export async function verifyAuthorityAudit(token: string): Promise<AuditVerification> {
  return requestValidated<AuditVerification>(
    "/v1/audit/verify",
    authorized(token),
    isAuditVerification,
    "Authority returned invalid audit verification data.",
  );
}

export async function recoverGovernedRun(token: string, runId: string): Promise<GovernedRun> {
  return requestValidated<GovernedRun>(
    `/v1/runs/${encodeURIComponent(runId)}/recover`,
    authorized(token, {
      method: "POST",
      headers: { "idempotency-key": `recover-${crypto.randomUUID()}` },
    }),
    isGovernedRun,
    "Authority returned invalid governed run data.",
  );
}

export async function rollbackGovernedRun(token: string, runId: string): Promise<RunCommandResponse> {
  return requestValidated<RunCommandResponse>(
    `/v1/runs/${encodeURIComponent(runId)}/rollback`,
    authorized(token, { method: "POST" }),
    (value): value is RunCommandResponse => isRunCommandResponseForRun(value, runId),
    "Authority returned invalid rollback response.",
  );
}

export async function streamGovernedRun(
  token: string,
  runId: string,
  tenantId: string,
  onEvent: (event: AuthorityEvent) => void,
  signal?: AbortSignal,
  after = 0,
  stopAtApproval = true,
): Promise<void> {
  const response = await fetch(`${authorityBase()}/v1/runs/${encodeURIComponent(runId)}/events?after=${after}`, {
    headers: { accept: "text/event-stream", authorization: `Bearer ${token}` },
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    referrerPolicy: "no-referrer",
    signal,
  });
  if (!response.ok || !response.body) throw new AuthorityError(`Event stream returned ${response.status}.`, response.status);
  const contentType = response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase();
  if (contentType !== "text/event-stream") {
    throw new AuthorityError("Authority returned a non-SSE event stream.", response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const processFrames = (flush = false): boolean => {
    const frames = buffer.replace(/\r\n?/g, "\n").split("\n\n");
    buffer = flush ? "" : (frames.pop() ?? "");
    for (const frame of frames) {
      const data = frame.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
      if (!data) continue;
      let payload: unknown;
      try {
        payload = JSON.parse(data);
      } catch {
        throw new AuthorityError("Authority returned malformed audit event.");
      }
      if (!isAuthorityEvent(payload, runId, tenantId)) {
        throw new AuthorityError("Authority returned an invalid audit event.");
      }
      const event = payload;
      onEvent(event);
      if (event.event_type === "RUN_RELEASED"
        && ["awaiting_effectiveness", "completed", "failed", "rolled_back"].includes(String(event.payload.runner_status))) {
        return true;
      }
      if (stopAtApproval && event.event_type === "RUN_RELEASED" && event.payload.runner_status === "awaiting_approval") return true;
    }
    return false;
  };
  try {
    while (true) {
      const { value, done } = await readStreamChunk(reader, signal);
      if (done) {
        buffer += decoder.decode();
        if (buffer && processFrames(true)) await reader.cancel();
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      if (processFrames()) {
        await reader.cancel();
        return;
      }
    }
  } catch (error) {
    if (signal?.aborted) void reader.cancel().catch(() => undefined);
    throw error;
  } finally {
    reader.releaseLock();
  }
}
