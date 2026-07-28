import { afterEach, describe, expect, it, vi } from "vitest";
import {
  canApprove,
  createApproval,
  createExecution,
  createUser,
  createWorkspace,
  DEFAULT_WORKSPACE_USE_CASE,
  loadWorkspaceState,
  saveWorkspaceState,
  MAX_WORKSPACE_STORAGE_BYTES,
} from "./workspaceStore";

describe("workspaceStore", () => {
  afterEach(() => vi.restoreAllMocks());

  it("creates a local workspace with empty governance records", () => {
    const user = createUser("Vijay", "vijay@example.local", "Operator");
    const workspace = createWorkspace(user, "Agentic AI Workspace", DEFAULT_WORKSPACE_USE_CASE);

    expect(workspace.name).toBe("Agentic AI Workspace");
    expect(workspace.owner_user_id).toBe(user.user_id);
    expect(workspace.owner_evidence_edits).toEqual([]);
    expect(workspace.approvals).toEqual([]);
    expect(workspace.execution_records).toEqual([]);
    expect(workspace.input_sources).toEqual([]);
  });

  it("migrates older saved workspaces with an empty input source register", () => {
    const user = createUser("Vijay", "vijay@example.local", "Operator");
    const legacyWorkspace = createWorkspace(user, "Legacy workspace", DEFAULT_WORKSPACE_USE_CASE) as unknown as Record<string, unknown>;
    delete legacyWorkspace.input_sources;
    window.localStorage.setItem(
      "loopos.v2.workspace-state",
      JSON.stringify({ current_user: user, active_workspace_id: legacyWorkspace.workspace_id, workspaces: [legacyWorkspace] }),
    );

    const state = loadWorkspaceState();

    expect(state.workspaces[0].input_sources).toEqual([]);
  });

  it("rejects malformed workspace records instead of trusting local storage", () => {
    window.localStorage.setItem(
      "loopos.v2.workspace-state",
      JSON.stringify({ current_user: { role: "Administrator" }, active_workspace_id: "bad", workspaces: [{ workspace_id: "bad", use_case: "not-an-object" }] }),
    );

    const state = loadWorkspaceState();

    expect(state.current_user).toBeNull();
    expect(state.workspaces).toEqual([]);
    expect(state.active_workspace_id).toBeNull();
  });

  it("reports storage and size failures to the caller", () => {
    const tooLarge = { ...DEFAULT_WORKSPACE_USE_CASE, description: "x".repeat(MAX_WORKSPACE_STORAGE_BYTES) };
    const user = createUser("Vijay", "vijay@example.local", "Operator");
    const largeState = { current_user: user, active_workspace_id: "large", workspaces: [{ ...createWorkspace(user, "Large", tooLarge), workspace_id: "large" }] };
    expect(saveWorkspaceState(largeState)).toMatchObject({ status: "error", code: "size_limit" });

    vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new DOMException("Storage is unavailable", "QuotaExceededError");
    });
    expect(saveWorkspaceState({ current_user: null, active_workspace_id: null, workspaces: [] })).toMatchObject({ status: "error", code: "storage_unavailable" });
  });

  it("keeps approval authority role-bound in the local workflow", () => {
    expect(canApprove(createUser("Approver", "approver@example.local", "Approver"))).toBe(true);
    expect(canApprove(createUser("Executive", "exec@example.local", "Executive"))).toBe(true);
    expect(canApprove(createUser("Operator", "operator@example.local", "Operator"))).toBe(false);
    expect(canApprove(null)).toBe(false);
  });

  it("creates pending approval and execution records", () => {
    const approval = createApproval({
      loop_id: "loop-079-agent-guardrail-loop",
      request_title: "Agent guardrail pilot",
      requested_by: "Operator",
      approver: "Approver",
      risk_tier: "R3",
      evidence_summary: "Evidence packet",
      decision_reason: "",
    });

    const execution = createExecution({
      loop_id: "loop-079-agent-guardrail-loop",
      title: "Run guardrail validation",
      correlation_id: "corr-test",
      state: "TRIGGERED",
      risk_tier: "R3",
      evidence_refs: "eval log",
      validation_result: "Not Run",
      proof_state: "Not Started",
      owner: "Operator",
    });

    expect(approval.status).toBe("Pending");
    expect(approval.approval_id).toMatch(/^approval-/);
    expect(execution.execution_id).toMatch(/^execution-/);
    expect(execution.state).toBe("TRIGGERED");
  });
});
