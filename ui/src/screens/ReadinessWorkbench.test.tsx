import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { evaluateDeploymentPosture } from "../lib/deployment";
import { looposData } from "../lib/loopos";
import { ReadinessWorkbench } from "./ReadinessWorkbench";

describe("ReadinessWorkbench pilot activation gate", () => {
  it("shows each known activation gap without presenting drafts as authoritative", () => {
    render(<ReadinessWorkbench data={looposData} posture={evaluateDeploymentPosture({})} />);

    expect(screen.getByRole("heading", { name: "Pilot Activation Gate" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "owners unassigned" })).toBeInTheDocument();
    expect(screen.getByText(/replace UNASSIGNED policy, gate, risk, backup, executor, and validator ownership/i)).toBeInTheDocument();
    expect(screen.getByText(/Workspace owner\/evidence edits are proposals only/i)).toBeInTheDocument();
  });
});
