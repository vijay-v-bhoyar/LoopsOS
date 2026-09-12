import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { looposData } from "../../lib/loopos";
import { recommendLoops } from "../../lib/recommendation";
import { createInitiativeFromWorkspace } from "../../lib/sdlcProductivity";
import { validateUseCase } from "../../lib/validation";
import { createUser, createWorkspace, DEFAULT_WORKSPACE_USE_CASE } from "../../lib/workspaceStore";
import { AuthorityError } from "./authorityClient";
import type { AuthoritySession } from "./types";
import { GovernedExecutionPanel } from "./GovernedExecutionPanel";

const authorityMocks = vi.hoisted(() => ({
  createAuthoritySession: vi.fn(),
  activateKillSwitch: vi.fn(),
  deactivateKillSwitch: vi.fn(),
  getKillSwitchStatus: vi.fn(),
  listGovernedRuns: vi.fn(),
  listReleaseInitiatives: vi.fn(),
  listConnectorEvents: vi.fn(),
  recordReleaseInitiative: vi.fn(),
}));

vi.mock("./authorityClient", async () => {
  const actual = await vi.importActual<typeof import("./authorityClient")>("./authorityClient");
  return { ...actual, ...authorityMocks };
});

const session: AuthoritySession = {
  access_token: "authority-token",
  token_type: "bearer",
  expires_in: 900,
  actor: {
    tenant_id: "local-evaluation",
    user_id: "operator-1",
    name: "Operator",
    role: "Operator",
  },
};

describe("GovernedExecutionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authorityMocks.createAuthoritySession.mockResolvedValue(session);
    authorityMocks.getKillSwitchStatus.mockResolvedValue({
      tenant_id: "local-evaluation",
      scope: "tenant",
      active: false,
      activation_id: null,
      reason: null,
      actor_id: null,
      activated_at: null,
      deactivated_at: null,
      deactivated_by: null,
      deactivation_reason: null,
      semantics: "pre_dispatch_block_and_in_flight_interrupt",
    });
    authorityMocks.listGovernedRuns.mockResolvedValue([]);
    authorityMocks.listReleaseInitiatives.mockResolvedValue([]);
    authorityMocks.listConnectorEvents.mockResolvedValue([]);
  });

  it("surfaces refresh failures instead of creating an unhandled rejection", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Execution workspace", DEFAULT_WORKSPACE_USE_CASE);
    render(<GovernedExecutionPanel data={looposData} user={user} workspace={workspace} />);

    const refresh = await screen.findByRole("button", { name: "Refresh governed runs" });
    authorityMocks.listGovernedRuns.mockRejectedValueOnce(new Error("Authority request timed out."));
    fireEvent.click(refresh);

    await waitFor(() => expect(screen.getByText("Authority request timed out.")).toBeInTheDocument());
  });

  it("offers reconnect after an initial authority read failure", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Execution workspace", DEFAULT_WORKSPACE_USE_CASE);
    authorityMocks.listGovernedRuns.mockRejectedValueOnce(new Error("Authority request timed out."));
    render(<GovernedExecutionPanel data={looposData} user={user} workspace={workspace} />);

    const reconnect = await screen.findByRole("button", { name: "Reconnect authority" });
    expect(screen.getByText(/Authority unavailable\./)).toBeInTheDocument();
    fireEvent.click(reconnect);

    await waitFor(() => expect(screen.getByText("Authority connected")).toBeInTheDocument());
    expect(authorityMocks.listGovernedRuns).toHaveBeenCalledTimes(2);
  });

  it("does not let a late read from a previous workspace overwrite the selected workspace", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const firstWorkspace = createWorkspace(user, "First workspace", DEFAULT_WORKSPACE_USE_CASE);
    const secondWorkspace = createWorkspace(user, "Second workspace", DEFAULT_WORKSPACE_USE_CASE);
    const runShape = (runId: string, workspaceId: string, title: string) => ({
      run_id: runId,
      tenant_id: "local-evaluation",
      workspace_id: workspaceId,
      loop_id: looposData.loops[0].loop_id,
      title,
      trigger: "Test trigger",
      state: "TRIGGERED",
      runner_status: "queued",
      risk_tier: "R1",
      requires_approval: false,
      payload_hash: "a".repeat(64),
      plan: { action: { tool: "record_action" }, validation_probes: [], effectiveness_probes: [] },
      attempt: 1,
      created_by: user.user_id,
      created_at: "2026-09-04T00:00:00Z",
      updated_at: "2026-09-04T00:00:00Z",
      last_error: null,
      output: null,
    });
    const oldRun = runShape("old-run", firstWorkspace.workspace_id, "Old workspace run");
    const newRun = runShape("new-run", secondWorkspace.workspace_id, "New workspace run");
    let resolveFirstRead: ((runs: unknown[]) => void) | undefined;
    const firstRead = new Promise<unknown[]>((resolve) => { resolveFirstRead = resolve; });
    authorityMocks.listGovernedRuns.mockImplementation((_token: string, workspaceId: string) => workspaceId === firstWorkspace.workspace_id ? firstRead : Promise.resolve([newRun]));

    const { rerender } = render(<GovernedExecutionPanel data={looposData} user={user} workspace={firstWorkspace} />);
    rerender(<GovernedExecutionPanel data={looposData} user={user} workspace={secondWorkspace} />);
    await waitFor(() => expect(screen.getByText("New workspace run")).toBeInTheDocument());

    act(() => resolveFirstRead?.([oldRun]));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("Old workspace run")).not.toBeInTheDocument();
  });

  it("returns to the shared sign-in boundary when an execution request expires", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Execution workspace", DEFAULT_WORKSPACE_USE_CASE);
    const onSessionExpired = vi.fn();
    render(<GovernedExecutionPanel data={looposData} user={user} workspace={workspace} onSessionExpired={onSessionExpired} />);

    const refresh = await screen.findByRole("button", { name: "Refresh governed runs" });
    authorityMocks.listGovernedRuns.mockRejectedValueOnce(new AuthorityError("Session expired.", 401));
    fireEvent.click(refresh);

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce());
    expect(screen.getByText("Session expired.")).toBeInTheDocument();
  });

  it("lets an Executive stop and restore tenant execution through the authority control", async () => {
    const user = createUser("Executive", "executive@example.local", "Executive");
    const workspace = createWorkspace(user, "Execution workspace", DEFAULT_WORKSPACE_USE_CASE);
    const inactive = {
      tenant_id: "local-evaluation",
      scope: "tenant" as const,
      active: false,
      activation_id: null,
      reason: null,
      actor_id: null,
      activated_at: null,
      deactivated_at: null,
      deactivated_by: null,
      deactivation_reason: null,
      semantics: "pre_dispatch_block_and_in_flight_interrupt" as const,
    };
    const active = {
      ...inactive,
      active: true,
      activation_id: "kill-switch-test",
      reason: "Emergency test stop.",
      actor_id: "executive-1",
      activated_at: "2026-09-04T00:00:00Z",
    };
    authorityMocks.getKillSwitchStatus
      .mockResolvedValueOnce(inactive)
      .mockResolvedValueOnce(active)
      .mockResolvedValue(inactive);
    authorityMocks.activateKillSwitch.mockResolvedValue(active);
    authorityMocks.deactivateKillSwitch.mockResolvedValue(inactive);
    render(<GovernedExecutionPanel data={looposData} user={user} workspace={workspace} />);

    const stop = await screen.findByRole("button", { name: "Stop tenant execution" });
    fireEvent.click(stop);
    await waitFor(() => expect(screen.getByText("STOPPED")).toBeInTheDocument());
    expect(authorityMocks.activateKillSwitch).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Restore tenant execution" }));
    await waitFor(() => expect(screen.getByText("RUNNING")).toBeInTheDocument());
    expect(authorityMocks.deactivateKillSwitch).toHaveBeenCalledOnce();
  });

  it("does not call an unverified action payload verified output", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Execution workspace", DEFAULT_WORKSPACE_USE_CASE);
    authorityMocks.listGovernedRuns.mockResolvedValueOnce([{
      run_id: "run-validation-failed",
      tenant_id: "local-evaluation",
      workspace_id: workspace.workspace_id,
      loop_id: looposData.loops[0].loop_id,
      title: "Failed connector action",
      trigger: "Test failure path",
      state: "VALIDATION_FAILED",
      runner_status: "failed",
      risk_tier: "R2",
      requires_approval: false,
      payload_hash: "a".repeat(64),
      plan: {
        evidence: [{ evidence_id: "workspace", kind: "workspace_snapshot", source_ref: "workspace", freshness_seconds: 60 }],
        validation_probes: [{ probe_id: "validation", kind: "json_equals", target: "action_output", path: "status", expected: "ok" }],
        effectiveness_probes: [{ probe_id: "effectiveness", kind: "json_equals", target: "action_output", path: "status", expected: "ok" }],
        action: { tool: "record_action", arguments: {}, idempotency_key: "action-failed", external_effect: false },
        max_attempts: 1,
        observation_delay_seconds: 0,
      },
      attempt: 1,
      created_by: "operator-1",
      created_at: "2026-08-23T00:00:00Z",
      updated_at: "2026-08-23T00:00:00Z",
      last_error: "Validation probe failed.",
      output: { status: "applied" },
    }]);
    render(<GovernedExecutionPanel data={looposData} user={user} workspace={workspace} />);

    await screen.findByText("Action output, not effectiveness-proven");
    expect(screen.queryByText("Verified output")).not.toBeInTheDocument();
  });

  it("records release evidence through one atomic authority mutation", async () => {
    const user = createUser("Operator", "operator@example.local", "Operator");
    const workspace = createWorkspace(user, "Release workspace", {
      ...DEFAULT_WORKSPACE_USE_CASE,
      title: "Prepare release 2026.08",
      description: "Govern a production release with Jira and GitHub evidence.",
    });
    const recommendations = recommendLoops(workspace.use_case, looposData);
    const validation = validateUseCase(workspace.use_case, recommendations, looposData, []);
    const initiative = createInitiativeFromWorkspace(workspace, recommendations, validation, looposData, user.name, "2026-07-23T12:00:00.000Z");
    const authorityWorkspace = { ...workspace, initiatives: [initiative] };
    authorityMocks.recordReleaseInitiative.mockResolvedValue({ initiative: {}, connector_events: [] });

    render(<GovernedExecutionPanel data={looposData} user={user} workspace={authorityWorkspace} />);
    fireEvent.click(await screen.findByRole("button", { name: "Record release initiative" }));

    await waitFor(() => expect(authorityMocks.recordReleaseInitiative).toHaveBeenCalledOnce());
    const [, input, connectorEvents, tenantId] = authorityMocks.recordReleaseInitiative.mock.calls[0];
    expect(input.source_event_ids).toEqual([]);
    expect(connectorEvents.length).toBeGreaterThan(0);
    expect(connectorEvents.every((event: { workspace_id: string }) => event.workspace_id === workspace.workspace_id)).toBe(true);
    expect(tenantId).toBe("local-evaluation");
  });
});
