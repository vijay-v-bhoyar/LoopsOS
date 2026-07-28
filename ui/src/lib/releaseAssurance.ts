import type {
  ConnectorInstallation,
  ExternalObjectRef,
  InitiativeWorkspace,
  LoopDetail,
  LoopOSData,
  MetricObservation,
  ReleaseAssuranceProfile,
  ReleaseGate,
  ReleaseGateStatus,
  RiskException,
  SavedWorkspace,
} from "../types";
import { nowIso, uid } from "./workspaceStore";

const RELEASE_LOOP_KEYWORDS = [
  "requirements traceability",
  "pull request review",
  "ci pipeline",
  "regression testing",
  "secure sdlc",
  "software supply chain",
  "release readiness",
  "operational readiness",
  "deployment validation",
  "rollback",
  "observability",
  "incident",
  "audit logging",
];

const CONNECTORS: ConnectorInstallation[] = [
  {
    connector_id: "connector-jira-cloud",
    system: "jira",
    mode: "shadow_read",
    label: "Jira Cloud release evidence",
    required_for: ["requirements", "owners", "release scope", "decision comments"],
    write_scope: "comment",
    trust_boundary: "Reads are automatic in production; write-back is approval-gated and payload-bound.",
  },
  {
    connector_id: "connector-github-app",
    system: "github",
    mode: "shadow_read",
    label: "GitHub App change evidence",
    required_for: ["pull requests", "commits", "checks", "workflow runs", "release status checks"],
    write_scope: "status_check",
    trust_boundary: "Credentials stay server-side; release status changes require governed authority approval.",
  },
  {
    connector_id: "connector-manual-attestation",
    system: "manual",
    mode: "export_ready",
    label: "Manual attestation fallback",
    required_for: ["pilot proof packs", "offline evidence references", "exception reasons"],
    write_scope: "none",
    trust_boundary: "Manual evidence is visible as pilot evidence, not system-of-record authority.",
  },
];

export function isReleaseAssuranceCandidate(workspace: SavedWorkspace): boolean {
  const text = [
    workspace.use_case.title,
    workspace.use_case.description,
    workspace.use_case.environment,
    workspace.use_case.businessOutcome,
    workspace.use_case.constraints,
  ].join(" ").toLowerCase();
  return ["release", "deploy", "change", "jira", "github", "pull request", "production", "rollback"].some((term) => text.includes(term));
}

export function releaseAssuranceLoops(data: LoopOSData, selectedLoopIds: string[]): LoopDetail[] {
  const selected = new Set(selectedLoopIds);
  const candidates = data.loops.filter((loop) => {
    const text = `${loop.name} ${loop.trigger} ${loop.output}`.toLowerCase();
    return selected.has(loop.loop_id) || RELEASE_LOOP_KEYWORDS.some((term) => text.includes(term));
  });
  return dedupeByLoop(candidates)
    .sort((left, right) => releaseLoopPriority(right, selected) - releaseLoopPriority(left, selected))
    .slice(0, 12);
}

export function createReleaseAssuranceProfile(
  workspace: SavedWorkspace,
  initiative: InitiativeWorkspace,
  data: LoopOSData,
  actorName: string,
  timestamp = nowIso(),
): ReleaseAssuranceProfile {
  const loops = releaseAssuranceLoops(data, initiative.loop_bundle_ids);
  const releaseName = inferReleaseName(workspace);
  const externalRefs = createExternalRefs(workspace, releaseName, timestamp);
  const gates = createReleaseGates(loops, externalRefs, actorName, timestamp);
  const evidenceArtifacts = gates.flatMap((gate) =>
    gate.required_evidence.map((label, index) => ({
      artifact_id: `${gate.gate_id}-evidence-${index}`,
      gate_id: gate.gate_id,
      loop_id: gate.loop_id,
      source_ref: externalRefs[index % externalRefs.length]?.ref_id ?? "manual-release-note",
      label,
      freshness: gate.status === "gap" || gate.status === "blocked" ? "missing" as const : "fresh" as const,
      required: true,
      observed_at: gate.status === "gap" || gate.status === "blocked" ? undefined : timestamp,
    })),
  );
  const decisions = gates.map((gate) => gate.last_decision).filter((decision): decision is NonNullable<ReleaseGate["last_decision"]> => Boolean(decision));
  return {
    profile_id: uid("release-assurance"),
    initiative_id: initiative.id,
    release_name: releaseName,
    operating_mode: isReleaseAssuranceCandidate(workspace) ? "shadow_release" : "local_draft",
    connectors: CONNECTORS,
    external_refs: externalRefs,
    gates,
    evidence_artifacts: evidenceArtifacts,
    decisions,
    exceptions: createDefaultExceptions(gates, actorName, timestamp),
    metric_observations: createMetricObservations(initiative, externalRefs),
    proof_pack_scope: [
      "Jira release scope and owner evidence",
      "GitHub PR, commit, review, check, and workflow evidence",
      "Loop gate decisions with gap status",
      "Risk exceptions with expiry and compensating controls",
      "Post-release validation and effort-saving measurements",
    ],
  };
}

export function refreshReleaseAssuranceProfile(profile: ReleaseAssuranceProfile, initiative: InitiativeWorkspace): ReleaseAssuranceProfile {
  return {
    ...profile,
    metric_observations: createMetricObservations(initiative, profile.external_refs),
  };
}

export function summarizeGateStatus(profile?: ReleaseAssuranceProfile): Record<ReleaseGateStatus, number> {
  const counts: Record<ReleaseGateStatus, number> = {
    passed: 0,
    gap: 0,
    review_required: 0,
    exception_active: 0,
    blocked: 0,
  };
  for (const gate of profile?.gates ?? []) counts[gate.status] += 1;
  return counts;
}

function createReleaseGates(loops: LoopDetail[], refs: ExternalObjectRef[], actorName: string, timestamp: string): ReleaseGate[] {
  return loops.map((loop, index) => {
    const status = statusForLoop(loop, index);
    const gateId = `gate-${loop.loop_id}`;
    return {
      gate_id: gateId,
      label: loop.name,
      loop_id: loop.loop_id,
      control_ids: loop.control_profile.applicable_control_ids.slice(0, 6),
      required_evidence: loop.operation_card.evidence_to_collect.slice(0, 3),
      status,
      blocker: blockerFor(status, loop),
      last_decision: {
        decision_id: uid("gate-decision"),
        gate_id: gateId,
        status,
        decided_by: actorName,
        decided_at: timestamp,
        basis: basisFor(status, loop),
        source_ref_ids: refs.map((ref) => ref.ref_id).slice(0, 3),
      },
    };
  });
}

function statusForLoop(loop: LoopDetail, index: number): ReleaseGateStatus {
  const name = loop.name.toLowerCase();
  if (name.includes("rollback") || name.includes("secure") || name.includes("supply chain")) return "review_required";
  if (name.includes("deployment validation") || name.includes("observability")) return "gap";
  if (name.includes("release readiness")) return "blocked";
  return index % 5 === 0 ? "exception_active" : "passed";
}

function blockerFor(status: ReleaseGateStatus, loop: LoopDetail): string {
  if (status === "passed") return "No blocker recorded from available evidence.";
  if (status === "gap") return `Missing fresh ${loop.operation_card.evidence_to_collect[0] ?? "release evidence"}.`;
  if (status === "review_required") return "Approver must review evidence before gated write-back or release status update.";
  if (status === "exception_active") return "Temporary exception requires expiry, reason, and compensating control.";
  return "Release readiness is blocked until required evidence and gate decisions are attached.";
}

function basisFor(status: ReleaseGateStatus, loop: LoopDetail): string {
  if (status === "passed") return `Recorded metadata satisfies the current ${loop.name} release gate for shadow evaluation.`;
  return blockerFor(status, loop);
}

function createDefaultExceptions(gates: ReleaseGate[], actorName: string, timestamp: string): RiskException[] {
  return gates
    .filter((gate) => gate.status === "exception_active")
    .map((gate, index) => ({
      exception_id: uid("risk-exception"),
      gate_id: gate.gate_id,
      reason: gate.blocker,
      approver: actorName,
      expires_at: new Date(Date.parse(timestamp) + (index + 7) * 86400000).toISOString(),
      compensating_controls: gate.control_ids.slice(0, 2),
      status: "active",
    }));
}

function createMetricObservations(initiative: InitiativeWorkspace, refs: ExternalObjectRef[]): MetricObservation[] {
  const completedSteps = initiative.execution_records.reduce((count, run) => count + run.step_records.filter((step) => step.status === "done").length, 0);
  const openHandoffs = initiative.handoffs.filter((handoff) => handoff.status !== "closed").length;
  return [
    {
      metric_id: "release-proof-pack-prep-hours-avoided",
      label: "Proof-pack prep avoided",
      value: Math.max(1, initiative.roi_assumptions.evidence_items_reused),
      unit: "hours",
      basis: "One hour per reused evidence item; replace with measured baseline after two shadow releases.",
      source_ref_ids: refs.map((ref) => ref.ref_id),
    },
    {
      metric_id: "release-handoff-risk-count",
      label: "Open release handoffs",
      value: openHandoffs,
      unit: "count",
      basis: "Count of unresolved loop-to-loop handoff actions in the initiative.",
      source_ref_ids: refs.map((ref) => ref.ref_id).slice(0, 2),
    },
    {
      metric_id: "release-runbook-step-count",
      label: "Runbook steps completed",
      value: completedSteps,
      unit: "count",
      basis: "Completed local runbook steps; authoritative completion requires authority run evidence.",
      source_ref_ids: refs.map((ref) => ref.ref_id).slice(0, 2),
    },
  ];
}

function createExternalRefs(workspace: SavedWorkspace, releaseName: string, timestamp: string): ExternalObjectRef[] {
  return [
    {
      ref_id: "jira-release-scope",
      system: "jira",
      object_type: "release",
      label: `${releaseName} release scope`,
      observed_at: timestamp,
      evidence_hash: hashText(`${workspace.workspace_id}:jira:${releaseName}`),
    },
    {
      ref_id: "github-change-set",
      system: "github",
      object_type: "pull_request",
      label: `${releaseName} change set`,
      observed_at: timestamp,
      evidence_hash: hashText(`${workspace.workspace_id}:github:${releaseName}`),
    },
    {
      ref_id: "manual-release-attestation",
      system: "manual",
      object_type: "manual_note",
      label: "Pilot release attestation",
      observed_at: timestamp,
      evidence_hash: hashText(`${workspace.workspace_id}:manual:${workspace.updated_at}`),
    },
  ];
}

function inferReleaseName(workspace: SavedWorkspace): string {
  const text = `${workspace.use_case.title} ${workspace.use_case.description}`;
  const match = text.match(/\b(?:release|version|v)\s*([a-z0-9._-]+)/i);
  return match ? `Release ${match[1]}` : workspace.use_case.title || "LoopOS governed release";
}

function dedupeByLoop(loops: LoopDetail[]): LoopDetail[] {
  const seen = new Set<string>();
  return loops.filter((loop) => {
    if (seen.has(loop.loop_id)) return false;
    seen.add(loop.loop_id);
    return true;
  });
}

function releaseLoopPriority(loop: LoopDetail, selected: Set<string>): number {
  const name = loop.name.toLowerCase();
  let priority = selected.has(loop.loop_id) ? 20 : 0;
  if (name.includes("release readiness")) priority += 50;
  if (name.includes("deployment validation")) priority += 45;
  if (name.includes("rollback")) priority += 45;
  if (name.includes("ci pipeline")) priority += 35;
  if (name.includes("pull request review")) priority += 35;
  if (name.includes("requirements traceability")) priority += 30;
  if (name.includes("regression testing")) priority += 30;
  if (name.includes("secure sdlc") || name.includes("supply chain")) priority += 30;
  if (name.includes("observability") || name.includes("incident")) priority += 20;
  return priority;
}

function hashText(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `local-fnv1a-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}
