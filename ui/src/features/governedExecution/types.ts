import type { EnterpriseUser, InitiativeWorkspace, ReleaseAssuranceProfile, RiskTier, SavedWorkspace } from "../../types";

export interface AuthoritySession {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  actor: {
    tenant_id: string;
    user_id: string;
    name: string;
    email?: string | null;
    role: EnterpriseUser["role"];
  };
}

export interface GovernedExecutionPlan {
  evidence: Array<{
    evidence_id: string;
    kind: "workspace_snapshot" | "http_json";
    source_ref: string;
    content?: Record<string, unknown>;
    freshness_seconds: number;
  }>;
  action: {
    tool: "record_action" | "http_json_action";
    arguments: Record<string, unknown>;
    idempotency_key: string;
    external_effect: boolean;
  };
  validation_probes: Array<{
    probe_id: string;
    kind: "json_equals" | "evidence_present" | "http_json_equals";
    target?: "action_output" | "evidence";
    path: string;
    expected: unknown;
    endpoint?: string;
  }>;
  effectiveness_probes: Array<{
    probe_id: string;
    kind: "json_equals" | "evidence_present" | "http_json_equals";
    target?: "action_output" | "evidence";
    path: string;
    expected: unknown;
    endpoint?: string;
  }>;
  rollback?: GovernedExecutionPlan["action"];
  enterprise_context?: {
    policy_decision_ref: string;
    sandbox_profile_ref: string;
    idempotency_scope: "tenant_workflow_tool_payload";
    evidence_refs: string[];
  } | null;
  max_attempts: number;
  observation_delay_seconds: number;
}

export interface CreateGovernedRun {
  workspace_id: string;
  loop_id: string;
  title: string;
  trigger: string;
  requested_risk_tier: RiskTier;
  plan: GovernedExecutionPlan;
}

export type GovernedRunState =
  | "TRIGGERED"
  | "QUALIFIED"
  | "INPUT_INCOMPLETE"
  | "BLOCKED"
  | "OBSERVED"
  | "DIAGNOSED"
  | "INPUT_STALE"
  | "INPUT_CONFLICTED"
  | "INPUT_UNTRUSTED"
  | "PRIORITIZED"
  | "PLANNED"
  | "PAUSED"
  | "AUTHORIZED"
  | "ACTION_IN_PROGRESS"
  | "ACTION_APPLIED"
  | "VALIDATION_FAILED"
  | "ROLLED_BACK"
  | "VALIDATION_PASSED"
  | "PROOF_GREEN"
  | "PROOF_FAILED"
  | "EFFECTIVENESS_PENDING"
  | "EFFECTIVENESS_PROVEN"
  | "EFFECTIVENESS_FAILED"
  | "INSUFFICIENT_EVIDENCE"
  | "CONDITIONAL_ACTIVE"
  | "CONDITIONAL_EXPIRED"
  | "RETIRED";

export type GovernedRunnerStatus =
  | "idle"
  | "queued"
  | "running"
  | "awaiting_approval"
  | "awaiting_effectiveness"
  | "completed"
  | "failed"
  | "rolled_back";

export interface GovernedRun {
  run_id: string;
  tenant_id: string;
  workspace_id: string;
  loop_id: string;
  title: string;
  trigger: string;
  state: GovernedRunState;
  runner_status: GovernedRunnerStatus;
  risk_tier: RiskTier;
  requires_approval: boolean;
  payload_hash: string;
  plan: GovernedExecutionPlan;
  attempt: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
  output?: Record<string, unknown> | null;
  recovery_of?: string | null;
  effectiveness_due_at?: string | null;
}

export interface AuditVerification {
  tenant_id: string;
  valid: boolean;
  event_count: number;
  first_invalid_sequence?: number | null;
}

export interface RunCommandResponse {
  run_id: string;
  state: GovernedRunState;
  runner_status: GovernedRunnerStatus;
}

export interface ApprovalCommandResponse {
  approval_id: string;
  status: "approved";
}

export interface RejectionCommandResponse {
  decision_id: string;
  status: "rejected";
}

export interface KillSwitchStatus {
  tenant_id: string;
  scope: "tenant";
  active: boolean;
  activation_id: string | null;
  reason: string | null;
  actor_id: string | null;
  activated_at: string | null;
  deactivated_at: string | null;
  deactivated_by: string | null;
  deactivation_reason: string | null;
  semantics: "pre_dispatch_block_and_in_flight_interrupt";
}

export interface CreateReleaseInitiative {
  workspace_id: string;
  title: string;
  description: string;
  workflow_type: InitiativeWorkspace["workflow_type"];
  business_outcome: string;
  maturity: string;
  risk_tier: RiskTier;
  status: InitiativeWorkspace["status"];
  release_name: string;
  loop_bundle_ids: string[];
  source_event_ids: string[];
  release_assurance: ReleaseAssuranceProfile;
}

export interface ReleaseInitiativeRecord extends CreateReleaseInitiative {
  initiative_id: string;
  tenant_id: string;
  freshness_summary?: {
    status?: "fresh" | "stale" | "missing";
    policy?: string;
    max_age_seconds?: number;
    evaluated_at?: string;
    source_event_count?: number;
    verified_webhook_count?: number;
    session_authenticated_count?: number;
    stale_event_ids?: string[];
    invalid_observed_at_event_ids?: string[];
    oldest_observed_at?: string | null;
    newest_observed_at?: string | null;
  };
  readiness_verdict?: {
    verdict?: "GO" | "NO_GO" | "REVIEW_REQUIRED";
    evaluated_at?: string;
    policy?: string;
    gate_status_counts?: Record<string, number>;
    failing_reasons?: string[];
    review_reasons?: string[];
  };
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ReleaseProofPack {
  initiative_id: string;
  tenant_id: string;
  workspace_id: string;
  release_name: string;
  readiness_verdict: NonNullable<ReleaseInitiativeRecord["readiness_verdict"]>;
  freshness_summary: NonNullable<ReleaseInitiativeRecord["freshness_summary"]>;
  source_event_ids: string[];
  markdown: string;
  markdown_hash: string;
  generated_at: string;
}

export interface ConnectorEventInput {
  workspace_id: string;
  system: "jira" | "github" | "manual";
  event_kind: "issue" | "pull_request" | "commit" | "check" | "workflow" | "release" | "deployment" | "manual_note";
  external_id: string;
  label: string;
  url?: string;
  observed_at: string;
  payload: Record<string, unknown>;
  verification_status?: "session_authenticated" | "verified_webhook";
  delivery_id?: string | null;
}

export interface ConnectorEventRecord extends ConnectorEventInput {
  connector_event_id: string;
  tenant_id: string;
  payload_hash: string;
  verification_status: "session_authenticated" | "verified_webhook";
  created_by: string;
  created_at: string;
}

export interface RecordReleaseInitiativeResponse {
  initiative: ReleaseInitiativeRecord;
  connector_events: ConnectorEventRecord[];
}

export interface AuthorityEvent {
  sequence: number;
  event_id: string;
  tenant_id: string;
  run_id: string;
  event_type: string;
  state: string | null;
  actor_id: string;
  created_at: string;
  event_hash: string;
  previous_hash: string;
  payload: Record<string, unknown>;
}

export interface ExecutionTargetOptions {
  mode: "record" | "http";
  endpoint?: string;
  method?: "POST" | "PUT" | "PATCH" | "DELETE";
  body?: Record<string, unknown>;
  rollbackEndpoint?: string;
  rollbackBody?: Record<string, unknown>;
  verificationEndpoint?: string;
  verificationPath?: string;
  verificationExpected?: unknown;
  observationDelaySeconds?: number;
}

export function buildWorkspaceExecutionPlan(
  workspace: SavedWorkspace,
  loopId: string,
  loopName: string,
  riskTier: RiskTier,
  target: ExecutionTargetOptions = { mode: "record" },
): CreateGovernedRun {
  const operationId = crypto.randomUUID();
  const requiresEnterpriseContext = target.mode === "http" || riskTier === "R3" || riskTier === "R4";
  const action = target.mode === "http" ? {
    tool: "http_json_action" as const,
    arguments: { endpoint: target.endpoint, method: target.method ?? "POST", body: target.body ?? {} },
    idempotency_key: `action-${operationId}`,
    external_effect: true,
  } : {
    tool: "record_action" as const,
    arguments: {
      operation: "apply",
      summary: `Apply the governed ${loopName} operation for ${workspace.use_case.title}.`,
      outputs: ["durable action artifact", "validation evidence", "effectiveness proof"],
    },
    idempotency_key: `action-${operationId}`,
    external_effect: false,
  };
  const validationProbe = target.mode === "http" ? {
    probe_id: "enterprise-state-validation",
    kind: "http_json_equals" as const,
    path: target.verificationPath ?? "status",
    expected: target.verificationExpected,
    endpoint: target.verificationEndpoint,
  } : { probe_id: "action-applied", kind: "json_equals" as const, path: "status", expected: "applied" };
  const effectivenessProbe = target.mode === "http" ? {
    ...validationProbe,
    probe_id: "enterprise-effectiveness-observed",
  } : { probe_id: "effectiveness-observed", kind: "json_equals" as const, path: "status", expected: "applied" };
  return {
    workspace_id: workspace.workspace_id,
    loop_id: loopId,
    title: `${loopName} governed run`,
    trigger: workspace.use_case.description || workspace.use_case.title,
    requested_risk_tier: riskTier,
    plan: {
      evidence: [{
        evidence_id: "workspace-snapshot",
        kind: "workspace_snapshot",
        source_ref: `workspace:${workspace.workspace_id}`,
        content: {
          use_case: workspace.use_case,
          selected_loop_ids: workspace.selected_loop_ids,
          owner_evidence_edits: workspace.owner_evidence_edits.filter((edit) => edit.loop_id === loopId),
          accepted_source_refs: workspace.input_sources.map((source) => ({ source_id: source.source_id, label: source.label, character_count: source.character_count })),
        },
        freshness_seconds: 3600,
      }],
      action,
      validation_probes: [validationProbe],
      effectiveness_probes: [effectivenessProbe],
      rollback: target.mode === "http" ? {
        tool: "http_json_action",
        arguments: { endpoint: target.rollbackEndpoint, method: "POST", body: target.rollbackBody ?? {} },
        idempotency_key: `rollback-${operationId}`,
        external_effect: true,
      } : undefined,
      enterprise_context: requiresEnterpriseContext ? {
        policy_decision_ref: `policy-${operationId}`,
        sandbox_profile_ref: riskTier === "R3" || riskTier === "R4" ? "sandbox-e2b-firecracker-production" : "sandbox-governed-standard",
        idempotency_scope: "tenant_workflow_tool_payload",
        evidence_refs: ["workspace-snapshot"],
      } : null,
      max_attempts: 3,
      observation_delay_seconds: target.observationDelaySeconds ?? 0,
    },
  };
}

export function buildReleaseInitiativeRecord(workspace: SavedWorkspace, initiative: InitiativeWorkspace, sourceEventIds: string[] = []): CreateReleaseInitiative {
  if (!initiative.release_assurance) throw new Error("The selected initiative has no release assurance profile.");
  return {
    workspace_id: workspace.workspace_id,
    title: initiative.title,
    description: initiative.description,
    workflow_type: initiative.workflow_type,
    business_outcome: initiative.business_outcome,
    maturity: initiative.maturity,
    risk_tier: initiative.risk,
    status: initiative.status,
    release_name: initiative.release_assurance.release_name,
    loop_bundle_ids: initiative.loop_bundle_ids,
    source_event_ids: sourceEventIds,
    release_assurance: initiative.release_assurance,
  };
}

export function buildConnectorEventsForRelease(workspace: SavedWorkspace, initiative: InitiativeWorkspace): ConnectorEventInput[] {
  if (!initiative.release_assurance) return [];
  return initiative.release_assurance.external_refs.map((ref) => ({
    workspace_id: workspace.workspace_id,
    system: ref.system,
    event_kind: ref.object_type,
    external_id: ref.ref_id,
    label: ref.label,
    url: ref.url,
    observed_at: ref.observed_at,
    verification_status: "session_authenticated",
    payload: {
      release_name: initiative.release_assurance?.release_name,
      evidence_hash: ref.evidence_hash,
      initiative_id: initiative.id,
      source_ref: ref.ref_id,
      trust_boundary: "shadow evidence only; governed write-back requires separate authority action",
    },
  }));
}
