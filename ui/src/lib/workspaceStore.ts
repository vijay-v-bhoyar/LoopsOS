import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ApprovalRecord,
  EnterpriseActionPlan,
  EnterpriseUser,
  ExecutionRecord,
  OwnerEvidenceEdit,
  SavedWorkspace,
  UseCaseInput,
  UserRole,
  WorkspaceState,
} from "../types";

const STORAGE_KEY = "loopos.v2.workspace-state";
export const MAX_WORKSPACE_STORAGE_BYTES = 4_000_000;

export interface WorkspacePersistenceResult {
  status: "saved" | "skipped" | "error";
  code?: "size_limit" | "storage_unavailable";
  message?: string;
  bytes: number;
}

export const EMPTY_STATE: WorkspaceState = {
  current_user: null,
  active_workspace_id: null,
  workspaces: [],
};

export const DEFAULT_WORKSPACE_USE_CASE: UseCaseInput = {
  title: "Prepare enterprise for agentic AI",
  description: "Assess whether our enterprise is ready for AI agents that use tools, memory, retrieval, and delegated workflows while preserving security, auditability, and human approvals.",
  environment: "enterprise portfolio",
  aiScope: "Agentic AI",
  dataSensitivity: "sensitive",
  businessOutcome: "Reduce agentic AI governance cycle time while preventing unsafe execution.",
  maturity: "discovery",
  constraints: "Must support compliance evidence, access controls, audit logging, approvals, and operational records before production.",
};

export function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function loadWorkspaceState(): WorkspaceState {
  if (typeof window === "undefined") return EMPTY_STATE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_STATE;
    const parsed = JSON.parse(raw) as unknown;
    return isRecord(parsed) ? normalizeWorkspaceState(parsed) : EMPTY_STATE;
  } catch {
    return EMPTY_STATE;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isUseCase(value: unknown): value is UseCaseInput {
  if (!isRecord(value)) return false;
  return ["title", "description", "environment", "aiScope", "dataSensitivity", "businessOutcome", "maturity", "constraints"].every((field) => isString(value[field]));
}

function normalizeUser(value: unknown): EnterpriseUser | null {
  if (!isRecord(value)) return null;
  const validRole = value.role === "Executive" || value.role === "Approver" || value.role === "Operator" || value.role === "Auditor";
  if (![value.user_id, value.name, value.email, value.signed_in_at].every(isString) || !validRole) return null;
  return value as unknown as EnterpriseUser;
}

function normalizeWorkspace(value: unknown): SavedWorkspace | null {
  if (!isRecord(value) || !isUseCase(value.use_case)) return null;
  if (![value.workspace_id, value.name, value.created_at, value.updated_at, value.owner_user_id].every(isString)) return null;
  return {
    workspace_id: value.workspace_id as string,
    name: value.name as string,
    created_at: value.created_at as string,
    updated_at: value.updated_at as string,
    owner_user_id: value.owner_user_id as string,
    use_case: value.use_case,
    selected_loop_ids: Array.isArray(value.selected_loop_ids) ? value.selected_loop_ids.filter(isString) : [],
    action_plan_markdown: isString(value.action_plan_markdown) ? value.action_plan_markdown : "",
    owner_evidence_edits: Array.isArray(value.owner_evidence_edits) ? value.owner_evidence_edits.filter(isRecord) as unknown as OwnerEvidenceEdit[] : [],
    approvals: Array.isArray(value.approvals) ? value.approvals.filter(isRecord) as unknown as ApprovalRecord[] : [],
    execution_records: Array.isArray(value.execution_records) ? value.execution_records.filter(isRecord) as unknown as ExecutionRecord[] : [],
    initiatives: Array.isArray(value.initiatives) ? value.initiatives.filter(isRecord) as unknown as SavedWorkspace["initiatives"] : [],
    question_suggestions: Array.isArray(value.question_suggestions) ? value.question_suggestions.filter(isRecord) as unknown as SavedWorkspace["question_suggestions"] : [],
    input_sources: Array.isArray(value.input_sources) ? value.input_sources.filter(isRecord) as unknown as SavedWorkspace["input_sources"] : [],
  };
}

export function normalizeWorkspaceState(value: Record<string, unknown> | Partial<WorkspaceState>): WorkspaceState {
  const workspaces = Array.isArray(value.workspaces)
    ? value.workspaces.map(normalizeWorkspace).filter((workspace): workspace is SavedWorkspace => Boolean(workspace))
    : [];
  const activeWorkspaceExists = workspaces.some((workspace) => workspace.workspace_id === value.active_workspace_id);
  return {
    current_user: normalizeUser(value.current_user),
    active_workspace_id: activeWorkspaceExists && isString(value.active_workspace_id) ? value.active_workspace_id : workspaces[0]?.workspace_id ?? null,
    workspaces,
  };
}

export function saveWorkspaceState(state: WorkspaceState): WorkspacePersistenceResult {
  if (typeof window === "undefined") return { status: "skipped", bytes: 0 };
  const serialized = JSON.stringify(state);
  const bytes = new TextEncoder().encode(serialized).byteLength;
  if (bytes > MAX_WORKSPACE_STORAGE_BYTES) {
    return { status: "error", code: "size_limit", message: "Workspace data exceeds the 4 MB browser-local storage limit.", bytes };
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, serialized);
    return { status: "saved", bytes };
  } catch {
    return { status: "error", code: "storage_unavailable", message: "Browser-local storage is unavailable or full. Export the workspace before leaving this page.", bytes };
  }
}

export function createUser(name: string, email: string, role: UserRole): EnterpriseUser {
  return {
    user_id: uid("user"),
    name: name.trim() || "LoopOS Operator",
    email: email.trim() || "operator@example.local",
    role,
    signed_in_at: nowIso(),
  };
}

export function createWorkspace(user: EnterpriseUser, name: string, useCase: UseCaseInput = DEFAULT_WORKSPACE_USE_CASE): SavedWorkspace {
  const timestamp = nowIso();
  return {
    workspace_id: uid("workspace"),
    name: name.trim() || "Agentic AI Readiness Workspace",
    created_at: timestamp,
    updated_at: timestamp,
    owner_user_id: user.user_id,
    use_case: useCase,
    selected_loop_ids: [],
    action_plan_markdown: "",
    owner_evidence_edits: [],
    approvals: [],
    execution_records: [],
    initiatives: [],
    question_suggestions: [],
    input_sources: [],
  };
}

export function createOwnerEvidenceEdit(params: Omit<OwnerEvidenceEdit, "edit_id" | "edited_at">): OwnerEvidenceEdit {
  return {
    ...params,
    edit_id: uid("edit"),
    edited_at: nowIso(),
  };
}

export function createApproval(params: Omit<ApprovalRecord, "approval_id" | "requested_at" | "status">): ApprovalRecord {
  return {
    ...params,
    approval_id: uid("approval"),
    requested_at: nowIso(),
    status: "Pending",
  };
}

export function createExecution(params: Omit<ExecutionRecord, "execution_id" | "created_at" | "updated_at">): ExecutionRecord {
  const timestamp = nowIso();
  return {
    ...params,
    execution_id: uid("execution"),
    created_at: timestamp,
    updated_at: timestamp,
  };
}

export function canApprove(user: EnterpriseUser | null): boolean {
  return Boolean(user && (user.role === "Approver" || user.role === "Executive"));
}

export function useWorkspaceStore() {
  const [state, setState] = useState<WorkspaceState>(() => loadWorkspaceState());
  const [persistence, setPersistence] = useState<WorkspacePersistenceResult>({ status: "skipped", bytes: 0 });

  useEffect(() => {
    setPersistence(saveWorkspaceState(state));
  }, [state]);

  const activeWorkspace = useMemo(
    () => state.workspaces.find((workspace) => workspace.workspace_id === state.active_workspace_id) ?? null,
    [state.active_workspace_id, state.workspaces],
  );

  const mutateActiveWorkspace = useCallback((updater: (workspace: SavedWorkspace) => SavedWorkspace) => {
    setState((current) => {
      if (!current.active_workspace_id) return current;
      return {
        ...current,
        workspaces: current.workspaces.map((workspace) =>
          workspace.workspace_id === current.active_workspace_id ? { ...updater(workspace), updated_at: nowIso() } : workspace,
        ),
      };
    });
  }, []);

  const signIn = useCallback((name: string, email: string, role: UserRole) => {
    setState((current) => {
      const user = createUser(name, email, role);
      const hasWorkspace = current.workspaces.length > 0;
      const firstWorkspace = hasWorkspace ? current.workspaces[0] : createWorkspace(user, "Agentic AI Readiness Workspace");
      return {
        ...current,
        current_user: user,
        active_workspace_id: current.active_workspace_id ?? firstWorkspace.workspace_id,
        workspaces: hasWorkspace ? current.workspaces : [firstWorkspace],
      };
    });
  }, []);

  const signOut = useCallback(() => {
    setState((current) => ({ ...current, current_user: null }));
  }, []);

  const addWorkspace = useCallback((name: string, useCase: UseCaseInput) => {
    setState((current) => {
      if (!current.current_user) return current;
      const workspace = createWorkspace(current.current_user, name, useCase);
      return {
        ...current,
        active_workspace_id: workspace.workspace_id,
        workspaces: [...current.workspaces, workspace],
      };
    });
  }, []);

  const setActiveWorkspace = useCallback((workspaceId: string) => {
    setState((current) => current.workspaces.some((workspace) => workspace.workspace_id === workspaceId) ? { ...current, active_workspace_id: workspaceId } : current);
  }, []);

  const deleteWorkspace = useCallback((workspaceId: string) => {
    setState((current) => {
      const workspaces = current.workspaces.filter((workspace) => workspace.workspace_id !== workspaceId);
      return {
        ...current,
        workspaces,
        active_workspace_id: current.active_workspace_id === workspaceId ? workspaces[0]?.workspace_id ?? null : current.active_workspace_id,
      };
    });
  }, []);

  const updateUseCase = useCallback(
    (useCase: UseCaseInput) => {
      mutateActiveWorkspace((workspace) => ({ ...workspace, use_case: useCase }));
    },
    [mutateActiveWorkspace],
  );

  const savePlan = useCallback(
    (plan: EnterpriseActionPlan) => {
      mutateActiveWorkspace((workspace) => ({
        ...workspace,
        action_plan_markdown: plan.exportMarkdown,
        selected_loop_ids: plan.recommendations.slice(0, 12).map((recommendation) => recommendation.loop_id),
      }));
    },
    [mutateActiveWorkspace],
  );

  return {
    state,
    persistence,
    activeWorkspace,
    signIn,
    signOut,
    addWorkspace,
    setActiveWorkspace,
    deleteWorkspace,
    updateUseCase,
    savePlan,
    mutateActiveWorkspace,
    setState,
  };
}
