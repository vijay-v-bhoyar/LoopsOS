import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function renderSignedIn(role: "Operator" | "Approver" = "Operator") {
  render(<App />);
  expect(screen.getByText("LoopOS Evaluation Workspace")).toBeInTheDocument();
  if (role !== "Operator") fireEvent.change(screen.getByLabelText("Simulation role"), { target: { value: role } });
  fireEvent.click(screen.getByText("Enter Evaluation Workspace"));
}

function openWorkspaces() {
  fireEvent.click(screen.getAllByRole("button", { name: "Workspaces" })[0]);
}

function loadExampleUseCase() {
  fireEvent.click(screen.getByText("Open Use Case Advisor"));
  fireEvent.click(screen.getByRole("button", { name: "Load Example" }));
  fireEvent.click(screen.getAllByRole("button", { name: "Dashboard" })[0]);
}

describe("LoopOS Enterprise UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  it("renders dashboard corpus counts", () => {
    renderSignedIn();
    expect(screen.getByText("LoopOS Enterprise Console")).toBeInTheDocument();
    expect(screen.getByText("108")).toBeInTheDocument();
    expect(screen.getByText("109")).toBeInTheDocument();
    expect(screen.getAllByText(/Evaluation only/i).length).toBeGreaterThan(0);
  });

  it("turns dashboard actions into workspace outputs", () => {
    renderSignedIn();
    loadExampleUseCase();
    expect(screen.getByText("SDLC Command Center")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record Dry Run" }));
    expect(screen.getByText("latest loop output")).toBeInTheDocument();
    let state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
    expect(state.workspaces[0].execution_records).toHaveLength(1);
    expect(state.workspaces[0].selected_loop_ids.length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Build Action Plan" }));
    expect(screen.getByText("Enterprise Action Plan")).toBeInTheDocument();
    state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
    expect(state.workspaces[0].action_plan_markdown).toContain("LoopOS Enterprise Action Plan");
  });

  it("creates SDLC initiatives, runs checklist steps, and exports proof packs from the command center", () => {
    renderSignedIn();
    loadExampleUseCase();
    expect(screen.getByText("SDLC Command Center")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create SDLC Initiative" }));
    expect(screen.getByText("Actionable loop runbook")).toBeInTheDocument();
    expect(screen.getByText("Handoff And Blocker Control")).toBeInTheDocument();
    expect(screen.getByText("SDLC Productivity Scorecard")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Complete step" })[0]);
    expect(screen.getByText(/1\/14 steps/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Export Proof Pack" }));
    const state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
    expect(state.workspaces[0].initiatives).toHaveLength(1);
    expect(state.workspaces[0].initiatives[0].execution_records[0].step_records[0].status).toBe("done");
    expect(state.workspaces[0].action_plan_markdown).toContain("LoopOS SDLC Proof Pack");
    expect(screen.getByText("Issue-ticket-ready output")).toBeInTheDocument();
  });

  it("exposes every primary destination through the mobile navigation menu", () => {
    renderSignedIn();
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    const navigation = screen.getByRole("dialog", { name: "Navigation" });
    expect(navigation).toBeInTheDocument();
    fireEvent.click(within(navigation).getByRole("button", { name: "Readiness" }));
    expect(screen.getByRole("heading", { name: "Enterprise Activation Readiness" })).toBeInTheDocument();
  });

  it("opens the advisor and shows recommendations", () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Open Use Case Advisor"));
    expect(screen.getAllByText("Use Case Advisor").length).toBeGreaterThan(0);
    expect(screen.getByText("Recommendation Result")).toBeInTheDocument();
    expect(screen.getByLabelText("AI scope")).toHaveValue("");
    expect(screen.getByLabelText("Environment")).toHaveValue("");
    expect(screen.getByLabelText("Data sensitivity")).toHaveValue("");
    expect(screen.getByLabelText("Maturity")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Load Example" })).toBeInTheDocument();
  });

  it("lets users deep dive into what a loop will do", () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Loop Explorer"));
    expect(screen.getByRole("heading", { name: "Production-Grade Run Sequence" })).toBeInTheDocument();
    expect(screen.getByText("First 10 Minutes")).toBeInTheDocument();
    expect(screen.getByText("Evidence To Collect")).toBeInTheDocument();
    expect(screen.getByText("Proof To Run")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Golden Tasks And Expected Outputs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Controls This Loop Must Satisfy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connected Loop Handoffs" })).toBeInTheDocument();
  });

  it("opens validation studio without overstating readiness", () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Validation Studio"));
    expect(screen.getAllByText("Activation gaps").length).toBeGreaterThan(0);
    expect(screen.getByText(/Framework-level DRAFT gaps/)).toBeInTheDocument();
  });

  it("runs the workspace flow for questions, owner evidence, approvals, and governed execution access", async () => {
    renderSignedIn("Approver");
    openWorkspaces();

    expect(screen.getByText("Saved Workspace Console")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Generate Questions"));
    await waitFor(() => {
      const state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
      expect(state.workspaces[0].question_suggestions.length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("deterministic fallback").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Save Owner/Evidence Edit"));
    expect(screen.getByText(/GRC \/ evidence store URL/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Save Approval Draft"));
    expect(screen.getByText("Pending")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Approve"));
    expect(screen.getByText("Approved")).toBeInTheDocument();

    expect(screen.getByText("Governed Execution Authority")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText(/Authority unavailable/i).length).toBeGreaterThan(0));
  });

  it("saves an enterprise action plan into the active workspace", () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Open Use Case Advisor"));
    fireEvent.click(screen.getByRole("button", { name: "Load Example" }));
    fireEvent.click(screen.getByText("Send To Action Plan"));
    expect(screen.getByText("Enterprise Action Plan")).toBeInTheDocument();

    openWorkspaces();
    expect(screen.getByText("Saved loops")).toBeInTheDocument();
    const state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
    expect(state.workspaces[0].selected_loop_ids).toHaveLength(12);
  });

  it("requires confirmation before permanently deleting a local workspace", async () => {
    renderSignedIn();
    openWorkspaces();
    fireEvent.click(screen.getByRole("button", { name: "Delete workspace" }));
    expect(screen.getByRole("dialog", { name: "Delete workspace?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));

    expect(screen.getByText("Saved Workspaces")).toBeInTheDocument();
    await waitFor(() => {
      const state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
      expect(state.workspaces).toEqual([]);
    });
  });

  it("accepts reviewed multimodal text into the workspace and groups source-backed recommendations", async () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Open Use Case Advisor"));
    const brief = [
      "# Agentic claims triage",
      "Workflow: Use AI agents with delegated tools and memory to triage insurance claims.",
      "Environment: production",
      "AI scope: Agentic AI",
      "Data sensitivity: regulated",
      "Business outcome: Reduce claims cycle time while preserving review quality.",
      "Maturity: pilot",
      "Constraints: Must preserve audit evidence, access controls, guardrails, and human approval.",
    ].join("\n");
    fireEvent.change(screen.getByLabelText("Describe the use case"), { target: { value: brief } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze and review" }));
    expect(await screen.findByRole("dialog", { name: "Review proposed use case" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Apply selected fields" }));

    await waitFor(() => {
      const state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
      expect(state.workspaces[0].input_sources).toHaveLength(1);
      expect(state.workspaces[0].input_sources[0]).toMatchObject({ label: "Typed use case", status: "accepted" });
      expect(state.workspaces[0].use_case.title).toBe("Agentic claims triage");
    });
    expect(screen.getByText("Primary loops")).toBeInTheDocument();
    expect(screen.getAllByText(/in Typed use case/).length).toBeGreaterThan(0);
  });

  it("does not mix a real use case with the preloaded demonstration", async () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Open Use Case Advisor"));
    fireEvent.change(screen.getByLabelText("Describe the use case"), {
      target: {
        value: "Our software team needs to reduce failed releases by checking change tickets, test results, approvals, rollback plans, and deployment evidence before promoting to production. The pilot uses internal engineering data and requires an auditable go or no-go decision.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze and review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Apply selected fields" }));

    await waitFor(() => {
      const state = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
      expect(state.workspaces[0].use_case).toMatchObject({
        title: "",
        aiScope: "",
        businessOutcome: "",
        constraints: "",
      });
      expect(state.workspaces[0].use_case.description).toContain("reduce failed releases");
    });
    expect(screen.queryByText(/Agent Memory Loop/)).not.toBeInTheDocument();
  });

  it("switches to recommendation mode after applying intake and lets the user return to input", async () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Open Use Case Advisor"));
    expect(screen.getByRole("button", { name: /Show input/i })).toHaveAttribute("aria-pressed", "true");

    fireEvent.change(screen.getByLabelText("Describe the use case"), {
      target: { value: "# Claims triage\nWorkflow: Use governed AI agents to triage incoming claims with human approval." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze and review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Apply selected fields" }));

    expect(screen.getByRole("button", { name: /Show recommendations/i })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Edit use case/i }));
    expect(screen.getByRole("button", { name: /Show input/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("records view history and provides an in-app back control", async () => {
    renderSignedIn();
    fireEvent.click(screen.getByText("Open Use Case Advisor"));
    expect(window.location.hash).toBe("#advisor");

    fireEvent.click(screen.getByText("Send To Action Plan"));
    expect(screen.getByText("Enterprise Action Plan")).toBeInTheDocument();
    expect(window.location.hash).toBe("#plan");

    fireEvent.click(screen.getByRole("button", { name: "Back to previous screen" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Use Case Advisor" })).toBeInTheDocument());
    expect(window.location.hash).toBe("#advisor");
  });
});
