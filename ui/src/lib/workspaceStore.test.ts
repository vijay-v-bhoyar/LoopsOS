import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthorityError, type AuthorityReadiness } from "../features/governedExecution/authorityClient";
import { evaluateDeploymentPosture } from "./deployment";
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
  runtimeEvidenceFromReadiness,
  useWorkspaceStore,
} from "./workspaceStore";

const HEALTHY_READINESS: AuthorityReadiness = {
  status: "ready",
  development_auth: false,
  rate_limit_configured: true,
  storage_backend: "postgres",
  production_identity: true,
  credential_injection_broker_verified: true,
  audit_anchor_configured: true,
  audit_anchor_backlog: 0,
  audit_anchor_delivery_verified: true,
  audit_anchor_delivery_fresh: true,
  audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
  execution_job_backlog: 0,
  execution_worker_dispatch: {
    verified: true,
    source: "external",
    observed_at: "2026-07-30T12:00:00+00:00",
    age_seconds: 5,
    detail: {},
  },
  operational_bindings: {
    retention_verified: true,
    support_verified: true,
    outbound_policy_verified: true,
    backup_restore_verified: true,
    worker_dispatch_verified: true,
  },
  configuration_contract: {
    allowed_http_hosts: ["api.example.com"],
    outbound_policy_mode: "allowlist",
    retention_policy_url: "https://policy.example.com/loopos-retention",
    support_contact: "loopos-operations@example.com",
    backup_restore_evidence_url: "https://evidence.example.com/loopos/restore.json",
  },
  backup_restore_evidence: {
    url: "https://evidence.example.com/loopos/restore.json",
    sha256: "a".repeat(64),
    verified_at: "2026-07-30T12:00:00+00:00",
  },
  operational_evidence: {
    url: "https://evidence.example.com/loopos/operational.json",
    sha256: "b".repeat(64),
    verified_at: "2026-07-30T12:00:00+00:00",
    binding_fingerprint: "c".repeat(64),
  },
};

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

  it("rejects malformed nested governance records from local storage", () => {
    const user = createUser("Vijay", "vijay@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    window.localStorage.setItem(
      "loopos.v2.workspace-state",
      JSON.stringify({
        current_user: user,
        active_workspace_id: workspace.workspace_id,
        workspaces: [{ ...workspace, approvals: [null] }],
      }),
    );

    const state = loadWorkspaceState();

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
        development_auth: false,
        rate_limit_configured: true,
        storage_backend: "postgres",
        production_identity: true,
        credential_injection_broker_verified: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 0,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: { claimed_jobs: 0 },
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://policy.example.com/loopos-retention",
          support_contact: "loopos-operations@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/loopos/restore.json",
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
      configurationVerified: true,
      credentialInjectionBrokerVerified: true,
      rateLimitVerified: true,
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

  it("does not restore enterprise state after sign-out while bootstrap is still pending", async () => {
    const localUser = createUser("Local", "local@example.local", "Operator");
    const authoritativeWorkspace = createWorkspace(localUser, "Pending claims", DEFAULT_WORKSPACE_USE_CASE);
    let resolveWorkspaces: ((records: unknown[]) => void) | undefined;
    const pendingWorkspaces = new Promise<unknown[]>((resolve) => { resolveWorkspaces = resolve; });
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue(HEALTHY_READINESS),
      createSession: vi.fn().mockResolvedValue({
        access_token: "enterprise-token",
        token_type: "bearer",
        expires_in: 900,
        actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Operator", role: "Operator" },
      }),
      listWorkspaces: vi.fn().mockReturnValue(pendingWorkspaces),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };
    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", authority }));

    await waitFor(() => expect(authority.listWorkspaces).toHaveBeenCalled());
    act(() => result.current.signOut());
    await act(async () => {
      resolveWorkspaces?.([{
        workspace_id: authoritativeWorkspace.workspace_id,
        tenant_id: "tenant-enterprise",
        revision: 1,
        document: authoritativeWorkspace,
        document_hash: "a".repeat(64),
        created_by: "oidc-user-42",
        updated_by: "oidc-user-42",
        created_at: authoritativeWorkspace.created_at,
        updated_at: authoritativeWorkspace.updated_at,
      }]);
      await Promise.resolve();
    });

    expect(result.current.enterpriseSession).toEqual({ status: "idle" });
    expect(result.current.state).toEqual({ current_user: null, active_workspace_id: null, workspaces: [] });
  });

  it("does not issue an enterprise session when authority readiness fails", async () => {
    const createSession = vi.fn();
    const authority = {
      checkReadiness: vi.fn().mockRejectedValue(new AuthorityError("Authority is not ready.", 503)),
      createSession,
      listWorkspaces: vi.fn(),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(createSession).not.toHaveBeenCalled();
    expect(result.current.enterpriseSession.error).toBe("Authority is not ready.");
    expect(result.current.enterpriseSession.retryable).toBe(true);
    expect(result.current.persistence).toMatchObject({
      status: "error",
      code: "authority_unavailable",
      location: "authority",
    });
    expect(result.current.runtimeEvidence).toMatchObject({
      apiReachable: true,
      sessionVerified: false,
      persistenceVerified: false,
      auditVerified: false,
      workerVerified: false,
    });
  });

  it("does not issue an enterprise session without a readiness verifier", async () => {
    const createSession = vi.fn();
    const authority = {
      createSession,
      listWorkspaces: vi.fn(),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(createSession).not.toHaveBeenCalled();
    expect(result.current.enterpriseSession.error).toBe("Enterprise readiness verification is unavailable.");
    expect(result.current.persistence).toMatchObject({
      status: "error",
      code: "authority_unavailable",
      location: "authority",
    });
  });

  it("does not issue an enterprise session when the authority contract mismatches the UI build", async () => {
    const createSession = vi.fn();
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue({
        status: "ready",
        development_auth: false,
        rate_limit_configured: true,
        storage_backend: "postgres",
        production_identity: true,
        credential_injection_broker_verified: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 0,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: {},
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://wrong.example/retention",
          support_contact: "loopos-operations@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/loopos/restore.json",
        },
        backup_restore_evidence: {
          url: "https://evidence.example.com/loopos/restore.json",
          sha256: "a".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
        },
        operational_evidence: {
          url: "https://evidence.example.com/loopos/operational.json",
          sha256: "b".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
          binding_fingerprint: "c".repeat(64),
        },
      }),
      createSession,
      listWorkspaces: vi.fn(),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };
    const posture = evaluateDeploymentPosture({
      VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise",
      VITE_LOOPOS_AUTHORITY_URL: "/api",
      VITE_LOOPOS_AUTH_MODE: "bff-session",
      VITE_LOOPOS_PERSISTENCE_MODE: "api",
      VITE_LOOPOS_AUDIT_MODE: "server",
      VITE_LOOPOS_CREDENTIAL_INJECTION_MODE: "broker",
      VITE_LOOPOS_RETENTION_POLICY_URL: "https://policy.example.com/retention",
      VITE_LOOPOS_SUPPORT_CONTACT: "loopos-operations@example.com",
      VITE_LOOPOS_OUTBOUND_POLICY_MODE: "allowlist",
      VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "api.example.com",
      VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL: "https://evidence.example.com/loopos/restore.json",
    });

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", posture, authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(createSession).not.toHaveBeenCalled();
    expect(result.current.enterpriseSession.error).toBe("Authority configuration does not match this UI build.");
    expect(result.current.enterpriseSession.retryable).toBe(false);
    expect(result.current.runtimeEvidence.configurationVerified).toBe(false);
  });

  it("fails closed when authority returns a workspace for a different tenant", async () => {
    const localUser = createUser("Local", "local@example.local", "Operator");
    const foreignWorkspace = createWorkspace(localUser, "Foreign workspace", DEFAULT_WORKSPACE_USE_CASE);
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue(HEALTHY_READINESS),
      createSession: vi.fn().mockResolvedValue({
        access_token: "enterprise-token",
        token_type: "bearer",
        expires_in: 900,
        actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Operator", role: "Operator" },
      }),
      listWorkspaces: vi.fn().mockResolvedValue([{
        workspace_id: foreignWorkspace.workspace_id,
        tenant_id: "tenant-other",
        revision: 1,
        document: foreignWorkspace,
        document_hash: "a".repeat(64),
        created_by: "other-user",
        updated_by: "other-user",
        created_at: foreignWorkspace.created_at,
        updated_at: foreignWorkspace.updated_at,
      }]),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(result.current.enterpriseSession.error).toBe("Authority returned a workspace for a different tenant.");
    expect(result.current.state).toEqual({ current_user: null, active_workspace_id: null, workspaces: [] });
    expect(result.current.runtimeEvidence.persistenceVerified).toBe(false);
  });

  it("does not mark persistence verified when the authenticated workspace list fails", async () => {
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue(HEALTHY_READINESS),
      createSession: vi.fn().mockResolvedValue({
        access_token: "enterprise-token",
        token_type: "bearer",
        expires_in: 900,
        actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Operator", role: "Operator" },
      }),
      listWorkspaces: vi.fn().mockRejectedValue(new AuthorityError("workspace list unavailable", 503)),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(result.current.runtimeEvidence.persistenceVerified).toBe(false);
    expect(result.current.persistence.location).toBe("authority");
  });

  it("does not treat stale audit delivery as verified runtime evidence", () => {
    const evidence = runtimeEvidenceFromReadiness({
      status: "ready",
      development_auth: false,
      rate_limit_configured: true,
      storage_backend: "postgres",
      production_identity: true,
      credential_injection_broker_verified: true,
      audit_anchor_configured: true,
      audit_anchor_backlog: 0,
      audit_anchor_delivery_verified: true,
      audit_anchor_delivery_fresh: false,
      audit_anchor_last_delivered_at: "2025-01-01T12:00:00+00:00",
      execution_job_backlog: 0,
      execution_worker_dispatch: {
        verified: true,
        source: "external",
        observed_at: "2026-07-30T12:00:00+00:00",
        age_seconds: 5,
        detail: {},
      },
      operational_bindings: {
        retention_verified: true,
        support_verified: true,
        outbound_policy_verified: true,
        backup_restore_verified: true,
        worker_dispatch_verified: true,
      },
      configuration_contract: {
        allowed_http_hosts: ["api.example.com"],
        outbound_policy_mode: "allowlist",
        retention_policy_url: "https://policy.example.com/loopos-retention",
        support_contact: "loopos-operations@example.com",
        backup_restore_evidence_url: "https://evidence.example.com/loopos/restore.json",
      },
      backup_restore_evidence: {
        url: "https://evidence.example.com/restore",
        sha256: "a".repeat(64),
        verified_at: "2026-07-30T12:00:00+00:00",
      },
      operational_evidence: {
        url: "https://evidence.example.com/operational",
        sha256: "b".repeat(64),
        verified_at: "2026-07-30T12:00:00+00:00",
        binding_fingerprint: "c".repeat(64),
      },
    });

    expect(evidence.auditVerified).toBe(false);
  });

  it("does not issue an enterprise session when a 200 readiness proof has a backlog", async () => {
    const createSession = vi.fn();
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue({
        status: "ready",
        development_auth: false,
        rate_limit_configured: true,
        storage_backend: "postgres",
        production_identity: true,
        credential_injection_broker_verified: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 1,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: {},
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://policy.example.com/loopos-retention",
          support_contact: "loopos-operations@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/loopos/restore.json",
        },
        backup_restore_evidence: {
          url: "https://evidence.example.com/loopos/restore.json",
          sha256: "a".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
        },
        operational_evidence: {
          url: "https://evidence.example.com/loopos/operational.json",
          sha256: "b".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
          binding_fingerprint: "c".repeat(64),
        },
      }),
      createSession,
      listWorkspaces: vi.fn(),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(createSession).not.toHaveBeenCalled();
    expect(result.current.enterpriseSession.error).toContain("execution_job_backlog");
  });

  it("surfaces authoritative revision conflicts without retrying stale state", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const authoritativeWorkspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue(HEALTHY_READINESS),
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

  it("retries a transient authoritative save when explicitly requested", async () => {
    const user = createUser("Operator", "operator@example.com", "Operator");
    const authoritativeWorkspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const updateWorkspace = vi.fn()
      .mockRejectedValueOnce(new AuthorityError("Authority temporarily unavailable.", 503))
      .mockImplementation(async (_token, workspace, revision) => ({
        workspace_id: workspace.workspace_id,
        tenant_id: "tenant-enterprise",
        revision: revision + 1,
        document: workspace,
        document_hash: "b".repeat(64),
        created_by: "oidc-user-42",
        updated_by: "oidc-user-42",
        created_at: workspace.created_at,
        updated_at: workspace.updated_at,
      }));
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue(HEALTHY_READINESS),
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
      updateWorkspace,
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({
      mode: "enterprise",
      authority,
      saveDebounceMs: 0,
    }));
    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("ready"));

    act(() => result.current.updateUseCase({ ...DEFAULT_WORKSPACE_USE_CASE, title: "Retryable edit" }));
    await waitFor(() => expect(result.current.persistence).toMatchObject({
      status: "error",
      code: "authority_unavailable",
      location: "authority",
    }));

    act(() => result.current.retryPersistence());
    await waitFor(() => expect(result.current.persistence).toMatchObject({ status: "saved", location: "authority" }));
    expect(updateWorkspace).toHaveBeenCalledTimes(2);
  });

  it("expires the verified session when authoritative persistence returns 401", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const authoritativeWorkspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const authority = {
      checkReadiness: vi.fn().mockResolvedValue(HEALTHY_READINESS),
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
      updateWorkspace: vi.fn().mockRejectedValue(new AuthorityError("Session expired.", 401)),
      deleteWorkspace: vi.fn(),
    };

    const { result } = renderHook(() => useWorkspaceStore({
      mode: "enterprise",
      authority,
      saveDebounceMs: 0,
    }));
    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("ready"));

    act(() => result.current.updateUseCase({ ...DEFAULT_WORKSPACE_USE_CASE, title: "Expired session edit" }));

    await waitFor(() => expect(result.current.persistence).toMatchObject({
      status: "error",
      code: "authority_unauthorized",
      message: "The enterprise identity session expired. Re-verify before saving.",
      location: "authority",
    }));
    expect(result.current.enterpriseSession).toEqual({
      status: "error",
      error: "The enterprise identity session expired. Re-verify before saving.",
      retryable: true,
    });
    expect(result.current.runtimeEvidence.sessionVerified).toBe(false);
    expect(authority.updateWorkspace).toHaveBeenCalledOnce();
  });

  it("does not bootstrap the authority when static enterprise bindings are blocked", async () => {
    const authority = {
      checkReadiness: vi.fn(),
      createSession: vi.fn(),
      listWorkspaces: vi.fn(),
      createWorkspace: vi.fn(),
      updateWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };
    const blockedPosture = evaluateDeploymentPosture({
      VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise",
      VITE_LOOPOS_AUTHORITY_URL: "//untrusted.example/api",
    });

    const { result } = renderHook(() => useWorkspaceStore({ mode: "enterprise", posture: blockedPosture, authority }));

    await waitFor(() => expect(result.current.enterpriseSession.status).toBe("error"));
    expect(authority.checkReadiness).not.toHaveBeenCalled();
    expect(authority.createSession).not.toHaveBeenCalled();
    expect(result.current.enterpriseSession.retryable).toBe(false);
    expect(result.current.persistence).toMatchObject({
      status: "error",
      location: "authority",
    });
  });
});
