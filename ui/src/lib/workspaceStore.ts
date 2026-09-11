import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AuthorityError,
  createAuthorityWorkspace,
  createEnterpriseSession,
  deleteAuthorityWorkspace,
  getAuthorityReadiness,
  listAuthorityWorkspaces,
  updateAuthorityWorkspace,
  type AuthorityReadiness,
  type AuthorityWorkspaceRecord,
} from "../features/governedExecution/authorityClient";
import type { AuthoritySession } from "../features/governedExecution/types";
import { authorityConfigurationMatches, deploymentPosture, type DeploymentMode, type DeploymentPosture, type DeploymentRuntimeEvidence } from "./deployment";
import { isSavedWorkspaceDocument } from "./workspaceDocument";
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

export const EMPTY_WORKSPACE_USE_CASE: UseCaseInput = {
  title: "",
  description: "",
  environment: "",
  aiScope: "",
  dataSensitivity: "",
  businessOutcome: "",
  maturity: "",
  constraints: "",
};

export interface WorkspacePersistenceResult {
  status: "saved" | "skipped" | "error";
  code?: "size_limit" | "storage_unavailable" | "authority_conflict" | "authority_unauthorized" | "authority_unavailable";
  message?: string;
  bytes: number;
  location?: "browser" | "authority";
}

export interface EnterpriseSessionState {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  retryable?: boolean;
}

export interface WorkspaceAuthorityAdapter {
  checkReadiness?: () => Promise<AuthorityReadiness>;
  createSession: () => Promise<AuthoritySession>;
  listWorkspaces: (token: string) => Promise<AuthorityWorkspaceRecord[]>;
  createWorkspace: (token: string, workspace: SavedWorkspace) => Promise<AuthorityWorkspaceRecord>;
  updateWorkspace: (token: string, workspace: SavedWorkspace, revision: number) => Promise<AuthorityWorkspaceRecord>;
  deleteWorkspace: (token: string, workspaceId: string, revision: number) => Promise<void>;
}

export interface WorkspaceStoreOptions {
  mode?: DeploymentMode;
  posture?: Pick<DeploymentPosture, "mode" | "blockers" | "allowedEndpointHosts" | "outboundPolicyMode" | "retentionPolicyUrl" | "supportContact" | "backupRestoreEvidenceUrl">;
  authority?: WorkspaceAuthorityAdapter;
  saveDebounceMs?: number;
}

export function runtimeEvidenceFromReadiness(
  readiness: AuthorityReadiness,
  posture: Pick<DeploymentPosture, "mode" | "allowedEndpointHosts" | "outboundPolicyMode" | "retentionPolicyUrl" | "supportContact" | "backupRestoreEvidenceUrl"> = deploymentPosture,
): DeploymentRuntimeEvidence {
  return {
    apiReachable: true,
    configurationVerified: authorityConfigurationMatches(posture, readiness.configuration_contract),
    credentialInjectionBrokerVerified: readiness.credential_injection_broker_verified,
    rateLimitVerified: readiness.rate_limit_configured,
    // Readiness only proves infrastructure health; the authenticated workspace
    // list below is the proof used for the runtime persistence binding.
    persistenceVerified: false,
    auditVerified: readiness.audit_anchor_configured
      && readiness.audit_anchor_backlog === 0
      && readiness.audit_anchor_delivery_verified
      && readiness.audit_anchor_delivery_fresh,
    retentionVerified: readiness.operational_bindings.retention_verified,
    supportVerified: readiness.operational_bindings.support_verified,
    outboundPolicyVerified: readiness.operational_bindings.outbound_policy_verified,
    backupRestoreVerified: readiness.operational_bindings.backup_restore_verified,
    workerVerified: readiness.execution_worker_dispatch.verified
      && readiness.operational_bindings.worker_dispatch_verified,
  };
}

export function readinessProofFailures(
  readiness: AuthorityReadiness,
  posture: Pick<DeploymentPosture, "mode" | "allowedEndpointHosts" | "outboundPolicyMode" | "retentionPolicyUrl" | "supportContact" | "backupRestoreEvidenceUrl"> = deploymentPosture,
): string[] {
  const evidence = runtimeEvidenceFromReadiness(readiness, posture);
  const failures: string[] = [];
  const persistenceReady = readiness.storage_backend === "postgres" && readiness.execution_job_backlog === 0;
  if (readiness.development_auth !== false) failures.push("development_auth_disabled");
  if (readiness.production_identity !== true) failures.push("production_identity");
  if (readiness.execution_job_backlog !== 0) failures.push("execution_job_backlog");
  if (!persistenceReady) failures.push("persistence_ready");
  if (evidence.configurationVerified !== true) failures.push("configuration_contract");
  for (const [name, verified] of Object.entries(evidence)) {
    if (name === "apiReachable" || name === "persistenceVerified") continue;
    if (verified !== true) failures.push(name);
  }
  return [...new Set(failures)];
}

const DEFAULT_AUTHORITY_ADAPTER: WorkspaceAuthorityAdapter = {
  checkReadiness: getAuthorityReadiness,
  createSession: createEnterpriseSession,
  listWorkspaces: listAuthorityWorkspaces,
  createWorkspace: createAuthorityWorkspace,
  updateWorkspace: updateAuthorityWorkspace,
  deleteWorkspace: deleteAuthorityWorkspace,
};

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

function normalizeUser(value: unknown): EnterpriseUser | null {
  if (!isRecord(value)) return null;
  const validRole = value.role === "Executive" || value.role === "Approver" || value.role === "Operator" || value.role === "Auditor";
  if (![value.user_id, value.name, value.email, value.signed_in_at].every(isString) || !validRole) return null;
  return value as unknown as EnterpriseUser;
}

function normalizeWorkspace(value: unknown): SavedWorkspace | null {
  if (!isRecord(value)) return null;
  const legacyDefaults = {
    selected_loop_ids: [],
    action_plan_markdown: "",
    owner_evidence_edits: [],
    approvals: [],
    execution_records: [],
    initiatives: [],
    question_suggestions: [],
    input_sources: [],
  };
  const candidate: Record<string, unknown> = { ...value };
  for (const [field, fallback] of Object.entries(legacyDefaults)) {
    if (!(field in candidate)) candidate[field] = fallback;
  }
  return isSavedWorkspaceDocument(candidate) ? candidate : null;
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
  if (typeof window === "undefined") return { status: "skipped", bytes: 0, location: "browser" };
  const serialized = JSON.stringify(state);
  const bytes = new TextEncoder().encode(serialized).byteLength;
  if (bytes > MAX_WORKSPACE_STORAGE_BYTES) {
    return { status: "error", code: "size_limit", message: "Workspace data exceeds the 4 MB browser-local storage limit.", bytes, location: "browser" };
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, serialized);
    return { status: "saved", bytes, location: "browser" };
  } catch {
    return { status: "error", code: "storage_unavailable", message: "Browser-local storage is unavailable or full. Export the workspace before leaving this page.", bytes, location: "browser" };
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

export function createWorkspace(user: EnterpriseUser, name: string, useCase: UseCaseInput = EMPTY_WORKSPACE_USE_CASE): SavedWorkspace {
  const timestamp = nowIso();
  return {
    workspace_id: uid("workspace"),
    name: name.trim() || "New Use Case Workspace",
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

export function useWorkspaceStore(options: WorkspaceStoreOptions = {}) {
  const mode = options.mode ?? deploymentPosture.mode;
  const posture = options.posture ?? deploymentPosture;
  const authority = options.authority ?? DEFAULT_AUTHORITY_ADAPTER;
  const saveDebounceMs = options.saveDebounceMs ?? 400;
  const [state, setState] = useState<WorkspaceState>(() => mode === "enterprise" ? EMPTY_STATE : loadWorkspaceState());
  const [persistence, setPersistence] = useState<WorkspacePersistenceResult>({
    status: "skipped",
    bytes: 0,
    location: mode === "enterprise" ? "authority" : "browser",
  });
  const [enterpriseSession, setEnterpriseSession] = useState<EnterpriseSessionState>({
    status: mode === "enterprise" ? "loading" : "idle",
  });
  const [runtimeEvidence, setRuntimeEvidence] = useState<DeploymentRuntimeEvidence>({});
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [persistenceAttempt, setPersistenceAttempt] = useState(0);
  const tokenRef = useRef<string | null>(null);
  const revisionsRef = useRef(new Map<string, number>());
  const synchronizedDocumentsRef = useRef(new Map<string, string>());
  const authorityHydratedRef = useRef(false);
  const bootstrapGenerationRef = useRef(0);
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    if (mode !== "enterprise") {
      setPersistence(saveWorkspaceState(state));
      return;
    }
    if (!authorityHydratedRef.current || enterpriseSession.status !== "ready" || !tokenRef.current) return;

    const snapshot = state.workspaces;
    const timeout = window.setTimeout(() => {
      saveQueueRef.current = saveQueueRef.current.then(async () => {
        const token = tokenRef.current;
        if (!token) return;
        try {
          const currentIds = new Set(snapshot.map((workspace) => workspace.workspace_id));
          for (const [workspaceId, revision] of [...revisionsRef.current.entries()]) {
            if (currentIds.has(workspaceId)) continue;
            await authority.deleteWorkspace(token, workspaceId, revision);
            revisionsRef.current.delete(workspaceId);
            synchronizedDocumentsRef.current.delete(workspaceId);
          }

          for (const workspace of snapshot) {
            const serialized = JSON.stringify(workspace);
            if (synchronizedDocumentsRef.current.get(workspace.workspace_id) === serialized) continue;
            const revision = revisionsRef.current.get(workspace.workspace_id);
            const record = revision === undefined
              ? await authority.createWorkspace(token, workspace)
              : await authority.updateWorkspace(token, workspace, revision);
            revisionsRef.current.set(workspace.workspace_id, record.revision);
            synchronizedDocumentsRef.current.set(workspace.workspace_id, JSON.stringify(record.document));
          }

          const bytes = new TextEncoder().encode(JSON.stringify(snapshot)).byteLength;
          setPersistence({
            status: "saved",
            bytes,
            location: "authority",
            message: "Saved to tenant-scoped authoritative storage.",
          });
        } catch (error) {
          const conflict = error instanceof AuthorityError && error.status === 409;
          const sessionExpired = error instanceof AuthorityError && error.status === 401;
          const unauthorized = sessionExpired || (error instanceof AuthorityError && error.status === 403);
          if (sessionExpired) {
            tokenRef.current = null;
            authorityHydratedRef.current = false;
            setRuntimeEvidence((current) => ({ ...current, sessionVerified: false }));
            setEnterpriseSession({
              status: "error",
              error: "The enterprise identity session expired. Re-verify before saving.",
              retryable: true,
            });
          }
          setPersistence({
            status: "error",
            code: conflict ? "authority_conflict" : unauthorized ? "authority_unauthorized" : "authority_unavailable",
            message: conflict
              ? "This workspace changed elsewhere. Reload authoritative state before making another edit."
              : sessionExpired
                ? "The enterprise identity session expired. Re-verify before saving."
              : unauthorized
                ? "The verified enterprise identity is not authorized to persist this workspace."
                : error instanceof Error ? error.message : "Authoritative workspace persistence failed.",
            bytes: new TextEncoder().encode(JSON.stringify(snapshot)).byteLength,
            location: "authority",
          });
        }
      });
    }, saveDebounceMs);
    return () => window.clearTimeout(timeout);
  }, [authority, enterpriseSession.status, mode, persistenceAttempt, saveDebounceMs, state]);

  useEffect(() => {
    if (mode !== "enterprise") return;
    const bootstrapGeneration = bootstrapGenerationRef.current + 1;
    bootstrapGenerationRef.current = bootstrapGeneration;
    let cancelled = false;
    const isCurrentBootstrap = () => !cancelled && bootstrapGeneration === bootstrapGenerationRef.current;
    authorityHydratedRef.current = false;
    tokenRef.current = null;
    revisionsRef.current.clear();
    synchronizedDocumentsRef.current.clear();
    setEnterpriseSession({ status: "loading" });
    setPersistence({ status: "skipped", bytes: 0, location: "authority", message: "Verifying enterprise identity and loading authoritative workspaces." });

    if (posture.mode === "enterprise" && posture.blockers.length > 0) {
      setEnterpriseSession({
        status: "error",
        error: "Enterprise activation bindings are incomplete; authority bootstrap was not attempted.",
        retryable: false,
      });
      setPersistence({
        status: "error",
        code: "authority_unavailable",
        message: "Configure every blocked enterprise binding before connecting to the authority plane.",
        bytes: 0,
        location: "authority",
      });
      return () => {
        cancelled = true;
      };
    }

    void (async () => {
      let readinessEvidence: DeploymentRuntimeEvidence = {};
      let readiness: AuthorityReadiness | undefined;
      let retryableFailure = false;
      try {
        if (!authority.checkReadiness) {
          throw new AuthorityError("Enterprise readiness verification is unavailable.");
        }
        try {
          readiness = await authority.checkReadiness();
          readinessEvidence = runtimeEvidenceFromReadiness(readiness, posture);
        } catch (error) {
          retryableFailure = !(error instanceof AuthorityError)
            || (error.status !== undefined && error.status >= 500);
          readinessEvidence = {
            apiReachable: error instanceof AuthorityError && error.status !== undefined,
            persistenceVerified: false,
            auditVerified: false,
            retentionVerified: false,
            supportVerified: false,
            outboundPolicyVerified: false,
            backupRestoreVerified: false,
            workerVerified: false,
          };
          throw error;
        }
        if (!isCurrentBootstrap()) return;
        setRuntimeEvidence(readinessEvidence);
        if (readinessEvidence.configurationVerified === false) {
          throw new AuthorityError("Authority configuration does not match this UI build.");
        }
        const readinessFailures = readinessProofFailures(readiness, posture);
        if (readinessFailures.length > 0) {
          throw new AuthorityError(`Authority readiness proof is incomplete: ${readinessFailures.join(", ")}.`);
        }
        retryableFailure = true;
        const session = await authority.createSession();
        if (!isCurrentBootstrap()) return;
        const records = await authority.listWorkspaces(session.access_token);
        if (!isCurrentBootstrap()) return;
        if (records.some((record) => record.tenant_id !== session.actor.tenant_id)) {
          throw new AuthorityError("Authority returned a workspace for a different tenant.");
        }
        const user: EnterpriseUser = {
          user_id: session.actor.user_id,
          name: session.actor.name,
          email: session.actor.email ?? "",
          role: session.actor.role,
          signed_in_at: nowIso(),
        };
        const normalized = records
          .map((record) => normalizeWorkspaceState({ workspaces: [record.document] }).workspaces[0] ?? null)
          .filter((workspace): workspace is SavedWorkspace => workspace !== null);
        if (normalized.length !== records.length) {
          throw new AuthorityError("Authority returned a malformed workspace document.");
        }
        if (!isCurrentBootstrap()) return;
        for (const record of records) {
          revisionsRef.current.set(record.workspace_id, record.revision);
          synchronizedDocumentsRef.current.set(record.workspace_id, JSON.stringify(record.document));
        }
        tokenRef.current = session.access_token;
        authorityHydratedRef.current = true;
        setState({
          current_user: user,
          active_workspace_id: normalized[0]?.workspace_id ?? null,
          workspaces: normalized,
        });
        setRuntimeEvidence({
          ...readinessEvidence,
          apiReachable: true,
          sessionVerified: true,
          persistenceVerified: true,
          auditVerified: readinessEvidence.auditVerified === true,
          retentionVerified: readinessEvidence.retentionVerified === true,
          supportVerified: readinessEvidence.supportVerified === true,
          outboundPolicyVerified: readinessEvidence.outboundPolicyVerified === true,
          backupRestoreVerified: readinessEvidence.backupRestoreVerified === true,
          workerVerified: readinessEvidence.workerVerified === true,
        });
        setEnterpriseSession({ status: "ready" });
      } catch (error) {
        if (!isCurrentBootstrap()) return;
        setState(EMPTY_STATE);
        setRuntimeEvidence({
          ...readinessEvidence,
          sessionVerified: false,
          persistenceVerified: false,
        });
        setEnterpriseSession({
          status: "error",
          error: error instanceof Error ? error.message : "Enterprise identity verification failed.",
          retryable: retryableFailure,
        });
        setPersistence({
          status: "error",
          code: error instanceof AuthorityError && (error.status === 401 || error.status === 403) ? "authority_unauthorized" : "authority_unavailable",
          message: error instanceof Error ? error.message : "Enterprise identity verification failed.",
          bytes: 0,
          location: "authority",
        });
      }
    })();

    return () => {
      cancelled = true;
      if (bootstrapGenerationRef.current === bootstrapGeneration) bootstrapGenerationRef.current += 1;
    };
  }, [authority, mode, sessionAttempt]);

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
    if (mode === "enterprise") return;
    setState((current) => {
      const user = createUser(name, email, role);
      const hasWorkspace = current.workspaces.length > 0;
      const firstWorkspace = hasWorkspace ? current.workspaces[0] : createWorkspace(user, "New Use Case Workspace");
      return {
        ...current,
        current_user: user,
        active_workspace_id: current.active_workspace_id ?? firstWorkspace.workspace_id,
        workspaces: hasWorkspace ? current.workspaces : [firstWorkspace],
      };
    });
  }, [mode]);

  const signOut = useCallback(() => {
    if (mode === "enterprise") {
      bootstrapGenerationRef.current += 1;
      tokenRef.current = null;
      authorityHydratedRef.current = false;
      revisionsRef.current.clear();
      synchronizedDocumentsRef.current.clear();
      setEnterpriseSession({ status: "idle" });
      setState(EMPTY_STATE);
      return;
    }
    setState((current) => ({ ...current, current_user: null }));
  }, [mode]);

  const retryEnterpriseSignIn = useCallback(() => {
    if (mode === "enterprise") setSessionAttempt((attempt) => attempt + 1);
  }, [mode]);

  const retryPersistence = useCallback(() => {
    if (mode !== "enterprise" || enterpriseSession.status !== "ready" || !tokenRef.current || !authorityHydratedRef.current) return;
    setPersistence((current) => ({
      ...current,
      status: "skipped",
      message: "Retrying the authoritative workspace save.",
    }));
    setPersistenceAttempt((attempt) => attempt + 1);
  }, [enterpriseSession.status, mode]);

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
    enterpriseSession,
    runtimeEvidence,
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
    retryEnterpriseSignIn,
    retryPersistence,
  };
}
