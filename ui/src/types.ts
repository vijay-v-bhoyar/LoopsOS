export type RiskTier = "R0" | "R1" | "R2" | "R3" | "R4";

export interface CategorySummary {
  number: number;
  name: string;
  slug: string;
  loop_count: number;
  risk_tiers: Record<string, number>;
}

export interface Control {
  control_id: string;
  control_name: string;
  section_key: string;
  section_name: string;
  minimum_risk_tier: RiskTier;
  applies_when: string;
  minimum_proof: string;
  proof_required: string;
}

export interface ControlProfile {
  profile_id: string;
  loop_id: string;
  baseline_risk_tier: RiskTier;
  applicable_control_ids: string[];
}

export interface OperationCard {
  operation_card_id: string;
  loop_id: string;
  name: string;
  primary_user: string;
  automation_mode: string;
  when_to_run: {
    trigger: string;
    minimum_cadence: string;
    do_not_run_if: string[];
  };
  first_10_minutes: string[];
  evidence_to_collect: string[];
  proof_to_run: string[];
  success_criteria: string[];
  handoff_rules: string[];
  minimum_viable_record: string[];
  common_failure_modes: string[];
}

export interface MetricPack {
  loop_id: string;
  metric_pack_ref: string;
  primary_metric: {
    name: string;
    formula: string;
    target_value: string;
    observation_window: string;
  };
  guardrails: string[];
  health_metrics: string[];
}

export interface GoldenTaskGroup {
  loop_id: string;
  golden_task_ref: string;
  tasks: Array<{
    task_id: string;
    type: string;
    scenario: string;
    expected: string;
  }>;
}

export interface LoopEdge {
  from: string;
  to: string;
  event: string;
  evidence: string;
  priority: string;
}

export interface LoopDetail {
  loop_id: string;
  number: number;
  name: string;
  slug: string;
  category_number: number;
  category_name: string;
  category_slug: string;
  trigger: string;
  run: string;
  output: string;
  cadence: string;
  baseline_risk_tier: RiskTier;
  markdown_path: string;
  descriptor_path: string;
  descriptor: Record<string, unknown>;
  operation_card: OperationCard;
  control_profile: ControlProfile;
  control_preview: Control[];
  metric_pack: MetricPack;
  golden_tasks: GoldenTaskGroup;
  incoming_edges: LoopEdge[];
  outgoing_edges: LoopEdge[];
}

export type LoopSummary = Pick<
  LoopDetail,
  | "loop_id"
  | "number"
  | "name"
  | "category_name"
  | "trigger"
  | "output"
  | "cadence"
  | "baseline_risk_tier"
>;

export interface PilotPlaybook {
  playbook_id: string;
  title: string;
  impact_rank: number;
  effort_saving: string;
  loops: string[];
  pilot_scope: string;
  setup: string[];
  operating_steps: string[];
  proof_bundle: string[];
  exit_criteria: string[];
}

export interface UseCaseRecord {
  use_case_id: string;
  family: "primary" | "moat";
  rank: number;
  title: string;
  summary: string;
  loop_names: string[];
  source: string;
}

export interface UseCaseInput {
  title: string;
  description: string;
  environment: string;
  aiScope: string;
  dataSensitivity: string;
  businessOutcome: string;
  maturity: string;
  constraints: string;
}

export type InputSourceKind = "text" | "document" | "voice";
export type InputSourceStatus = "processing" | "ready_for_review" | "accepted" | "error";

export interface ExtractionWarning {
  code: "truncated" | "encrypted" | "image_only" | "parser_warning" | "unsupported";
  message: string;
}

export interface UseCaseSource {
  source_id: string;
  kind: InputSourceKind;
  label: string;
  mime_type: string;
  status: InputSourceStatus;
  accepted_text: string;
  extraction_method: string;
  character_count: number;
  created_at: string;
  warnings: ExtractionWarning[];
  truncated: boolean;
}

export interface UseCaseFieldProposal {
  field: keyof UseCaseInput;
  value: string;
  evidence_excerpt: string;
  source_ids: string[];
  method: "deterministic" | "enterprise LLM";
}

export interface UseCaseDraft {
  draft_id: string;
  source_ids: string[];
  fields: UseCaseFieldProposal[];
  method: "deterministic" | "enterprise LLM";
  created_at: string;
}

export type VoiceCaptureState = "idle" | "requesting_permission" | "listening" | "stopped" | "transcribing" | "review" | "unavailable" | "error";

export interface RecommendationContext {
  sources?: UseCaseSource[];
}

export interface MatchFactor {
  label: string;
  detail: string;
  weight: number;
  source: string;
  source_ref?: string;
  evidence_excerpt?: string;
}

export interface LoopRecommendation {
  loop_id: string;
  name: string;
  category_name: string;
  risk_tier: RiskTier;
  role: "primary" | "supporting" | "governance" | "validation" | "next-step";
  score: number;
  factors: MatchFactor[];
  evidence_refs: string[];
}

export interface UseCaseValidationResult {
  readiness: "Discovery Ready" | "Pilot Candidate" | "Governance Review" | "Blocked";
  corpusStatus: "PASS" | "FAIL" | "UNKNOWN";
  findings: Array<{
    status: "pass" | "gap" | "review";
    label: string;
    detail: string;
  }>;
  gaps: string[];
  nextActions: string[];
}

export interface EnterpriseActionPlan {
  title: string;
  summary: string;
  recommendations: LoopRecommendation[];
  validation: UseCaseValidationResult;
  first30Days: string[];
  exportMarkdown: string;
}

export type UserRole = "Executive" | "Approver" | "Operator" | "Auditor";

export interface EnterpriseUser {
  user_id: string;
  name: string;
  email: string;
  role: UserRole;
  signed_in_at: string;
}

export interface OwnerEvidenceEdit {
  edit_id: string;
  loop_id: string;
  owner_ref: string;
  policy_owner: string;
  gate_owner: string;
  risk_owner: string;
  evidence_ref: string;
  authoritative_location: string;
  freshness_policy: string;
  retention_policy: string;
  edited_by: string;
  edited_at: string;
}

export interface ApprovalRecord {
  approval_id: string;
  loop_id: string;
  request_title: string;
  requested_by: string;
  requested_at: string;
  approver: string;
  status: "Pending" | "Approved" | "Rejected";
  risk_tier: RiskTier;
  evidence_summary: string;
  decision_reason: string;
  decided_at?: string;
}

export interface ExecutionRecord {
  execution_id: string;
  loop_id: string;
  title: string;
  correlation_id: string;
  state: string;
  risk_tier: RiskTier;
  evidence_refs: string;
  validation_result: "Not Run" | "Passed" | "Failed" | "Inconclusive";
  proof_state: "Not Started" | "Proof Green" | "Proof Failed" | "Effectiveness Pending" | "Effectiveness Proven";
  owner: string;
  created_at: string;
  updated_at: string;
}

export type InitiativeWorkflowType = "new_feature" | "release" | "defect" | "incident" | "architecture_change" | "compliance_ask" | "ai_use_case" | "vendor_change";
export type InitiativeStatus = "intake" | "discovery" | "planned" | "executing" | "validating" | "blocked" | "approved" | "standardized" | "retired";
export type LoopRunStatus = "not_started" | "running" | "blocked" | "validated" | "standardized";
export type LoopRunStepStatus = "open" | "done" | "blocked";
export type HandoffStatus = "open" | "assigned" | "closed" | "blocked";

export interface LoopRunStep {
  step_key: string;
  label: string;
  status: LoopRunStepStatus;
  required_evidence: string;
  required_owner: string;
  required_controls: string[];
  output: string;
  notes: string;
  completed_at?: string;
}

export interface LoopRun {
  run_id: string;
  loop_id: string;
  initiative_id: string;
  status: LoopRunStatus;
  current_step: string;
  step_records: LoopRunStep[];
  owner: string;
  evidence_refs: string[];
  validation_result: "Not Run" | "Passed" | "Failed" | "Inconclusive";
  created_at: string;
  updated_at: string;
}

export interface HandoffAction {
  handoff_id: string;
  from_loop_id: string;
  to_loop_id: string;
  reason: string;
  owner: string;
  status: HandoffStatus;
  due_date: string;
  evidence_ref: string;
}

export interface EffortSavingEstimate {
  initiative_id: string;
  meetings_avoided: number;
  review_cycles_reduced: number;
  evidence_items_reused: number;
  hours_saved_estimate: number;
  assumptions: string;
  confidence_basis: string;
}

export type ExternalSystem = "jira" | "github" | "manual";
export type ReleaseGateStatus = "passed" | "gap" | "review_required" | "exception_active" | "blocked";
export type ConnectorMode = "not_configured" | "export_ready" | "shadow_read" | "gated_write";

export interface ExternalObjectRef {
  ref_id: string;
  system: ExternalSystem;
  object_type: "issue" | "pull_request" | "commit" | "check" | "workflow" | "release" | "deployment" | "manual_note";
  label: string;
  url?: string;
  observed_at: string;
  evidence_hash: string;
}

export interface EvidenceArtifact {
  artifact_id: string;
  gate_id: string;
  loop_id: string;
  source_ref: string;
  label: string;
  freshness: "fresh" | "stale" | "missing";
  required: boolean;
  observed_at?: string;
}

export interface GateDecision {
  decision_id: string;
  gate_id: string;
  status: ReleaseGateStatus;
  decided_by: string;
  decided_at: string;
  basis: string;
  source_ref_ids: string[];
}

export interface RiskException {
  exception_id: string;
  gate_id: string;
  reason: string;
  approver: string;
  expires_at: string;
  compensating_controls: string[];
  status: "active" | "expired" | "closed";
}

export interface ReleaseGate {
  gate_id: string;
  label: string;
  loop_id: string;
  control_ids: string[];
  required_evidence: string[];
  status: ReleaseGateStatus;
  blocker: string;
  last_decision?: GateDecision;
}

export interface ConnectorInstallation {
  connector_id: string;
  system: ExternalSystem;
  mode: ConnectorMode;
  label: string;
  required_for: string[];
  write_scope: "none" | "comment" | "status_check" | "issue_update";
  trust_boundary: string;
}

export interface MetricObservation {
  metric_id: string;
  label: string;
  value: number;
  unit: "hours" | "count" | "percent";
  basis: string;
  source_ref_ids: string[];
}

export interface ReleaseAssuranceProfile {
  profile_id: string;
  initiative_id: string;
  release_name: string;
  operating_mode: "local_draft" | "shadow_release" | "gated_release";
  connectors: ConnectorInstallation[];
  external_refs: ExternalObjectRef[];
  gates: ReleaseGate[];
  evidence_artifacts: EvidenceArtifact[];
  decisions: GateDecision[];
  exceptions: RiskException[];
  metric_observations: MetricObservation[];
  proof_pack_scope: string[];
}

export interface EvidenceRecord {
  evidence_id: string;
  loop_id: string;
  label: string;
  source: string;
  freshness: "fresh" | "stale" | "missing";
  created_at: string;
}

export interface InitiativeWorkspace {
  id: string;
  title: string;
  description: string;
  workflow_type: InitiativeWorkflowType;
  business_outcome: string;
  maturity: string;
  risk: RiskTier;
  status: InitiativeStatus;
  created_at: string;
  updated_at: string;
  loop_bundle_ids: string[];
  execution_records: LoopRun[];
  evidence_records: EvidenceRecord[];
  approvals: ApprovalRecord[];
  handoffs: HandoffAction[];
  roi_assumptions: EffortSavingEstimate;
  release_assurance?: ReleaseAssuranceProfile;
}

export interface QuestionSuggestion {
  question_id: string;
  question: string;
  why_it_matters: string;
  target_field: keyof UseCaseInput | "ownerEvidence" | "approval" | "execution";
  source: "LLM endpoint" | "deterministic fallback";
}

export interface SavedWorkspace {
  workspace_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  owner_user_id: string;
  use_case: UseCaseInput;
  selected_loop_ids: string[];
  action_plan_markdown: string;
  owner_evidence_edits: OwnerEvidenceEdit[];
  approvals: ApprovalRecord[];
  execution_records: ExecutionRecord[];
  initiatives: InitiativeWorkspace[];
  question_suggestions: QuestionSuggestion[];
  input_sources: UseCaseSource[];
}

export interface WorkspaceState {
  current_user: EnterpriseUser | null;
  active_workspace_id: string | null;
  workspaces: SavedWorkspace[];
}

export interface LoopOSData {
  metadata: Record<string, string>;
  stats: {
    loops: number;
    categories: number;
    controls: number;
    operation_cards: number;
    playbooks: number;
    control_profiles: number;
    golden_task_groups: number;
    metric_packs: number;
    handoff_rules: number;
    known_activation_gaps: number;
  };
  categories: CategorySummary[];
  loops: LoopDetail[];
  controls: Control[];
  control_profiles: ControlProfile[];
  operation_cards: OperationCard[];
  playbooks: PilotPlaybook[];
  metric_packs: MetricPack[];
  golden_tasks: GoldenTaskGroup[];
  graph: {
    version: string;
    cycle_controls: Record<string, unknown>;
    edges: LoopEdge[];
  };
  state_machine: Record<string, unknown>;
  tool_contracts: Array<Record<string, unknown>>;
  agent_topology: Record<string, unknown>;
  human_handoffs: Array<Record<string, string>>;
  practicality_gaps: Array<Record<string, string>>;
  owners: Array<Record<string, string>>;
  evidence_locations: Array<Record<string, string>>;
  probes: Array<Record<string, unknown>>;
  use_cases: UseCaseRecord[];
  validation: {
    corpus_status: string;
    validator_checks: number;
    audit: {
      status: string;
      files_scanned: number;
      lines_scanned: number;
      blockers: number | null;
      action_required: number | null;
      warnings: number | null;
    };
    required_counts: Record<string, number>;
  };
}
