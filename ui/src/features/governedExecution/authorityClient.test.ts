import { beforeEach, describe, expect, it, vi } from "vitest";
import { buildConnectorEventsForRelease, buildReleaseInitiativeRecord, buildWorkspaceExecutionPlan } from "./types";
import { createReleaseAssuranceProfile } from "../../lib/releaseAssurance";
import { createUser, createWorkspace, DEFAULT_WORKSPACE_USE_CASE } from "../../lib/workspaceStore";
import {
  AuthorityError,
  createAuthoritySession,
  createAuthorityWorkspace,
  createDevelopmentSession,
  createEnterpriseSession,
  createReleaseInitiative,
  deleteAuthorityWorkspace,
  getReleaseProofPack,
  getAuthorityReadiness,
  listAuthorityWorkspaces,
  recordConnectorEvent,
  streamGovernedRun,
  updateAuthorityWorkspace,
} from "./authorityClient";
import { looposData } from "../../lib/loopos";
import type { InitiativeWorkspace } from "../../types";

describe("authorityClient", () => {
  beforeEach(() => vi.restoreAllMocks());

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

  it("creates an explicit development authority session without persisting the token", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ access_token: "token", token_type: "bearer", expires_in: 3600, actor: { tenant_id: "local-evaluation", user_id: "user", name: "Operator", role: "Operator" } }), { status: 200, headers: { "content-type": "application/json" } }));
    const user = createUser("Operator", "operator@example.local", "Operator");
    const session = await createDevelopmentSession(user);

    expect(session.access_token).toBe("token");
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/dev/sessions", expect.objectContaining({ credentials: "omit", redirect: "error" }));
    expect(window.localStorage.length).toBe(0);
  });

  it("exchanges only same-origin identity credentials for an enterprise session", async () => {
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
      credentials: "same-origin",
      redirect: "error",
    }));
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

    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/sessions", expect.any(Object));
  });

  it("reads fail-closed runtime evidence from the authority readiness endpoint", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      status: "ready",
      storage_backend: "postgres",
      production_identity: true,
      audit_anchor_configured: true,
      audit_anchor_backlog: 0,
      audit_anchor_delivery_verified: true,
      audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
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
      backup_restore_evidence: {
        url: "https://evidence.example.com/loopos/postgres-restore.json",
        sha256: "a".repeat(64),
        verified_at: "2026-07-30T12:00:00+00:00",
      },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    const readiness = await getAuthorityReadiness();

    expect(readiness).toMatchObject({
      storage_backend: "postgres",
      production_identity: true,
      audit_anchor_configured: true,
      audit_anchor_backlog: 0,
      audit_anchor_delivery_verified: true,
      execution_worker_dispatch: expect.objectContaining({ verified: true, source: "external" }),
      operational_bindings: expect.objectContaining({ backup_restore_verified: true }),
      backup_restore_evidence: expect.objectContaining({ sha256: "a".repeat(64) }),
    });
    expect(fetchImpl).toHaveBeenCalledWith("/api/health/ready", expect.objectContaining({
      credentials: "omit",
      cache: "no-store",
    }));
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

  it("builds and posts a release assurance initiative record", async () => {
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
    const fetchImpl = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...connectorInput, connector_event_id: "connector-event-1", tenant_id: "local-evaluation", payload_hash: "hash-1", verification_status: "session_authenticated", created_by: user.user_id, created_at: "2026-07-23T12:00:00.000Z" }), { status: 201, headers: { "content-type": "application/json" } }))
      .mockImplementationOnce(async (_url, init) => {
        const body = JSON.parse(String(init?.body)) as { source_event_ids: string[] };
        return new Response(JSON.stringify({ ...body, ...buildReleaseInitiativeRecord(workspace, initiative, body.source_event_ids), initiative_id: "initiative-authority", tenant_id: "local-evaluation", freshness_summary: { status: "fresh", source_event_count: 1 }, readiness_verdict: { verdict: "NO_GO", failing_reasons: ["release gate blocked"] }, created_by: user.user_id, created_at: "2026-07-23T12:00:00.000Z", updated_at: "2026-07-23T12:00:00.000Z" }), { status: 201, headers: { "content-type": "application/json" } });
      });

    const event = await recordConnectorEvent("token", connectorInput);
    const input = buildReleaseInitiativeRecord(workspace, initiative, [event.connector_event_id]);
    const record = await createReleaseInitiative("token", input);

    expect(record.initiative_id).toBe("initiative-authority");
    expect(record.source_event_ids).toEqual(["connector-event-1"]);
    expect(record.release_assurance.gates.length).toBeGreaterThan(0);
    expect(record.freshness_summary?.status).toBe("fresh");
    expect(record.readiness_verdict?.verdict).toBe("NO_GO");
    expect(fetchImpl).toHaveBeenNthCalledWith(1, "/api/v1/connector-events", expect.objectContaining({ method: "POST" }));
    expect(fetchImpl).toHaveBeenNthCalledWith(2, "/api/v1/release-initiatives", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ authorization: "Bearer token", "idempotency-key": expect.stringContaining("release-") }),
    }));
  });

  it("parses streamed audit events and stops at an authority release boundary", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('id: 1\nevent: RUN_CREATED\ndata: {"sequence":1,"event_type":"RUN_CREATED","payload":{}}\n\n'));
        controller.enqueue(encoder.encode('id: 2\nevent: RUN_RELEASED\ndata: {"sequence":2,"event_type":"RUN_RELEASED","payload":{"runner_status":"completed"}}\n\n'));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
    const events: string[] = [];
    await streamGovernedRun("token", "run-1", (event) => events.push(event.event_type), undefined, 7);
    expect(events).toEqual(["RUN_CREATED", "RUN_RELEASED"]);
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("after=7"), expect.any(Object));
  });

  it("fetches a release proof pack from the durable authority record", async () => {
    const fetchImpl = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      initiative_id: "initiative-authority",
      tenant_id: "local-evaluation",
      workspace_id: "workspace-release",
      release_name: "Release 2026.08",
      readiness_verdict: { verdict: "NO_GO" },
      freshness_summary: { status: "fresh" },
      source_event_ids: ["connector-event-1"],
      markdown: "# LoopOS Authority Release Proof Pack",
      markdown_hash: "a".repeat(64),
      generated_at: "2026-07-23T12:00:00.000Z",
    }), { status: 200, headers: { "content-type": "application/json" } }));

    const proofPack = await getReleaseProofPack("token", "initiative-authority");

    expect(proofPack.markdown).toContain("Authority Release Proof Pack");
    expect(proofPack.markdown_hash).toHaveLength(64);
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/release-initiatives/initiative-authority/proof-pack", expect.objectContaining({
      headers: expect.objectContaining({ authorization: "Bearer token" }),
    }));
  });

  it("releases a stream while delayed effectiveness is pending", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('id: 9\nevent: RUN_RELEASED\ndata: {"sequence":9,"event_type":"RUN_RELEASED","payload":{"runner_status":"awaiting_effectiveness"}}\n\n'));
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200 }));
    await streamGovernedRun("token", "run-delayed", () => undefined);
    expect(fetch).toHaveBeenCalledOnce();
  });
});
