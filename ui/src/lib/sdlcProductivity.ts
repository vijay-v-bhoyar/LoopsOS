import type {
  EffortSavingEstimate,
  HandoffAction,
  InitiativeStatus,
  InitiativeWorkflowType,
  InitiativeWorkspace,
  LoopDetail,
  LoopOSData,
  LoopRecommendation,
  LoopRun,
  LoopRunStep,
  RiskTier,
  SavedWorkspace,
  UseCaseValidationResult,
} from "../types";
import { createReleaseAssuranceProfile, refreshReleaseAssuranceProfile } from "./releaseAssurance";
import { nowIso, uid } from "./workspaceStore";

export const SDLC_RUNBOOK_STEPS = [
  "Trigger",
  "Qualify",
  "Observe",
  "Diagnose",
  "Prioritize",
  "Plan",
  "Authorize",
  "Execute",
  "Validate",
  "Recover if needed",
  "Record",
  "Learn",
  "Standardize",
  "Monitor effectiveness",
] as const;

const WORKFLOW_LABELS: Record<InitiativeWorkflowType, string> = {
  new_feature: "New feature",
  release: "Release",
  defect: "Defect",
  incident: "Incident",
  architecture_change: "Architecture change",
  compliance_ask: "Compliance ask",
  ai_use_case: "AI use case",
  vendor_change: "Vendor change",
};

export function inferWorkflowType(text: string): InitiativeWorkflowType {
  const value = text.toLowerCase();
  if (value.includes("incident") || value.includes("outage")) return "incident";
  if (value.includes("release") || value.includes("deploy")) return "release";
  if (value.includes("defect") || value.includes("bug") || value.includes("quality")) return "defect";
  if (value.includes("architecture") || value.includes("modernization")) return "architecture_change";
  if (value.includes("compliance") || value.includes("audit") || value.includes("regulator")) return "compliance_ask";
  if (value.includes("vendor") || value.includes("third party")) return "vendor_change";
  if (value.includes("ai") || value.includes("agent") || value.includes("rag") || value.includes("genai")) return "ai_use_case";
  return "new_feature";
}

export function workflowLabel(type: InitiativeWorkflowType): string {
  return WORKFLOW_LABELS[type];
}

export function riskFromRecommendations(recommendations: LoopRecommendation[]): RiskTier {
  const order: RiskTier[] = ["R0", "R1", "R2", "R3", "R4"];
  return recommendations.reduce<RiskTier>((highest, item) => order.indexOf(item.risk_tier) > order.indexOf(highest) ? item.risk_tier : highest, "R0");
}

export function deriveInitiativeStatus(validation: UseCaseValidationResult, hasRuns: boolean): InitiativeStatus {
  if (validation.readiness === "Blocked") return "blocked";
  if (hasRuns && validation.readiness === "Governance Review") return "validating";
  if (hasRuns) return "executing";
  if (validation.readiness === "Pilot Candidate") return "planned";
  return "discovery";
}

export function createLoopRun(loop: LoopDetail, initiativeId: string, owner: string, timestamp = nowIso()): LoopRun {
  const evidence = loop.operation_card.evidence_to_collect;
  const controls = loop.control_profile.applicable_control_ids;
  const step_records: LoopRunStep[] = SDLC_RUNBOOK_STEPS.map((label, index) => ({
    step_key: label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""),
    label,
    status: "open",
    required_evidence: evidence[index % Math.max(evidence.length, 1)] ?? "Evidence reference required.",
    required_owner: index < 6 ? loop.operation_card.primary_user : owner,
    required_controls: controls.slice(index % Math.max(controls.length - 2, 1), index % Math.max(controls.length - 2, 1) + 3),
    output: `${label} output for ${loop.name}`,
    notes: "",
  }));
  return {
    run_id: uid("loop-run"),
    loop_id: loop.loop_id,
    initiative_id: initiativeId,
    status: "not_started",
    current_step: step_records[0]?.step_key ?? "trigger",
    step_records,
    owner,
    evidence_refs: [],
    validation_result: "Not Run",
    created_at: timestamp,
    updated_at: timestamp,
  };
}

export function completeNextRunStep(run: LoopRun, timestamp = nowIso()): LoopRun {
  const openIndex = run.step_records.findIndex((step) => step.status === "open");
  if (openIndex === -1) return run;
  const step_records = run.step_records.map((step, index) =>
    index === openIndex
      ? { ...step, status: "done" as const, notes: step.notes || `${step.label} locally attested; attach authority evidence before enterprise release use.`, completed_at: timestamp }
      : step,
  );
  const next = step_records.find((step) => step.status === "open");
  return {
    ...run,
    status: next ? "running" : "validated",
    current_step: next?.step_key ?? "validated",
    step_records,
    evidence_refs: Array.from(new Set([...run.evidence_refs, step_records[openIndex].required_evidence])),
    // Completing the local checklist is not an authority validation result.
    validation_result: "Inconclusive",
    updated_at: timestamp,
  };
}

export function deriveHandoffs(loopIds: string[], data: LoopOSData, owner: string, timestamp = nowIso()): HandoffAction[] {
  const selected = new Set(loopIds);
  return data.graph.edges
    .filter((edge) => selected.has(edge.from) && selected.has(edge.to))
    .slice(0, 12)
    .map((edge, index) => ({
      handoff_id: `handoff-${edge.from}-${edge.to}-${index}`,
      from_loop_id: edge.from,
      to_loop_id: edge.to,
      reason: edge.event,
      owner,
      status: edge.priority === "high" ? "assigned" : "open",
      due_date: new Date(Date.parse(timestamp) + (index + 2) * 86400000).toISOString(),
      evidence_ref: edge.evidence,
    }));
}

export function estimateEffortSaving(initiativeId: string, loopCount: number, handoffCount: number, evidenceCount: number, completedSteps: number): EffortSavingEstimate {
  const meetings = Math.max(1, Math.ceil(loopCount / 3));
  const reviewCycles = Math.max(1, Math.ceil((handoffCount + completedSteps) / 6));
  const reusedEvidence = Math.max(evidenceCount, completedSteps);
  const hours = meetings * 1.5 + reviewCycles * 3 + reusedEvidence * 0.5 + handoffCount;
  return {
    initiative_id: initiativeId,
    meetings_avoided: meetings,
    review_cycles_reduced: reviewCycles,
    evidence_items_reused: reusedEvidence,
    hours_saved_estimate: Math.round(hours),
    assumptions: "1.5h per status meeting, 3h per review cycle, 0.5h per reused evidence item, and 1h per explicit handoff made visible.",
    confidence_basis: "Transparent estimate from loop count, handoff count, evidence references, and completed checklist steps. No model confidence is used.",
  };
}

export function createInitiativeFromWorkspace(
  workspace: SavedWorkspace,
  recommendations: LoopRecommendation[],
  validation: UseCaseValidationResult,
  data: LoopOSData,
  owner: string,
  timestamp = nowIso(),
): InitiativeWorkspace {
  const loopIds = recommendations.slice(0, 12).map((item) => item.loop_id);
  const primaryLoop = data.loops.find((loop) => loop.loop_id === loopIds[0]);
  const id = uid("initiative");
  const execution_records = primaryLoop ? [createLoopRun(primaryLoop, id, owner, timestamp)] : [];
  const handoffs = deriveHandoffs(loopIds, data, owner, timestamp);
  const evidence_records = loopIds.slice(0, 6).map((loopId, index) => ({
    evidence_id: `evidence-${id}-${index}`,
    loop_id: loopId,
    label: data.loops.find((loop) => loop.loop_id === loopId)?.operation_card.evidence_to_collect[0] ?? "Evidence reference",
    source: "workspace intake",
    freshness: "missing" as const,
    created_at: timestamp,
  }));
  const initiative: InitiativeWorkspace = {
    id,
    title: workspace.use_case.title || "SDLC productivity initiative",
    description: workspace.use_case.description,
    workflow_type: inferWorkflowType(`${workspace.use_case.title} ${workspace.use_case.description} ${workspace.use_case.aiScope}`),
    business_outcome: workspace.use_case.businessOutcome,
    maturity: workspace.use_case.maturity,
    risk: riskFromRecommendations(recommendations),
    status: deriveInitiativeStatus(validation, Boolean(execution_records.length)),
    created_at: timestamp,
    updated_at: timestamp,
    loop_bundle_ids: loopIds,
    execution_records,
    evidence_records,
    approvals: workspace.approvals,
    handoffs,
    roi_assumptions: estimateEffortSaving(id, loopIds.length, handoffs.length, evidence_records.length, 0),
  };
  return {
    ...initiative,
    release_assurance: createReleaseAssuranceProfile(workspace, initiative, data, owner, timestamp),
  };
}

export function refreshInitiative(initiative: InitiativeWorkspace, validation: UseCaseValidationResult): InitiativeWorkspace {
  const completedSteps = initiative.execution_records.reduce((total, run) => total + run.step_records.filter((step) => step.status === "done").length, 0);
  const refreshed = {
    ...initiative,
    status: deriveInitiativeStatus(validation, initiative.execution_records.length > 0),
    roi_assumptions: estimateEffortSaving(initiative.id, initiative.loop_bundle_ids.length, initiative.handoffs.length, initiative.evidence_records.length, completedSteps),
    updated_at: nowIso(),
  };
  return {
    ...refreshed,
    release_assurance: refreshed.release_assurance ? refreshReleaseAssuranceProfile(refreshed.release_assurance, refreshed) : undefined,
  };
}

export function buildEvaluationPackMarkdown(workspace: SavedWorkspace, initiative: InitiativeWorkspace, data: LoopOSData, validation: UseCaseValidationResult): string {
  const loops = initiative.loop_bundle_ids.map((id) => data.loops.find((loop) => loop.loop_id === id)).filter((loop): loop is LoopDetail => Boolean(loop));
  return [
    `# LoopOS SDLC Evaluation Pack: ${initiative.title}`,
    "",
    "Evidence status: LOCAL DRAFT - not an authoritative proof pack.",
    "Authority record: none. Human approval: not recorded.",
    "Use this artifact to prepare review; rely on the tenant-bound authority proof pack for release decisions.",
    "",
    `Status: ${initiative.status}`,
    `Workflow: ${workflowLabel(initiative.workflow_type)}`,
    `Risk: ${initiative.risk}`,
    `Readiness: ${validation.readiness}`,
    "",
    "## Business Outcome",
    "",
    initiative.business_outcome,
    "",
    "## Loop Bundle",
    "",
    ...loops.map((loop, index) => `${index + 1}. ${loop.name} - ${loop.output}`),
    "",
    "## Owners And Evidence",
    "",
    ...initiative.evidence_records.map((item) => `- ${item.label}: ${item.freshness.toUpperCase()} (${item.source})`),
    "",
    "## Approvals",
    "",
    ...(initiative.approvals.length ? initiative.approvals.map((item) => `- ${item.request_title}: ${item.status} by ${item.approver}`) : ["- No approval drafts recorded."]),
    "",
    "## Handoffs And Blockers",
    "",
    ...(initiative.handoffs.length ? initiative.handoffs.map((item) => `- ${item.reason}: ${item.status} owner ${item.owner} evidence ${item.evidence_ref}`) : ["- No loop-to-loop handoffs recorded for the current bundle."]),
    "",
    "## Execution History",
    "",
    ...(initiative.execution_records.length ? initiative.execution_records.map((run) => `- ${run.run_id}: ${run.status}, ${run.step_records.filter((step) => step.status === "done").length}/${run.step_records.length} steps complete`) : ["- No loop runs recorded."]),
    "",
    "## Release Assurance Gates",
    "",
    ...(initiative.release_assurance
      ? [
          `Mode: ${initiative.release_assurance.operating_mode}`,
          `Release: ${initiative.release_assurance.release_name}`,
          ...initiative.release_assurance.gates.map((gate) => `- ${gate.label}: ${gate.status.toUpperCase()} - ${gate.blocker}`),
        ]
      : ["- No release assurance profile recorded."]),
    "",
    "## External Evidence References",
    "",
    ...(initiative.release_assurance?.external_refs.length
      ? initiative.release_assurance.external_refs.map((ref) => `- ${ref.system.toUpperCase()} ${ref.object_type}: ${ref.label} (${ref.evidence_hash})`)
      : ["- No external release evidence references recorded."]),
    "",
    "## ROI Assumptions",
    "",
    `Estimated hours saved: ${initiative.roi_assumptions.hours_saved_estimate}`,
    initiative.roi_assumptions.assumptions,
    initiative.roi_assumptions.confidence_basis,
    "",
    "## 30/60/90 Day Plan",
    "",
    "- 30 days: run the primary loop bundle, close ownership gaps, and collect proof references.",
    "- 60 days: standardize successful loop records and retire repeated handoff gaps.",
    "- 90 days: connect authoritative systems of record and compare actual cycle-time reduction.",
    "",
    "## Workspace",
    "",
    `Workspace: ${workspace.name}`,
  ].join("\n");
}

export function buildIssueTicketText(initiative: InitiativeWorkspace): string {
  return [
    `[LoopOS] ${initiative.title}`,
    "",
    `Workflow: ${workflowLabel(initiative.workflow_type)}`,
    `Status: ${initiative.status}`,
    `Risk: ${initiative.risk}`,
    `Business outcome: ${initiative.business_outcome}`,
    `Open handoffs: ${initiative.handoffs.filter((item) => item.status !== "closed").length}`,
    `Estimated effort saved: ${initiative.roi_assumptions.hours_saved_estimate} hours`,
    "",
    "Next action: assign owners for open handoffs, run the primary loop checklist, and attach evidence references.",
  ].join("\n");
}
