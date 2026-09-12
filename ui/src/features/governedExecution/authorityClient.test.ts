import { beforeEach, describe, expect, it, vi } from "vitest";
import { buildConnectorEventsForRelease, buildReleaseInitiativeRecord, buildWorkspaceExecutionPlan } from "./types";
import { createReleaseAssuranceProfile } from "../../lib/releaseAssurance";
import { createUser, createWorkspace, DEFAULT_WORKSPACE_USE_CASE } from "../../lib/workspaceStore";
import {
  AuthorityError,
  approveGovernedRun,
  createAuthoritySession,
  createAuthorityWorkspace,
  createDevelopmentSession,
  createEnterpriseSession,
  createReleaseInitiative,
  deleteAuthorityWorkspace,
  getReleaseProofPack,
  getAuthorityReadiness,
  listGovernedRuns,
  listAuthorityWorkspaces,
  listConnectorEvents,
  listReleaseInitiatives,
  recordReleaseInitiative,
  recordConnectorEvent,
  rejectGovernedRun,
  rollbackGovernedRun,
  resolveAuthorityBase,
  startGovernedRun,
  streamGovernedRun,
  updateAuthorityWorkspace,
  verifyAuthorityAudit,
} from "./authorityClient";
import { looposData } from "../../lib/loopos";
import type { InitiativeWorkspace } from "../../types";
import type { GovernedRun } from "./types";

describe("authorityClient", () => {
  beforeEach(() => vi.restoreAllMocks());

  function completeReadinessPayload(): Record<string, unknown> {
    return {
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
        retention_policy_url: "https://evidence.example.com/loopos/retention",
        support_contact: "loopos-operations@example.com",
        backup_restore_evidence_url: "https://evidence.example.com/loopos/postgres-restore.json",
      },
      backup_restore_evidence: {
        url: "https://evidence.example.com/loopos/postgres-restore.json",
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
  }

  it("builds an evidence-bearing plan with validation and effectiveness probes", () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const input = buildWorkspaceExecutionPlan(workspace, "loop-001-product-discovery-loop", "Product Discovery Loop", "R1");

    expect(input.plan.evidence).toHaveLength(1);
    expect(input.plan.action.tool).toBe("record_action");
    expect(input.plan.validation_probes).toHaveLength(1);
    expect(input.plan.effectiveness_probes).toHaveLength(1);
    expect(input.plan.action.idempotency_key).toMatch(/^action-/);
    expect(input.plan.enterprise_context).toBeNull();
  });

  it("adds enterprise runtime context for high-risk governed runs", () => {
    const user = createUser("Approver", "approver@example.local", "Approver");
    const workspace = createWorkspace(user, "Agent guardrails", DEFAULT_WORKSPACE_USE_CASE);
    const input = buildWorkspaceExecutionPlan(workspace, "loop-079-agent-guardrail-loop", "Agent Guardrail Loop", "R3");

    expect(input.plan.enterprise_context).toEqual(expect.objectContaining({
      sandbox_profile_ref: "sandbox-e2b-firecracker-production",
      idempotency_scope: "tenant_workflow_tool_payload",
      evidence_refs: ["workspace-snapshot"],
    }));
  });

  it("keeps authority traffic on the same origin or an explicit enterprise allowlist", () => {
    expect(resolveAuthorityBase("/api", [], "http://localhost/")).toBe("/api");
    expect(resolveAuthorityBase("https://authority.example.com/api", ["authority.example.com"], "https://console.example.com/")).toBe("https://authority.example.com/api");
    expect(() => resolveAuthorityBase("https://unapproved.example/api", [], "https://console.example.com/")).toThrow(/allowlist/);
    expect(() => resolveAuthorityBase("https://authority.example.com/api?token=secret", ["authority.example.com"], "https://console.example.com/")).toThrow(/query strings/);
  });

  it("rejects an unapproved enterprise authority before sending a request", async () => {
    vi.stubEnv("VITE_LOOPOS_DEPLOYMENT_MODE", "enterprise");
    vi.stubEnv("VITE_LOOPOS_AUTH_MODE", "bff-session");
    vi.stubEnv("VITE_LOOPOS_AUTHORITY_URL", "https://unapproved.example/api");
    vi.stubEnv("VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS", "");
    vi.resetModules();
    const client = await import("./authorityClient");
    const fetchImpl = vi.spyOn(globalThis, "fetch");

    await expect(client.createEnterpriseSession()).rejects.toThrow(/allowlist/);
    expect(fetchImpl).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("creates an explicit development authority session without persisting the token", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ access_token: "token", token_type: "bearer", expires_in: 3600, actor: { tenant_id: "local-evaluation", user_id: "user", name: "Operator", role: "Operator" } }), { status: 200, headers: { "content-type": "application/json" } }));
    const user = createUser("Operator", "operator@example.local", "Operator");
    const session = await createDevelopmentSession(user);

    expect(session.access_token).toBe("token");
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/dev/sessions", expect.objectContaining({
      credentials: "omit",
      redirect: "error",
      headers: expect.objectContaining({ "x-request-id": expect.stringMatching(/^ui-/) }),
    }));
    expect(window.localStorage.length).toBe(0);
  });

  it("retains the server correlation ID on authority failures", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Authority unavailable." }), {
      status: 503,
      headers: { "content-type": "application/json", "x-request-id": "request-support-42" },
    }));

    const error = await getAuthorityReadiness().catch((value) => value);

    expect(error).toBeInstanceOf(AuthorityError);
    expect((error as AuthorityError).status).toBe(503);
    expect((error as AuthorityError).requestId).toBe("request-support-42");
  });

  it("exchanges managed identity credentials for an enterprise session", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
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
    }), { status: 200, headers: { "content-type": "application/json" } }));

    const session = await createEnterpriseSession();

    expect(session.actor.tenant_id).toBe("tenant-enterprise");
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/sessions", expect.objectContaining({
      method: "POST",
      credentials: "include",
      redirect: "error",
    }));
  });

  it("times out when an authority JSON response stalls after headers", async () => {
    vi.useFakeTimers();
    try {
      const stream = new ReadableStream({
        pull() {
          return new Promise<void>(() => undefined);
        },
      });
      vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "application/json" } }));
      const pending = listGovernedRuns("token", "workspace-stalled", "tenant-1").catch((error) => error);

      await vi.advanceTimersByTimeAsync(15_001);
      await expect(pending).resolves.toMatchObject({ message: "Authority request timed out after 15000 ms." });
    } finally {
      vi.useRealTimers();
    }
  });

  it("rejects malformed authority session claims instead of trusting a type cast", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      access_token: "enterprise-token",
      token_type: "bearer",
      expires_in: 900,
      actor: {
        tenant_id: "tenant-enterprise",
        user_id: "oidc-user-42",
        name: "Enterprise Approver",
        role: "Administrator",
      },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(createEnterpriseSession()).rejects.toThrow("invalid session response");
  });

  it("rejects a non-positive or non-string session credential", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      access_token: 42,
      token_type: "bearer",
      expires_in: 0,
      actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Operator", role: "Operator" },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(createEnterpriseSession()).rejects.toThrow("invalid session response");
  });

  it("rejects an authority session with an excessive lifetime", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      access_token: "enterprise-token",
      token_type: "bearer",
      expires_in: 901,
      actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Operator", role: "Operator" },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(createEnterpriseSession()).rejects.toThrow("invalid session response");
  });

  it("selects the secure session bootstrap for enterprise mode", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      access_token: "enterprise-token",
      token_type: "bearer",
      expires_in: 900,
      actor: { tenant_id: "tenant-enterprise", user_id: "oidc-user-42", name: "Approver", role: "Approver" },
    }), { status: 200, headers: { "content-type": "application/json" } }));
    const user = createUser("Ignored local user", "ignored@example.local", "Operator");

    await createAuthoritySession(user, "enterprise");

    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/sessions", expect.objectContaining({ credentials: "include" }));
  });

  it("reads fail-closed runtime evidence from the authority readiness endpoint", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
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
        backup_restore_evidence_url: "https://evidence.example.com/loopos/postgres-restore.json",
      },
      backup_restore_evidence: {
        url: "https://evidence.example.com/loopos/postgres-restore.json",
        sha256: "a".repeat(64),
        verified_at: "2026-07-30T12:00:00+00:00",
      },
      operational_evidence: {
        url: "https://evidence.example.com/loopos/operational.json",
        sha256: "b".repeat(64),
        verified_at: "2026-07-30T12:00:00+00:00",
        binding_fingerprint: "c".repeat(64),
      },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    const readiness = await getAuthorityReadiness();

    expect(readiness).toMatchObject({
      storage_backend: "postgres",
      production_identity: true,
      audit_anchor_configured: true,
      audit_anchor_backlog: 0,
      audit_anchor_delivery_verified: true,
      audit_anchor_delivery_fresh: true,
      execution_worker_dispatch: expect.objectContaining({ verified: true, source: "external" }),
      operational_bindings: expect.objectContaining({ backup_restore_verified: true }),
      backup_restore_evidence: expect.objectContaining({ sha256: "a".repeat(64) }),
    });
    expect(fetchImpl).toHaveBeenCalledWith("/api/health/ready", expect.objectContaining({
      credentials: "omit",
      cache: "no-store",
    }));
  });

  it.each(["execution_job_backlog", "operational_evidence"])(
    "rejects readiness proof missing %s",
    async (field) => {
      const payload = completeReadinessPayload();
      delete payload[field];
      vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));

      await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
    },
  );

  it.each([
    ["development_auth", true],
    ["production_identity", false],
    ["audit_anchor_backlog", 1],
    ["execution_job_backlog", 1],
  ])("rejects a structurally valid but incomplete production readiness proof for %s", async (field, value) => {
    const payload = completeReadinessPayload();
    payload[field] = value;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
  });

  it("rejects malformed readiness evidence instead of trusting a type cast", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      status: "ready",
      storage_backend: "postgres",
      production_identity: "true",
      audit_anchor_configured: true,
      audit_anchor_backlog: 0,
      audit_anchor_delivery_verified: true,
      audit_anchor_delivery_fresh: true,
      audit_anchor_last_delivered_at: null,
      execution_worker_dispatch: {
        verified: true,
        source: "external",
        observed_at: null,
        age_seconds: 0,
        detail: {},
      },
      operational_bindings: {
        retention_verified: true,
        support_verified: true,
        outbound_policy_verified: true,
        backup_restore_verified: true,
        worker_dispatch_verified: true,
      },
      backup_restore_evidence: { url: null, sha256: null, verified_at: null },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
  });

  it.each([
    ["audit_anchor_last_delivered_at", (payload: Record<string, unknown>) => { payload.audit_anchor_last_delivered_at = "not-a-timestamp"; }],
    ["worker_observed_at", (payload: Record<string, unknown>) => {
      payload.execution_worker_dispatch = {
        ...(payload.execution_worker_dispatch as Record<string, unknown>),
        observed_at: "not-a-timestamp",
      };
    }],
    ["restore_verified_at", (payload: Record<string, unknown>) => {
      payload.backup_restore_evidence = {
        ...(payload.backup_restore_evidence as Record<string, unknown>),
        verified_at: "not-a-timestamp",
      };
    }],
    ["operational_verified_at", (payload: Record<string, unknown>) => {
      payload.operational_evidence = {
        ...(payload.operational_evidence as Record<string, unknown>),
        verified_at: "not-a-timestamp",
      };
    }],
  ])("rejects readiness proof with an invalid %s timestamp", async (_field, mutate) => {
    const payload = completeReadinessPayload();
    mutate(payload);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
  });

  it.each([
    ["restore evidence", (payload: Record<string, unknown>) => {
      payload.backup_restore_evidence = {
        ...(payload.backup_restore_evidence as Record<string, unknown>),
        url: "https://user:password@evidence.example.com/restore.json",
      };
    }],
    ["operational evidence", (payload: Record<string, unknown>) => {
      payload.operational_evidence = {
        ...(payload.operational_evidence as Record<string, unknown>),
        url: "https://evidence.example.com/operational.json?token=secret",
      };
    }],
    ["retention policy", (payload: Record<string, unknown>) => {
      payload.configuration_contract = {
        ...(payload.configuration_contract as Record<string, unknown>),
        retention_policy_url: "http://policy.example.com/retention",
      };
    }],
    ["restore contract", (payload: Record<string, unknown>) => {
      payload.configuration_contract = {
        ...(payload.configuration_contract as Record<string, unknown>),
        backup_restore_evidence_url: "https://evidence.example.com/restore.json#fragment",
      };
    }],
  ])("rejects readiness proof with an unsafe %s URL", async (_field, mutate) => {
    const payload = completeReadinessPayload();
    mutate(payload);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
  });

  it.each([
    "https://127.0.0.1/restore.json",
    "https://100.64.0.1/restore.json",
  ])("rejects readiness proof with a non-global evidence host: %s", async (url) => {
    const payload = completeReadinessPayload();
    payload.backup_restore_evidence = {
      ...(payload.backup_restore_evidence as Record<string, unknown>),
      url,
    };
    payload.configuration_contract = {
      ...(payload.configuration_contract as Record<string, unknown>),
      backup_restore_evidence_url: url,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
  });

  it("rejects a verified worker proof without a timestamped observation and age", async () => {
    const payload = completeReadinessPayload();
    payload.execution_worker_dispatch = {
      ...(payload.execution_worker_dispatch as Record<string, unknown>),
      source: null,
      observed_at: null,
      age_seconds: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(getAuthorityReadiness()).rejects.toThrow("invalid readiness response");
  });

  it("normalizes non-object authority errors without throwing a parser error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("null", { status: 503 }));

    await expect(getAuthorityReadiness()).rejects.toMatchObject({
      message: "Authority returned 503.",
      status: 503,
    });
  });

  it("lists tenant-scoped authoritative workspace documents", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([{
      workspace_id: workspace.workspace_id,
      tenant_id: "tenant-enterprise",
      revision: 3,
      document: workspace,
      document_hash: "a".repeat(64),
      created_by: "oidc-user-42",
      updated_by: "oidc-user-42",
      created_at: workspace.created_at,
      updated_at: workspace.updated_at,
    }]), { status: 200, headers: { "content-type": "application/json" } }));

    const records = await listAuthorityWorkspaces("enterprise-token");

    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({ revision: 3, document: { workspace_id: workspace.workspace_id } });
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/workspaces", expect.objectContaining({
      headers: expect.objectContaining({ authorization: "Bearer enterprise-token" }),
    }));
  });

  it("rejects malformed or cross-workspace authoritative workspace records", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const responseRecord = {
      workspace_id: workspace.workspace_id,
      tenant_id: "tenant-enterprise",
      revision: 1,
      document: workspace,
      document_hash: "a".repeat(64),
      created_by: "oidc-user-42",
      updated_by: "oidc-user-42",
      created_at: workspace.created_at,
      updated_at: workspace.updated_at,
    };
    const fetchImpl = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([{ ...responseRecord, workspace_id: "workspace-other" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...responseRecord, document_hash: "not-a-sha256" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...responseRecord, document: { ...workspace, workspace_id: "workspace-other" } }), { status: 200 }));

    await expect(listAuthorityWorkspaces("enterprise-token")).rejects.toThrow("invalid workspace data");
    await expect(createAuthorityWorkspace("enterprise-token", workspace)).rejects.toThrow("invalid workspace data");
    await expect(updateAuthorityWorkspace("enterprise-token", workspace, 1)).rejects.toThrow("invalid workspace data");
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("rejects malformed nested authoritative workspace documents", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const responseRecord = {
      workspace_id: workspace.workspace_id,
      tenant_id: "tenant-enterprise",
      revision: 1,
      document: { ...workspace, approvals: [null] },
      document_hash: "a".repeat(64),
      created_by: "oidc-user-42",
      updated_by: "oidc-user-42",
      created_at: workspace.created_at,
      updated_at: workspace.updated_at,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([responseRecord]), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(listAuthorityWorkspaces("enterprise-token")).rejects.toThrow("invalid workspace data");
  });

  it("uses create-only and revision preconditions for authoritative writes", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const responseRecord = {
      workspace_id: workspace.workspace_id,
      tenant_id: "tenant-enterprise",
      revision: 1,
      document: workspace,
      document_hash: "a".repeat(64),
      created_by: "oidc-user-42",
      updated_by: "oidc-user-42",
      created_at: workspace.created_at,
      updated_at: workspace.updated_at,
    };
    const fetchImpl = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(responseRecord), { status: 201, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...responseRecord, revision: 2 }), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await createAuthorityWorkspace("enterprise-token", workspace);
    await updateAuthorityWorkspace("enterprise-token", workspace, 1);
    await deleteAuthorityWorkspace("enterprise-token", workspace.workspace_id, 2);

    expect(fetchImpl).toHaveBeenNthCalledWith(1, `/api/v1/workspaces/${workspace.workspace_id}`, expect.objectContaining({
      method: "PUT",
      headers: expect.objectContaining({ "if-none-match": "*" }),
    }));
    expect(fetchImpl).toHaveBeenNthCalledWith(2, `/api/v1/workspaces/${workspace.workspace_id}`, expect.objectContaining({
      method: "PUT",
      headers: expect.objectContaining({ "if-match": "\"1\"" }),
    }));
    expect(fetchImpl).toHaveBeenNthCalledWith(3, `/api/v1/workspaces/${workspace.workspace_id}`, expect.objectContaining({
      method: "DELETE",
      headers: expect.objectContaining({ "if-match": "\"2\"" }),
    }));
  });

  it("validates governed command acknowledgements and requires a 204 workspace delete", async () => {
    const user = createUser("Approver", "approver@example.local", "Approver");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const input = buildWorkspaceExecutionPlan(workspace, "loop-001-product-discovery-loop", "Product Discovery Loop", "R1");
    const run = {
      ...input,
      run_id: "run-command-contract",
      tenant_id: "local-evaluation",
      state: "PLANNED",
      runner_status: "awaiting_approval",
      risk_tier: input.requested_risk_tier,
      requires_approval: true,
      payload_hash: "a".repeat(64),
      attempt: 0,
      created_by: user.user_id,
      created_at: "2026-07-23T12:00:00.000Z",
      updated_at: "2026-07-23T12:00:00.000Z",
    } as GovernedRun;
    const fetchImpl = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: run.run_id, state: "PLANNED", runner_status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ approval_id: "approval-1", status: "approved" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ decision_id: "decision-1", status: "rejected" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: run.run_id, state: "ROLLED_BACK", runner_status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(startGovernedRun("token", run.run_id)).resolves.toMatchObject({ run_id: run.run_id, runner_status: "queued" });
    await expect(approveGovernedRun("token", run, "approved for contract test")).resolves.toEqual({ approval_id: "approval-1", status: "approved" });
    await expect(rejectGovernedRun("token", run, "rejected for contract test")).resolves.toEqual({ decision_id: "decision-1", status: "rejected" });
    await expect(rollbackGovernedRun("token", run.run_id)).resolves.toMatchObject({ run_id: run.run_id, state: "ROLLED_BACK" });
    await expect(deleteAuthorityWorkspace("token", workspace.workspace_id, 3)).resolves.toBeUndefined();

    expect(fetchImpl).toHaveBeenCalledTimes(5);

    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: "other-run", state: "QUEUED", runner_status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "approved" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ decision_id: "decision-1", status: "approved" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: run.run_id, state: "ROLLED_BACK" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ deleted: true }), { status: 200 }));

    await expect(startGovernedRun("token", run.run_id)).rejects.toThrow("invalid start response");
    await expect(approveGovernedRun("token", run, "approved for contract test")).rejects.toThrow("invalid approval response");
    await expect(rejectGovernedRun("token", run, "rejected for contract test")).rejects.toThrow("invalid rejection response");
    await expect(rollbackGovernedRun("token", run.run_id)).rejects.toThrow("invalid rollback response");
    await expect(deleteAuthorityWorkspace("token", workspace.workspace_id, 3)).rejects.toThrow("invalid delete response");
  });

  it("rejects governed responses with unknown lifecycle states", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: "run-contract", state: "UNKNOWN", runner_status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: "run-contract", state: "PLANNED", runner_status: "unknown" }), { status: 202 }));

    await expect(startGovernedRun("token", "run-contract")).rejects.toThrow("invalid start response");
    await expect(startGovernedRun("token", "run-contract")).rejects.toThrow("invalid start response");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("retains the server correlation ID for no-content mutation failures", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Workspace conflict." }), {
      status: 409,
      headers: { "content-type": "application/json", "x-request-id": "request-delete-17" },
    }));

    const error = await deleteAuthorityWorkspace("token", "workspace-authoritative", 4).catch((value) => value);

    expect(error).toBeInstanceOf(AuthorityError);
    expect((error as AuthorityError).status).toBe(409);
    expect((error as AuthorityError).requestId).toBe("request-delete-17");
  });

  it("surfaces optimistic concurrency conflicts without overwriting authority state", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Workspace revision changed." }), {
      status: 409,
      headers: { "content-type": "application/json" },
    }));

    await expect(updateAuthorityWorkspace("enterprise-token", workspace, 4)).rejects.toEqual(
      expect.objectContaining<Partial<AuthorityError>>({ status: 409, message: "Workspace revision changed." }),
    );
  });

  it("rejects malformed or cross-workspace governed run responses", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const input = buildWorkspaceExecutionPlan(workspace, "loop-001-product-discovery-loop", "Product Discovery Loop", "R1");
    const run = {
      ...input,
      run_id: "run-authority",
      tenant_id: "local-evaluation",
      state: "PLANNED",
      runner_status: "awaiting_approval",
      risk_tier: input.requested_risk_tier,
      requires_approval: false,
      payload_hash: "a".repeat(64),
      attempt: 0,
      created_by: user.user_id,
      created_at: "2026-07-23T12:00:00.000Z",
      updated_at: "2026-07-23T12:00:00.000Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([
      run,
      { ...run, workspace_id: "workspace-other" },
    ]), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(listGovernedRuns("token", workspace.workspace_id, "local-evaluation")).rejects.toThrow("invalid governed run data");
  });

  it("rejects malformed or cross-workspace release evidence responses", async () => {
    const validEvent = {
      connector_event_id: "connector-event-1",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      system: "github",
      event_kind: "pull_request",
      external_id: "pr-1",
      label: "Release pull request",
      url: null,
      observed_at: "2026-07-23T12:00:00.000Z",
      payload_hash: "a".repeat(64),
      payload: { state: "open" },
      verification_status: "session_authenticated",
      delivery_id: null,
      created_by: "user-1",
      created_at: "2026-07-23T12:00:00.000Z",
    };
    const fetchImpl = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([{ ...validEvent, workspace_id: "workspace-other" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ ...validEvent, release_assurance: {} }]), { status: 200 }));

    await expect(listConnectorEvents("token", "workspace-release", "local-evaluation")).rejects.toThrow("invalid connector event data");
    await expect(listReleaseInitiatives("token", "workspace-release", "local-evaluation")).rejects.toThrow("invalid release initiative data");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("rejects release initiatives with malformed nested assurance records", async () => {
    const payload = {
      initiative_id: "initiative-authority",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      title: "Release readiness",
      description: "Release evidence",
      workflow_type: "release",
      business_outcome: "Safer releases",
      maturity: "pilot",
      risk_tier: "R3",
      status: "planned",
      release_name: "Release 2026.08",
      loop_bundle_ids: [],
      source_event_ids: [],
      release_assurance: {
        profile_id: "profile-release",
        initiative_id: "initiative-authority",
        release_name: "Release 2026.08",
        operating_mode: "shadow_release",
        connectors: [],
        external_refs: [],
        gates: [null],
        evidence_artifacts: [],
        decisions: [],
        exceptions: [],
        metric_observations: [],
        proof_pack_scope: [],
      },
      freshness_summary: { status: "fresh" },
      readiness_verdict: { verdict: "NO_GO" },
      created_by: "user-1",
      created_at: "2026-07-23T12:00:00.000Z",
      updated_at: "2026-07-23T12:00:00.000Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([payload]), { status: 200 }));

    await expect(listReleaseInitiatives("token", "workspace-release", "local-evaluation")).rejects.toThrow("invalid release initiative data");
  });

  it("rejects malformed audit verification responses instead of trusting a type cast", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      tenant_id: "local-evaluation",
      valid: "true",
      event_count: 2,
      first_invalid_sequence: null,
    }), { status: 200 }));

    await expect(verifyAuthorityAudit("token")).rejects.toThrow("invalid audit verification data");
  });

  it("builds and posts an atomic release assurance initiative record", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Release", {
      ...DEFAULT_WORKSPACE_USE_CASE,
      title: "Prepare release 2026.08",
      description: "Govern a production release with Jira and GitHub evidence.",
    });
    const initiative: InitiativeWorkspace = {
      id: "initiative-release",
      title: workspace.use_case.title,
      description: workspace.use_case.description,
      workflow_type: "release",
      business_outcome: workspace.use_case.businessOutcome,
      maturity: workspace.use_case.maturity,
      risk: "R3",
      status: "planned",
      created_at: "2026-07-23T12:00:00.000Z",
      updated_at: "2026-07-23T12:00:00.000Z",
      loop_bundle_ids: ["loop-036-release-readiness-loop", "loop-038-deployment-validation-loop"],
      execution_records: [],
      evidence_records: [],
      approvals: [],
      handoffs: [],
      roi_assumptions: {
        initiative_id: "initiative-release",
        meetings_avoided: 1,
        review_cycles_reduced: 1,
        evidence_items_reused: 1,
        hours_saved_estimate: 3,
        assumptions: "test",
        confidence_basis: "recorded facts",
      },
    };
    initiative.release_assurance = createReleaseAssuranceProfile(workspace, initiative, looposData, user.name, "2026-07-23T12:00:00.000Z");
    const connectorInput = buildConnectorEventsForRelease(workspace, initiative)[0];
    expect(connectorInput.verification_status).toBe("session_authenticated");
    expect(connectorInput.payload.trust_boundary).toBe("shadow evidence only; governed write-back requires separate authority action");
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockImplementationOnce(async (_url, init) => {
      const body = JSON.parse(String(init?.body)) as { initiative: ReturnType<typeof buildReleaseInitiativeRecord>; connector_events: Array<typeof connectorInput> };
      const event = { ...body.connector_events[0], connector_event_id: "connector-event-1", tenant_id: "local-evaluation", url: body.connector_events[0].url ?? null, delivery_id: body.connector_events[0].delivery_id ?? null, payload_hash: "a".repeat(64), verification_status: "session_authenticated", created_by: user.user_id, created_at: "2026-07-23T12:00:00.000Z" };
      const record = { ...body.initiative, initiative_id: "initiative-authority", tenant_id: "local-evaluation", source_event_ids: [event.connector_event_id], freshness_summary: { status: "fresh", source_event_count: 1 }, readiness_verdict: { verdict: "NO_GO", failing_reasons: ["release gate blocked"] }, created_by: user.user_id, created_at: "2026-07-23T12:00:00.000Z", updated_at: "2026-07-23T12:00:00.000Z" };
      return new Response(JSON.stringify({ initiative: record, connector_events: [event] }), { status: 201, headers: { "content-type": "application/json" } });
    });

    const response = await recordReleaseInitiative("token", buildReleaseInitiativeRecord(workspace, initiative), [connectorInput], "local-evaluation");
    const record = response.initiative;

    expect(record.initiative_id).toBe("initiative-authority");
    expect(record.source_event_ids).toEqual(["connector-event-1"]);
    expect(record.release_assurance.gates.length).toBeGreaterThan(0);
    expect(record.freshness_summary?.status).toBe("fresh");
    expect(record.readiness_verdict?.verdict).toBe("NO_GO");
    expect(response.connector_events).toHaveLength(1);
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/release-initiatives/record", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ authorization: "Bearer token", "idempotency-key": expect.stringContaining("release-") }),
    }));
  });

  it("parses streamed audit events and stops at an authority release boundary", async () => {
    const encoder = new TextEncoder();
    const event = (sequence: number, eventType: string, payload: Record<string, unknown>) => JSON.stringify({
      sequence,
      event_id: `event-${sequence}`,
      tenant_id: "tenant-1",
      run_id: "run-1",
      event_type: eventType,
      state: null,
      actor_id: "user-1",
      created_at: "2026-07-23T12:00:00.000Z",
      event_hash: "a".repeat(64),
      previous_hash: "b".repeat(64),
      payload,
    });
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`id: 1\nevent: RUN_CREATED\ndata: ${event(1, "RUN_CREATED", {})}\n\n`));
        controller.enqueue(encoder.encode(`id: 2\nevent: RUN_RELEASED\ndata: ${event(2, "RUN_RELEASED", { runner_status: "completed" })}\n\n`));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const events: string[] = [];
    await streamGovernedRun("token", "run-1", "tenant-1", (event) => events.push(event.event_type), undefined, 7);
    expect(events).toEqual(["RUN_CREATED", "RUN_RELEASED"]);
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("after=7"), expect.any(Object));
  });

  it("parses CRLF event frames when transport chunks split the delimiter", async () => {
    const encoder = new TextEncoder();
    const event = (sequence: number, eventType: string) => JSON.stringify({
      sequence,
      event_id: `event-${sequence}`,
      tenant_id: "tenant-1",
      run_id: "run-crlf",
      event_type: eventType,
      state: null,
      actor_id: "user-1",
      created_at: "2026-07-23T12:00:00.000Z",
      event_hash: "a".repeat(64),
      previous_hash: "b".repeat(64),
      payload: eventType === "RUN_RELEASED" ? { runner_status: "completed" } : {},
    });
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`id: 3\r\nevent: RUN_CREATED\r\ndata: ${event(3, "RUN_CREATED")}\r`));
        controller.enqueue(encoder.encode('\n\r\n' + `id: 4\r\nevent: RUN_RELEASED\r\ndata: ${event(4, "RUN_RELEASED")}\r\n\r\n`));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const events: string[] = [];
    await streamGovernedRun("token", "run-crlf", "tenant-1", (event) => events.push(event.event_type));
    expect(events).toEqual(["RUN_CREATED", "RUN_RELEASED"]);
  });

  it("flushes a complete final event when the stream closes without a blank line", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`id: 5\nevent: RUN_CREATED\ndata: ${JSON.stringify({
          sequence: 5,
          event_id: "event-5",
          tenant_id: "tenant-1",
          run_id: "run-final",
          event_type: "RUN_CREATED",
          state: null,
          actor_id: "user-1",
          created_at: "2026-07-23T12:00:00.000Z",
          event_hash: "a".repeat(64),
          previous_hash: "b".repeat(64),
          payload: {},
        })}`));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const events: string[] = [];
    await streamGovernedRun("token", "run-final", "tenant-1", (event) => events.push(event.event_type));
    expect(events).toEqual(["RUN_CREATED"]);
  });

  it("rejects malformed or cross-run audit events before exposing them to the panel", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"sequence":1,"event_id":"event-1","tenant_id":"tenant-1","run_id":"other-run","event_type":"RUN_CREATED","state":null,"actor_id":"user-1","created_at":"2026-07-23T12:00:00.000Z","event_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","previous_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","payload":{}}\n\n'));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const onEvent = vi.fn();

    await expect(streamGovernedRun("token", "run-expected", "tenant-1", onEvent)).rejects.toThrow("invalid audit event");
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("rejects streamed audit events from another tenant before exposing them to the panel", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"sequence":1,"event_id":"event-1","tenant_id":"tenant-other","run_id":"run-expected","event_type":"RUN_CREATED","state":null,"actor_id":"user-1","created_at":"2026-07-23T12:00:00.000Z","event_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","previous_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","payload":{}}\n\n'));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));

    await expect(streamGovernedRun("token", "run-expected", "tenant-primary", () => undefined)).rejects.toThrow("invalid audit event");
  });

  it("rejects a successful non-SSE response instead of treating it as an empty stream", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "proxy response" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(streamGovernedRun("token", "run-expected", "tenant-1", () => undefined)).rejects.toThrow("non-SSE event stream");
  });

  it("fetches a release proof pack from the durable authority record", async () => {
    const markdown = "# LoopOS Authority Release Proof Pack";
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(markdown));
    const markdownHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      initiative_id: "initiative-authority",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      release_name: "Release 2026.08",
      readiness_verdict: { verdict: "NO_GO" },
      freshness_summary: { status: "fresh" },
      source_event_ids: ["connector-event-1"],
      markdown,
      markdown_hash: markdownHash,
      generated_at: "2026-07-23T12:00:00.000Z",
    }), { status: 200, headers: { "content-type": "application/json" } }));

    const proofPack = await getReleaseProofPack("token", "initiative-authority", "local-evaluation");

    expect(proofPack.markdown).toContain("Authority Release Proof Pack");
    expect(proofPack.markdown_hash).toHaveLength(64);
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/release-initiatives/initiative-authority/proof-pack", expect.objectContaining({
      headers: expect.objectContaining({ authorization: "Bearer token" }),
    }));
  });

  it("rejects a proof pack whose hash does not cover its returned markdown", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      initiative_id: "initiative-authority",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      release_name: "Release 2026.08",
      readiness_verdict: { verdict: "NO_GO" },
      freshness_summary: { status: "fresh" },
      source_event_ids: ["connector-event-1"],
      markdown: "# Tampered proof pack",
      markdown_hash: "a".repeat(64),
      generated_at: "2026-07-23T12:00:00.000Z",
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(getReleaseProofPack("token", "initiative-authority", "local-evaluation")).rejects.toThrow("invalid content hash");
  });

  it.each([
    ["freshness evaluation", (payload: Record<string, unknown>) => {
      payload.freshness_summary = { status: "fresh", evaluated_at: "not-a-timestamp" };
    }],
    ["readiness evaluation", (payload: Record<string, unknown>) => {
      payload.readiness_verdict = { verdict: "NO_GO", evaluated_at: "not-a-timestamp" };
    }],
    ["observed range", (payload: Record<string, unknown>) => {
      payload.freshness_summary = { status: "fresh", oldest_observed_at: "not-a-timestamp" };
    }],
  ])("rejects a release proof pack with an invalid %s timestamp", async (_field, mutate) => {
    const markdown = "# LoopOS Authority Release Proof Pack";
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(markdown));
    const markdownHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    const payload: Record<string, unknown> = {
      initiative_id: "initiative-authority",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      release_name: "Release 2026.08",
      readiness_verdict: { verdict: "NO_GO" },
      freshness_summary: { status: "fresh" },
      source_event_ids: ["connector-event-1"],
      markdown,
      markdown_hash: markdownHash,
      generated_at: "2026-07-23T12:00:00.000Z",
    };
    mutate(payload);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));

    await expect(getReleaseProofPack("token", "initiative-authority", "local-evaluation")).rejects.toThrow("invalid release proof pack data");
  });

  it("rejects connector evidence with a non-timestamp observation", async () => {
    const payload = {
      connector_event_id: "connector-event-1",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      system: "github",
      event_kind: "pull_request",
      external_id: "pr-1",
      label: "Release pull request",
      url: null,
      observed_at: "not-a-timestamp",
      payload_hash: "a".repeat(64),
      payload: { state: "open" },
      verification_status: "session_authenticated",
      delivery_id: null,
      created_by: "user-1",
      created_at: "2026-07-23T12:00:00.000Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([payload]), { status: 200 }));

    await expect(listConnectorEvents("token", "workspace-release", "local-evaluation")).rejects.toThrow("invalid connector event data");
  });

  it("releases a stream while delayed effectiveness is pending", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`id: 9\nevent: RUN_RELEASED\ndata: ${JSON.stringify({
          sequence: 9,
          event_id: "event-9",
          tenant_id: "tenant-1",
          run_id: "run-delayed",
          event_type: "RUN_RELEASED",
          state: null,
          actor_id: "user-1",
          created_at: "2026-07-23T12:00:00.000Z",
          event_hash: "a".repeat(64),
          previous_hash: "b".repeat(64),
          payload: { runner_status: "awaiting_effectiveness" },
        })}\n\n`));
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    await streamGovernedRun("token", "run-delayed", "tenant-1", () => undefined);
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("stops waiting when an audit stream body stalls after headers", async () => {
    const stream = new ReadableStream({
      pull() {
        return new Promise<void>(() => undefined);
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const controller = new AbortController();
    const pending = streamGovernedRun("token", "run-stalled", "tenant-1", () => undefined, controller.signal);

    await new Promise((resolve) => setTimeout(resolve, 0));
    controller.abort();

    await expect(pending).rejects.toThrow(/aborted/);
  });

  it("can consume a historical approval hold before a later terminal release", async () => {
    const encoder = new TextEncoder();
    const event = (sequence: number, eventType: string, runnerStatus?: string) => JSON.stringify({
      sequence,
      event_id: `event-${sequence}`,
      tenant_id: "tenant-1",
      run_id: "run-approved-after-reconnect",
      event_type: eventType,
      state: null,
      actor_id: "user-1",
      created_at: "2026-07-23T12:00:00.000Z",
      event_hash: "a".repeat(64),
      previous_hash: "b".repeat(64),
      payload: runnerStatus ? { runner_status: runnerStatus } : {},
    });
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`data: ${event(1, "RUN_RELEASED", "awaiting_approval")}\n\n`));
        controller.enqueue(encoder.encode(`data: ${event(2, "RUN_QUEUED")}\n\n`));
        controller.enqueue(encoder.encode(`data: ${event(3, "RUN_RELEASED", "completed")}\n\n`));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const events: string[] = [];
    await streamGovernedRun("token", "run-approved-after-reconnect", "tenant-1", (item) => events.push(item.event_type), undefined, 0, false);
    expect(events).toEqual(["RUN_RELEASED", "RUN_QUEUED", "RUN_RELEASED"]);
  });
});
