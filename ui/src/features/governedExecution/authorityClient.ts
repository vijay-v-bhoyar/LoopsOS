import type { EnterpriseUser, SavedWorkspace } from "../../types";
import { deploymentPosture, type DeploymentMode } from "../../lib/deployment";
import type { AuditVerification, AuthorityEvent, AuthoritySession, ConnectorEventInput, ConnectorEventRecord, CreateGovernedRun, CreateReleaseInitiative, GovernedRun, ReleaseInitiativeRecord, ReleaseProofPack } from "./types";

const AUTHORITY_BASE = (import.meta.env.VITE_LOOPOS_AUTHORITY_URL as string | undefined)?.replace(/\/$/, "") ?? "/api";

export class AuthorityError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export interface AuthorityWorkspaceRecord {
  workspace_id: string;
  tenant_id: string;
  revision: number;
  document: SavedWorkspace;
  document_hash: string;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 15_000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${AUTHORITY_BASE}${path}`, {
      ...options,
      cache: "no-store",
      credentials: options.credentials ?? "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
    if (!response.ok) throw new AuthorityError(typeof payload.detail === "string" ? payload.detail : `Authority returned ${response.status}.`, response.status);
    return payload as T;
  } catch (error) {
    if (controller.signal.aborted) throw new AuthorityError(`Authority request timed out after ${timeoutMs} ms.`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function authorized(token: string, init: RequestInit = {}): RequestInit {
  return { ...init, headers: { ...init.headers, authorization: `Bearer ${token}` } };
}

export async function createDevelopmentSession(user: EnterpriseUser): Promise<AuthoritySession> {
  return request<AuthoritySession>("/v1/dev/sessions", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ tenant_id: "local-evaluation", user_id: user.user_id, name: user.name, role: user.role, ttl_seconds: 3600 }),
  });
}

export async function createEnterpriseSession(): Promise<AuthoritySession> {
  return request<AuthoritySession>("/v1/sessions", {
    method: "POST",
    credentials: "same-origin",
  });
}

export async function createAuthoritySession(
  user: EnterpriseUser,
  mode: DeploymentMode = deploymentPosture.mode,
): Promise<AuthoritySession> {
  return mode === "enterprise" ? createEnterpriseSession() : createDevelopmentSession(user);
}

export async function listAuthorityWorkspaces(token: string): Promise<AuthorityWorkspaceRecord[]> {
  return request<AuthorityWorkspaceRecord[]>("/v1/workspaces", authorized(token));
}

export async function createAuthorityWorkspace(token: string, workspace: SavedWorkspace): Promise<AuthorityWorkspaceRecord> {
  return request<AuthorityWorkspaceRecord>(`/v1/workspaces/${encodeURIComponent(workspace.workspace_id)}`, authorized(token, {
    method: "PUT",
    headers: { "content-type": "application/json", "if-none-match": "*" },
    body: JSON.stringify({ document: workspace }),
  }));
}

export async function updateAuthorityWorkspace(token: string, workspace: SavedWorkspace, revision: number): Promise<AuthorityWorkspaceRecord> {
  return request<AuthorityWorkspaceRecord>(`/v1/workspaces/${encodeURIComponent(workspace.workspace_id)}`, authorized(token, {
    method: "PUT",
    headers: { "content-type": "application/json", "if-match": `"${revision}"` },
    body: JSON.stringify({ document: workspace }),
  }));
}

export async function deleteAuthorityWorkspace(token: string, workspaceId: string, revision: number): Promise<void> {
  await request(`/v1/workspaces/${encodeURIComponent(workspaceId)}`, authorized(token, {
    method: "DELETE",
    headers: { "if-match": `"${revision}"` },
  }));
}

export async function listGovernedRuns(token: string, workspaceId: string): Promise<GovernedRun[]> {
  return request<GovernedRun[]>(`/v1/runs?workspace_id=${encodeURIComponent(workspaceId)}`, authorized(token));
}

export async function listReleaseInitiatives(token: string, workspaceId: string): Promise<ReleaseInitiativeRecord[]> {
  return request<ReleaseInitiativeRecord[]>(`/v1/release-initiatives?workspace_id=${encodeURIComponent(workspaceId)}`, authorized(token));
}

export async function listConnectorEvents(token: string, workspaceId: string): Promise<ConnectorEventRecord[]> {
  return request<ConnectorEventRecord[]>(`/v1/connector-events?workspace_id=${encodeURIComponent(workspaceId)}`, authorized(token));
}

export async function getGovernedRun(token: string, runId: string): Promise<GovernedRun> {
  return request<GovernedRun>(`/v1/runs/${encodeURIComponent(runId)}`, authorized(token));
}

export async function createGovernedRun(token: string, input: CreateGovernedRun): Promise<GovernedRun> {
  return request<GovernedRun>("/v1/runs", authorized(token, {
    method: "POST",
    headers: { "content-type": "application/json", "idempotency-key": `create-${crypto.randomUUID()}` },
    body: JSON.stringify(input),
  }));
}

export async function createReleaseInitiative(token: string, input: CreateReleaseInitiative): Promise<ReleaseInitiativeRecord> {
  return request<ReleaseInitiativeRecord>("/v1/release-initiatives", authorized(token, {
    method: "POST",
    headers: { "content-type": "application/json", "idempotency-key": `release-${input.workspace_id}-${input.release_name}`.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 180) },
    body: JSON.stringify(input),
  }));
}

export async function getReleaseProofPack(token: string, initiativeId: string): Promise<ReleaseProofPack> {
  return request<ReleaseProofPack>(`/v1/release-initiatives/${encodeURIComponent(initiativeId)}/proof-pack`, authorized(token));
}

export async function recordConnectorEvent(token: string, input: ConnectorEventInput): Promise<ConnectorEventRecord> {
  return request<ConnectorEventRecord>("/v1/connector-events", authorized(token, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  }));
}

export async function startGovernedRun(token: string, runId: string): Promise<void> {
  await request(`/v1/runs/${encodeURIComponent(runId)}/start`, authorized(token, { method: "POST" }));
}

export async function approveGovernedRun(token: string, run: GovernedRun, reason: string): Promise<void> {
  await request(`/v1/runs/${encodeURIComponent(run.run_id)}/approve`, authorized(token, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ payload_hash: run.payload_hash, decision_reason: reason }),
  }));
}

export async function rejectGovernedRun(token: string, run: GovernedRun, reason: string): Promise<void> {
  await request(`/v1/runs/${encodeURIComponent(run.run_id)}/reject`, authorized(token, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ payload_hash: run.payload_hash, decision_reason: reason }),
  }));
}

export async function verifyAuthorityAudit(token: string): Promise<AuditVerification> {
  return request<AuditVerification>("/v1/audit/verify", authorized(token));
}

export async function recoverGovernedRun(token: string, runId: string): Promise<GovernedRun> {
  return request<GovernedRun>(`/v1/runs/${encodeURIComponent(runId)}/recover`, authorized(token, {
    method: "POST",
    headers: { "idempotency-key": `recover-${crypto.randomUUID()}` },
  }));
}

export async function rollbackGovernedRun(token: string, runId: string): Promise<void> {
  await request(`/v1/runs/${encodeURIComponent(runId)}/rollback`, authorized(token, { method: "POST" }));
}

export async function streamGovernedRun(
  token: string,
  runId: string,
  onEvent: (event: AuthorityEvent) => void,
  signal?: AbortSignal,
  after = 0,
): Promise<void> {
  const response = await fetch(`${AUTHORITY_BASE}/v1/runs/${encodeURIComponent(runId)}/events?after=${after}`, {
    headers: { accept: "text/event-stream", authorization: `Bearer ${token}` },
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    referrerPolicy: "no-referrer",
    signal,
  });
  if (!response.ok || !response.body) throw new AuthorityError(`Event stream returned ${response.status}.`, response.status);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
      if (!data) continue;
      const event = JSON.parse(data) as AuthorityEvent;
      onEvent(event);
      if (event.event_type === "RUN_RELEASED" && ["awaiting_approval", "awaiting_effectiveness", "completed", "failed", "rolled_back"].includes(String(event.payload.runner_status))) {
        await reader.cancel();
        return;
      }
    }
  }
}
