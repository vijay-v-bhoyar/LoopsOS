import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthorityError } from "../features/governedExecution/authorityClient";
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
  useWorkspaceStore,
} from "./workspaceStore";

describe("workspaceStore", () => {
  afterEach(() => vi.restoreAllMocks());

  it("starts a new workspace without demo use-case classifications", () => {
    const user = createUser("Vijay", "vijay@example.local", "Operator");

    const workspace = createWorkspace(user, "Production release review");

    expect(workspace.use_case).toEqual({
      title: "",
      description: "",
      environment: "",
      aiScope: "",
      dataSensitivity: "",
      businessOutcome: "",
      maturity: "",
      constraints: "",
    });
  });

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

  it("hydrates enterprise identity and workspaces from authority without browser persistence", async () => {
    const localUser = createUser("Local", "local@example.local", "Operator");
    const authoritativeWorkspace = createWorkspace(localUser, "Authoritative claims", DEFAULT_WORKSPACE_USE_CASE);
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue({
        status: "ready",
        storage_backend: "postgres",
        production_identity: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
      }),
      createSession: vi.fn().mockResolvedValue({
        access_token: "enterprise-token",
        token_type: "bearer",
        expires_in: 900,
        actor: {
          tenant_id: "tenant-enterprise",
          user_id: "oidc-user-42",
          name: "Enterprise Approver",
          email: "approver@example.com",
          role: "Approver",
        },
      }),
      listWorkspaces: vi.fn().mockResolvedValue([{
        workspace_id: authoritativeWorkspace.workspace_id,
        tenant_id: "tenant-enterprise",
        revision: 7,
        document: authoritativeWorkspace,
        document_hash: "a".repeat(64),
        created_by: "oidc-user-42",
        updated_by: "oidc-user-42",
        created_at: authoritativeWorkspace.created_at,
        updated_at: authoritativeWorkspace.updated_at,
      }]),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn().mockImplementation(async (_token, workspace, revision) => ({
        workspace_id: workspace.workspace_id,
        tenant_id: "tenant-enterprise",
        revision: revision + 1,
        document: workspace,
        document_hash: "b".repeat(64),
        created_by: "oidc-user-42",
        updated_by: "oidc-user-42",
        created_at: workspace.created_at,
        updated_at: workspace.updated_at,
      })),
      deleteWorkspace: vi.fn(),
    };
    const localStorageWrite = vi.spyOn(window.localStorage, "setItem");

    const { result } = renderHook(() => useWorkspaceStore({
      mode: "enterprise",
      authority,
      saveDebounceMs: 0,
    }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("ready"));
    expect(result.current.runtimeEvidence).toEqual({
      apiReachable: true,
      sessionVerified: true,
      persistenceVerified: true,
      auditVerified: true,
      retentionVerified: true,
      supportVerified: true,
      outboundPolicyVerified: true,
      backupRestoreVerified: true,
      workerVerified: true,
    });
    expect(result.current.state.current_user).toMatchObject({
      user_id: "oidc-user-42",
      role: "Approver",
      email: "approver@example.com",
    });
    expect(result.current.activeWorkspace?.workspace_id).toBe(authoritativeWorkspace.workspace_id);
    expect(localStorageWrite).not.toHaveBeenCalled();

    act(() => result.current.updateUseCase({ ...DEFAULT_WORKSPACE_USE_CASE, title: "Updated authoritative claim" }));

    await waitFor(() => expect(authority.updateWorkspace).toHaveBeenCalledWith(
      "enterprise-token",
      expect.objectContaining({ use_case: expect.objectContaining({ title: "Updated authoritative claim" }) }),
      7,
    ));
    await waitFor(() => expect(result.current.persistence).toMatchObject({ status: "saved", location: "authority" }));
    expect(localStorageWrite).not.toHaveBeenCalled();
  });

  it("surfaces authoritative revision conflicts without retrying stale state", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const authoritativeWorkspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const authority = {
      createSession: vi.fn().mockResolvedValue({
        access_token: "enterprise-token",
        token_type: "bearer",
        expires_in: 900,
        actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Operator", role: "Operator" },
      }),
      listWorkspaces: vi.fn().mockResolvedValue([{
        workspace_id: authoritativeWorkspace.workspace_id,
        tenant_id: "tenant-enterprise",
        revision: 2,
        document: authoritativeWorkspace,
        document_hash: "a".repeat(64),
        created_by: "oidc-user-42",
        updated_by: "oidc-user-42",
        created_at: authoritativeWorkspace.created_at,
        updated_at: authoritativeWorkspace.updated_at,
      }]),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn().mockRejectedValue(new AuthorityError("Workspace revision changed.", 409)),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({
      mode: "enterprise",
      authority,
      saveDebounceMs: 0,
    }));
    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("ready"));

    act(() => result.current.updateUseCase({ ...DEFAULT_WORKSPACE_USE_CASE, title: "Stale edit" }));

    await waitFor(() => expect(result.current.persistence).toMatchObject({
      status: "error",
      code: "authority_conflict",
      location: "authority",
    }));
    expect(authority.updateWorkspace).toHaveBeenCalledOnce();
  });
});
