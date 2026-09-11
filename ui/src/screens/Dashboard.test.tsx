import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { evaluateDeploymentPosture } from "../lib/deployment";
import { looposData } from "../lib/loopos";
import { recommendLoops } from "../lib/recommendation";
import { createInitiativeFromWorkspace } from "../lib/sdlcProductivity";
import { validateUseCase } from "../lib/validation";
import { createUser, createWorkspace } from "../lib/workspaceStore";
import { Dashboard } from "./Dashboard";

describe("Dashboard enterprise action boundary", () => {
  it("requires authority runs instead of exposing browser-local simulation actions", () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Enterprise workspace");
    const recommendations = recommendLoops(workspace.use_case, looposData);
    const validation = validateUseCase(workspace.use_case, recommendations, looposData);
    const initiative = createInitiativeFromWorkspace(workspace, recommendations, validation, looposData, user.name);
    const posture = evaluateDeploymentPosture({ VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise" });

    render(
      <Dashboard
        data={looposData}
        activeWorkspace={{ ...workspace, initiatives: [initiative] }}
        recommendations={recommendations}
        validation={validation}
        onOpenAdvisor={vi.fn()}
        onOpenPlaybook={vi.fn()}
        onOpenWorkspace={vi.fn()}
        onOpenValidation={vi.fn()}
        onOpenPlan={vi.fn()}
        onOpenLoop={vi.fn()}
        onRecordDryRun={vi.fn()}
        onCreateInitiative={vi.fn()}
        onCompleteRunStep={vi.fn()}
        onExportEvaluationPack={vi.fn()}
        posture={posture}
      />,
    );

    expect(screen.getByRole("button", { name: "Authority Run Required" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Complete In Authority" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Authority Step Required" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Prepare Initiative Draft" })).toBeEnabled();
    expect(screen.getByText("Release Assurance Authority Preparation")).toBeInTheDocument();
  });
});
