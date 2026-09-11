import { describe, expect, it } from "vitest";
import { looposData } from "./loopos";
import { recommendLoops } from "./recommendation";
import {
  buildIssueTicketText,
  buildEvaluationPackMarkdown,
  completeNextRunStep,
  createInitiativeFromWorkspace,
  createLoopRun,
  deriveHandoffs,
  estimateEffortSaving,
  inferWorkflowType,
} from "./sdlcProductivity";
import { validateUseCase } from "./validation";
import { createUser, createWorkspace } from "./workspaceStore";

describe("sdlcProductivity", () => {
  const user = createUser("Asha Rao", "asha@example.local", "Operator");
  const workspace = createWorkspace(user, "Release Workspace", {
    title: "Prepare release 2026.08",
    description: "We are preparing a high-risk release and want to reduce review meetings, handoff churn, and missing evidence.",
    environment: "production",
    aiScope: "Release/compliance governance",
    dataSensitivity: "sensitive",
    businessOutcome: "Reduce release cycle time while keeping approvals and evidence visible.",
    maturity: "pilot",
    constraints: "Needs owner evidence, release readiness, validation, and handoff closure.",
  });
  const recommendations = recommendLoops(workspace.use_case, looposData);
  const validation = validateUseCase(workspace.use_case, recommendations, looposData, []);

  it("creates an SDLC initiative from intake with bundle, run, handoffs, and ROI", () => {
    const initiative = createInitiativeFromWorkspace(workspace, recommendations, validation, looposData, user.name, "2026-07-23T12:00:00.000Z");
    expect(initiative.workflow_type).toBe("release");
    expect(initiative.loop_bundle_ids.length).toBeGreaterThan(0);
    expect(initiative.execution_records).toHaveLength(1);
    expect(initiative.execution_records[0].step_records).toHaveLength(14);
    expect(initiative.handoffs.length).toBeGreaterThan(0);
    expect(initiative.roi_assumptions.hours_saved_estimate).toBeGreaterThan(0);
    expect(initiative.roi_assumptions.confidence_basis).toContain("No model confidence");
  });

  it("advances a loop run checklist and updates validation output", () => {
    const loop = looposData.loops[0];
    const run = createLoopRun(loop, "initiative-1", user.name, "2026-07-23T12:00:00.000Z");
    const next = completeNextRunStep(run, "2026-07-23T12:05:00.000Z");
    expect(next.step_records[0]).toMatchObject({ status: "done", completed_at: "2026-07-23T12:05:00.000Z" });
    expect(next.step_records[0].notes).toContain("locally attested");
    expect(next.step_records[0].notes).not.toContain("completed with local workspace evidence");
    expect(next.current_step).toBe("qualify");
    expect(next.evidence_refs.length).toBe(1);
    expect(next.validation_result).toBe("Inconclusive");
  });

  it("keeps a fully completed local checklist inconclusive until authority evidence exists", () => {
    const loop = looposData.loops[0];
    let run = createLoopRun(loop, "initiative-1", user.name, "2026-07-23T12:00:00.000Z");
    for (let index = 0; index < run.step_records.length; index += 1) {
      run = completeNextRunStep(run, `2026-07-23T12:${String(index + 1).padStart(2, "0")}:00.000Z`);
    }

    expect(run.status).toBe("validated");
    expect(run.validation_result).toBe("Inconclusive");
  });

  it("generates proof pack and issue-ticket-ready text with required sections", () => {
    const initiative = createInitiativeFromWorkspace(workspace, recommendations, validation, looposData, user.name, "2026-07-23T12:00:00.000Z");
    const evaluationPack = buildEvaluationPackMarkdown(workspace, initiative, looposData, validation);
    expect(evaluationPack).toContain("# LoopOS SDLC Evaluation Pack");
    expect(evaluationPack).toContain("not an authoritative proof pack");
    expect(evaluationPack).toContain("## Loop Bundle");
    expect(evaluationPack).toContain("## Handoffs And Blockers");
    expect(evaluationPack).toContain("## ROI Assumptions");
    expect(evaluationPack).toContain("## Release Assurance Gates");
    expect(evaluationPack).toContain("## External Evidence References");
    expect(initiative.release_assurance?.connectors.map((connector) => connector.system)).toEqual(["jira", "github", "manual"]);
    expect(evaluationPack).toContain("## 30/60/90 Day Plan");
    expect(buildIssueTicketText(initiative)).toContain("[LoopOS]");
  });

  it("derives workflow and handoffs deterministically", () => {
    expect(inferWorkflowType("production defect keeps recurring")).toBe("defect");
    const handoffs = deriveHandoffs(recommendations.slice(0, 12).map((item) => item.loop_id), looposData, user.name, "2026-07-23T12:00:00.000Z");
    expect(handoffs.every((handoff) => handoff.owner === user.name)).toBe(true);
  });

  it("keeps effort saving transparent and editable instead of model-scored", () => {
    const estimate = estimateEffortSaving("initiative-1", 12, 5, 6, 3);
    expect(estimate.hours_saved_estimate).toBeGreaterThan(0);
    expect(estimate.assumptions).toContain("1.5h per status meeting");
    expect(estimate.confidence_basis).not.toMatch(/\d+%/);
  });
});
