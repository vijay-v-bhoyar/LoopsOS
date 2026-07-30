export type DeploymentMode = "evaluation" | "enterprise";
export type DeploymentStatus = "evaluation_only" | "activation_blocked" | "verification_required" | "enterprise_ready";
export type BindingStatus = "bound" | "review" | "blocked";

export interface DeploymentRuntimeEvidence {
  apiReachable?: boolean;
  sessionVerified?: boolean;
  persistenceVerified?: boolean;
  auditVerified?: boolean;
  retentionVerified?: boolean;
  supportVerified?: boolean;
  outboundPolicyVerified?: boolean;
  backupRestoreVerified?: boolean;
}

export interface DeploymentBinding {
  id: "identity" | "persistence" | "audit" | "transport" | "retention" | "support" | "outbound_policy" | "backup_restore";
  label: string;
  status: BindingStatus;
  detail: string;
}

export interface DeploymentPosture {
  mode: DeploymentMode;
  status: DeploymentStatus;
  enterpriseReady: boolean;
  environmentName: string;
  apiBaseUrl: string;
  allowedEndpointHosts: string[];
  bindings: DeploymentBinding[];
  blockers: string[];
  reviews: string[];
}

export const DEPLOYMENT_STATUS_LABELS: Record<DeploymentStatus, string> = {
  evaluation_only: "Evaluation only",
  activation_blocked: "Activation blocked",
  verification_required: "Verification required",
  enterprise_ready: "Enterprise ready",
};

type Environment = Record<string, string | boolean | undefined>;

function value(env: Environment, key: string): string {
  const candidate = env[key];
  return typeof candidate === "string" ? candidate.trim() : "";
}

function isSecureLocation(location: string): boolean {
  if (!location) return false;
  if (location.startsWith("/")) return true;
  try {
    const url = new URL(location);
    return url.protocol === "https:" || (url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1"));
  } catch {
    return false;
  }
}

function binding(
  id: DeploymentBinding["id"],
  label: string,
  configured: boolean,
  verified: boolean | undefined,
  blockedDetail: string,
  reviewDetail: string,
  boundDetail: string,
): DeploymentBinding {
  if (!configured) return { id, label, status: "blocked", detail: blockedDetail };
  if (verified === false || verified === undefined) return { id, label, status: "review", detail: reviewDetail };
  return { id, label, status: "bound", detail: boundDetail };
}

export function evaluateDeploymentPosture(env: Environment, runtime: DeploymentRuntimeEvidence = {}): DeploymentPosture {
  const mode: DeploymentMode = value(env, "VITE_LOOPOS_DEPLOYMENT_MODE").toLowerCase() === "enterprise" ? "enterprise" : "evaluation";
  const apiBaseUrl = value(env, "VITE_LOOPOS_AUTHORITY_URL") || value(env, "VITE_LOOPOS_API_BASE_URL");
  const authMode = value(env, "VITE_LOOPOS_AUTH_MODE");
  const persistenceMode = value(env, "VITE_LOOPOS_PERSISTENCE_MODE");
  const auditMode = value(env, "VITE_LOOPOS_AUDIT_MODE");
  const retentionPolicy = value(env, "VITE_LOOPOS_RETENTION_POLICY_URL");
  const supportContact = value(env, "VITE_LOOPOS_SUPPORT_CONTACT");
  const outboundPolicyMode = value(env, "VITE_LOOPOS_OUTBOUND_POLICY_MODE");
  const backupRestoreEvidence = value(env, "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL");
  const allowedEndpointHosts = value(env, "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS")
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter(Boolean);

  const enterpriseDeclared = mode === "enterprise";
  const secureTransport = enterpriseDeclared && isSecureLocation(apiBaseUrl);
  const bindings: DeploymentBinding[] = [
    binding(
      "identity",
      "Enterprise identity",
      enterpriseDeclared && authMode === "bff-session" && Boolean(apiBaseUrl),
      runtime.sessionVerified,
      "Configure a server-managed BFF session. Browser-selected roles are evaluation-only.",
      "Identity is declared but the current session has not been verified by the authority plane.",
      "The authority plane verified the signed-in identity and role claims.",
    ),
    binding(
      "persistence",
      "Authoritative persistence",
      enterpriseDeclared && persistenceMode === "api" && Boolean(apiBaseUrl),
      runtime.persistenceVerified,
      "Configure tenant-scoped API persistence. Browser storage is not authoritative.",
      "Persistence is declared but read/write and tenant-isolation probes have not passed.",
      "The tenant-scoped persistence probe passed.",
    ),
    binding(
      "audit",
      "Append-only audit",
      enterpriseDeclared && auditMode === "server" && Boolean(apiBaseUrl),
      runtime.auditVerified,
      "Configure a server-side append-only audit sink for approvals and execution records.",
      "Audit is declared but event write and retrieval probes have not passed.",
      "The append-only audit probe passed.",
    ),
    {
      id: "transport",
      label: "Secure transport",
      status: secureTransport ? (runtime.apiReachable ? "bound" : "review") : "blocked",
      detail: secureTransport
        ? runtime.apiReachable
          ? "The authoritative API is reachable over an approved secure origin."
          : "The API origin is secure, but runtime reachability has not been proven."
        : "Use HTTPS for every non-local authoritative API origin.",
    },
    binding(
      "retention",
      "Retention policy",
      enterpriseDeclared && isSecureLocation(retentionPolicy),
      runtime.retentionVerified,
      "Configure the approved retention and deletion policy URL.",
      "Retention is declared but the authority has not verified its server-side binding.",
      "The authority verified the server-side retention-policy binding.",
    ),
    binding(
      "support",
      "Operational ownership",
      enterpriseDeclared && Boolean(supportContact),
      runtime.supportVerified,
      "Configure the accountable operational support contact.",
      "Operational ownership is declared but the authority has not verified its server-side binding.",
      `The authority verified operational ownership for ${supportContact}.`,
    ),
    binding(
      "outbound_policy",
      "Outbound endpoint policy",
      enterpriseDeclared && (
        outboundPolicyMode === "deny_all"
        || (outboundPolicyMode === "allowlist" && allowedEndpointHosts.length > 0)
      ),
      runtime.outboundPolicyVerified,
      "Configure deny-all or an explicit host allowlist for outbound services.",
      "Outbound policy is declared but the authority has not verified its server-side enforcement.",
      outboundPolicyMode === "deny_all"
        ? "The authority verified a deny-all outbound policy."
        : `The authority verified an allowlist with ${allowedEndpointHosts.length} host${allowedEndpointHosts.length === 1 ? "" : "s"}.`,
    ),
    binding(
      "backup_restore",
      "Backup and restore",
      enterpriseDeclared && isSecureLocation(backupRestoreEvidence),
      runtime.backupRestoreVerified,
      "Configure a secure reference to the latest approved backup/restore exercise.",
      "Restore evidence is declared but is missing, invalid, or older than the server freshness policy.",
      "The authority verified a recent backup/restore evidence binding.",
    ),
  ];

  const blockers = bindings.filter((item) => item.status === "blocked").map((item) => item.id);
  const reviews = bindings.filter((item) => item.status === "review").map((item) => item.id);
  const status: DeploymentStatus = mode === "evaluation"
    ? "evaluation_only"
    : blockers.length
      ? "activation_blocked"
      : reviews.length
        ? "verification_required"
        : "enterprise_ready";

  return {
    mode,
    status,
    enterpriseReady: status === "enterprise_ready",
    environmentName: value(env, "VITE_LOOPOS_ENVIRONMENT_NAME") || (mode === "enterprise" ? "Enterprise" : "Local evaluation"),
    apiBaseUrl,
    allowedEndpointHosts,
    bindings,
    blockers,
    reviews,
  };
}

export const deploymentPosture = evaluateDeploymentPosture(import.meta.env as Environment);

export function deploymentPostureForRuntime(runtime: DeploymentRuntimeEvidence): DeploymentPosture {
  return evaluateDeploymentPosture(import.meta.env as Environment, runtime);
}
