import { describe, expect, it } from "vitest";
import { looposData } from "./loopos";
import {
  createReleaseAssuranceProfile,
  isReleaseAssuranceCandidate,
  releaseAssuranceLoops,
  summarizeGateStatus,
} from "./releaseAssurance";
import { createInitiativeFromWorkspace } from "./sdlcProductivity";
import { validateUseCase } from "./validation";
import { recommendLoops } from "./recommendation";
import { createUser, createWorkspace } from "./workspaceStore";

describe("releaseAssurance", () => {
  const user = createUser("Mira Patel", "mira@example.local", "Approver");
  const workspace = createWorkspace(user, "Release assurance", {
    title: "Prepare release 2026.08",
    description: "Use Jira release scope and GitHub pull request evidence to govern a production deployment.",
    environment: "production",
    aiScope: "Release governance",
    dataSensitivity: "sensitive",
    businessOutcome: "Reduce release meetings and audit prep while preserving approval evidence.",
    maturity: "pilot",
    constraints: "Requires release readiness, rollback proof, CI checks, review evidence, and post-release validation.",
  });
  const recommendations = recommendLoops(workspace.use_case, looposData);
  const validation = validateUseCase(workspace.use_case, recommendations, looposData, []);
  const initiative = createInitiativeFromWorkspace(workspace, recommendations, validation, looposData, user.name, "2026-07-23T12:00:00.000Z");

  it("recognizes release and change workspaces as release assurance candidates", () => {
    expect(isReleaseAssuranceCandidate(workspace)).toBe(true);
  });

  it("selects release-critical loops even when the recommendation bundle is broader", () => {
    const loops = releaseAssuranceLoops(looposData, initiative.loop_bundle_ids);
    const names = loops.map((loop) => loop.name);

    expect(names).toContain("Release Readiness Loop");
    expect(names).toContain("Deployment Validation Loop");
    expect(names).toContain("Rollback, Backup and Recovery Loop");
  });

  it("creates deterministic gates with GitHub and Jira evidence posture", () => {
    const profile = createReleaseAssuranceProfile(workspace, initiative, looposData, user.name, "2026-07-23T12:00:00.000Z");
    const counts = summarizeGateStatus(profile);

    expect(profile.operating_mode).toBe("shadow_release");
    expect(profile.connectors.map((connector) => connector.system)).toEqual(["jira", "github", "manual"]);
    expect(profile.connectors.every((connector) => connector.trust_boundary.length > 0)).toBe(true);
    expect(profile.external_refs.map((ref) => ref.system)).toEqual(["jira", "github", "manual"]);
    expect(profile.gates.length).toBeGreaterThan(5);
    expect(counts.blocked).toBeGreaterThan(0);
    expect(profile.gates.every((gate) => gate.last_decision?.source_ref_ids.length)).toBe(true);
    expect(profile.metric_observations.every((metric) => !metric.basis.match(/\d+% confidence/i))).toBe(true);
  });
});
