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
      // Local reference hashes are graph seeds, not fetched external evidence.
      freshness: "missing" as const,
      required: true,
      observed_at: undefined,
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
  return index % 5 === 0 ? "exception_active" : "review_required";
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
      label: "Proof-pack prep planning estimate",
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
  // Keep draft generation synchronous while producing the same digest shape as authority proof artifacts.
  const bytes = new TextEncoder().encode(value);
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const message = new Uint8Array(paddedLength);
  message.set(bytes);
  message[bytes.length] = 0x80;
  const view = new DataView(message.buffer);
  const bitLength = bytes.length * 8;
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000), false);
  view.setUint32(paddedLength - 4, bitLength >>> 0, false);

  const roundConstants = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  let hash = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const schedule = new Uint32Array(64);
  const rotateRight = (word: number, bits: number): number => (word >>> bits) | (word << (32 - bits));

  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      schedule[index] = view.getUint32(offset + index * 4, false);
    }
    for (let index = 16; index < 64; index += 1) {
      const smallSigma0 = rotateRight(schedule[index - 15], 7) ^ rotateRight(schedule[index - 15], 18) ^ (schedule[index - 15] >>> 3);
      const smallSigma1 = rotateRight(schedule[index - 2], 17) ^ rotateRight(schedule[index - 2], 19) ^ (schedule[index - 2] >>> 10);
      schedule[index] = (schedule[index - 16] + smallSigma0 + schedule[index - 7] + smallSigma1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const bigSigma1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temporary1 = (h + bigSigma1 + choice + roundConstants[index] + schedule[index]) >>> 0;
      const bigSigma0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temporary2 = (bigSigma0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temporary1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temporary1 + temporary2) >>> 0;
    }
    hash = hash.map((word, index) => (word + [a, b, c, d, e, f, g, h][index]) >>> 0);
  }

  return hash.map((word) => word.toString(16).padStart(8, "0")).join("");
}
