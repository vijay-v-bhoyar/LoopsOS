export type DeploymentMode = "evaluation" | "enterprise";
export type DeploymentStatus = "evaluation_only" | "activation_blocked" | "verification_required" | "enterprise_ready";
export type BindingStatus = "bound" | "review" | "blocked";

export interface AuthorityConfigurationContract {
  allowed_http_hosts: string[];
  outbound_policy_mode: "allowlist" | "deny_all" | null;
  retention_policy_url: string | null;
  support_contact: string | null;
  backup_restore_evidence_url: string | null;
}

export interface DeploymentRuntimeEvidence {
  apiReachable?: boolean;
  configurationVerified?: boolean;
  credentialInjectionBrokerVerified?: boolean;
  rateLimitVerified?: boolean;
  sessionVerified?: boolean;
  persistenceVerified?: boolean;
  auditVerified?: boolean;
  retentionVerified?: boolean;
  supportVerified?: boolean;
  outboundPolicyVerified?: boolean;
  backupRestoreVerified?: boolean;
  workerVerified?: boolean;
}

export interface DeploymentBinding {
  id: "identity" | "persistence" | "audit" | "transport" | "configuration" | "credential_injection" | "retention" | "support" | "outbound_policy" | "backup_restore" | "worker" | "rate_limit";
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
  authorityAllowedHosts: string[];
  allowedEndpointHosts: string[];
  outboundPolicyMode: string;
  retentionPolicyUrl: string;
  supportContact: string;
  backupRestoreEvidenceUrl: string;
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
  // Reject protocol-relative and backslash-normalized URLs before treating a
  // leading slash as a same-origin path. Query and fragment components are
  // rejected so bindings cannot carry secrets or ambiguous routing state.
  if (location.startsWith("/")) {
    return (
      !location.startsWith("//")
      && !location.includes("\\")
      && !location.includes("?")
      && !location.includes("#")
    );
  }
  try {
    const url = new URL(location);
    const safeComponents = !url.username && !url.password && !url.search && !url.hash && !location.includes("\\");
    return safeComponents && (
      url.protocol === "https:"
      || (url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1"))
    );
  } catch {
    return false;
  }
}

export function isUnsafeAuthorityHostname(hostname: string): boolean {
  const normalized = hostname.replace(/^\[|\]$/g, "").toLowerCase().replace(/\.+$/, "");
  if (!normalized || normalized === "localhost" || normalized.endsWith(".localhost") || normalized === "::1") return true;
  const octets = normalized.split(".").map(Number);
  const isIpv4 = octets.length === 4
    && octets.every((octet) => Number.isInteger(octet) && octet >= 0 && octet <= 255);
  if (isIpv4) {
    const [first, second, third] = octets;
    return first === 0
      || first === 10
      || first === 127
      || (first === 100 && second >= 64 && second <= 127)
      || (first === 169 && second === 254)
      || (first === 172 && second >= 16 && second <= 31)
      || (first === 192 && (second === 0 || second === 168))
      || (first === 198 && (second === 18 || second === 19 || (second === 51 && third === 100)))
      || (first === 203 && second === 0 && third === 113)
      || first >= 224;
  }
  return normalized.startsWith("::")
    || normalized.startsWith("fc")
    || normalized.startsWith("fd")
    || /^(fe[89ab])/.test(normalized)
    || normalized.startsWith("ff")
    || normalized.startsWith("2001:db8");
}

function isAllowedAuthorityLocation(location: string, allowedHosts: string[]): boolean {
  if (!isSecureLocation(location)) return false;
  if (location.startsWith("/")) return location === "/api" || location === "/api/";
  try {
    const url = new URL(location);
    const normalizedHosts = allowedHosts.map((host) => host.trim().toLowerCase()).filter(Boolean);
    const authorityPath = url.pathname === "/api" || url.pathname === "/api/";
    return authorityPath
      && !isUnsafeAuthorityHostname(url.hostname)
      && (normalizedHosts.includes(url.hostname.toLowerCase()) || normalizedHosts.includes(url.host.toLowerCase()));
  } catch {
    return false;
  }
}

function isSecureEvidenceLocation(location: string): boolean {
  if (!location || location.startsWith("/")) return false;
  try {
    const url = new URL(location);
    return url.protocol === "https:"
      && !isUnsafeAuthorityHostname(url.hostname)
      && !url.username
      && !url.password
      && !url.search
      && !url.hash
      && !location.includes("\\");
  } catch {
    return false;
  }
}

export function authorityConfigurationMatches(
  posture: Pick<DeploymentPosture, "mode" | "allowedEndpointHosts" | "outboundPolicyMode" | "retentionPolicyUrl" | "supportContact" | "backupRestoreEvidenceUrl">,
  contract: AuthorityConfigurationContract,
): boolean {
  if (posture.mode !== "enterprise") return true;
  const authorityHosts = new Set(contract.allowed_http_hosts.map((host) => host.trim().toLowerCase()).filter(Boolean));
  const endpointHosts = new Set(posture.allowedEndpointHosts.map((host) => host.trim().toLowerCase()).filter(Boolean));
  const authorityHostPolicyMatches = contract.outbound_policy_mode === "deny_all"
    ? authorityHosts.size === 0
    : contract.outbound_policy_mode === "allowlist" && authorityHosts.size > 0;
  const endpointHostsMatch = posture.outboundPolicyMode === "deny_all"
    ? endpointHosts.size === 0 && authorityHosts.size === 0
    : endpointHosts.size > 0
      && endpointHosts.size === authorityHosts.size
      && [...endpointHosts].every((host) => authorityHosts.has(host));
  return (contract.outbound_policy_mode ?? "") === posture.outboundPolicyMode
    && authorityHostPolicyMatches
    && (contract.retention_policy_url ?? "") === posture.retentionPolicyUrl
    && (contract.support_contact ?? "") === posture.supportContact
    && (contract.backup_restore_evidence_url ?? "") === posture.backupRestoreEvidenceUrl
    && endpointHostsMatch;
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
  const credentialInjectionMode = value(env, "VITE_LOOPOS_CREDENTIAL_INJECTION_MODE");
  const retentionPolicy = value(env, "VITE_LOOPOS_RETENTION_POLICY_URL");
  const supportContact = value(env, "VITE_LOOPOS_SUPPORT_CONTACT");
  const outboundPolicyMode = value(env, "VITE_LOOPOS_OUTBOUND_POLICY_MODE");
  const backupRestoreEvidence = value(env, "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL");
  const authorityAllowedHosts = value(env, "VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST")
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter(Boolean);
  const allowedEndpointHosts = value(env, "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS")
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter(Boolean);

  const enterpriseDeclared = mode === "enterprise";
  const secureTransport = enterpriseDeclared && isAllowedAuthorityLocation(apiBaseUrl, authorityAllowedHosts);
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
    binding(
      "credential_injection",
      "Credential injection broker",
      enterpriseDeclared && credentialInjectionMode === "broker" && Boolean(apiBaseUrl),
      runtime.credentialInjectionBrokerVerified,
      "Configure the approved short-lived credential injection broker. Static bearer tokens are not supported.",
      "The credential broker is declared but its authority-side verification has not passed.",
      "The authority verified short-lived, tenant-bound credential injection.",
    ),
    binding(
      "worker",
      "Durable execution worker",
      enterpriseDeclared && persistenceMode === "api" && Boolean(apiBaseUrl),
      runtime.workerVerified,
      "Configure the durable execution worker and protected dispatch route.",
      "Execution persistence is declared but worker dispatch has not been verified by the authority.",
      "The authority verified durable worker dispatch and leased job storage.",
    ),
    binding(
      "rate_limit",
      "Request rate limiting",
      enterpriseDeclared && Boolean(apiBaseUrl),
      runtime.rateLimitVerified,
      "Configure a durable request limit and fixed window before enterprise activation.",
      "Request rate limiting is declared but the authority has not verified its production policy.",
      "The authority verified a durable request limit and fixed window.",
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
    {
      id: "configuration",
      label: "Cross-plane configuration",
      status: !enterpriseDeclared
        ? "bound"
        : runtime.configurationVerified === true
          ? "bound"
          : runtime.configurationVerified === false
            ? "blocked"
            : "review",
      detail: !enterpriseDeclared || runtime.configurationVerified === true
        ? "The compiled UI bindings match the authority configuration contract."
        : runtime.configurationVerified === false
          ? "The compiled UI bindings do not match the authority configuration contract."
          : "The authority configuration contract has not been verified against this UI build.",
    },
    binding(
      "retention",
      "Retention policy",
      enterpriseDeclared && isSecureEvidenceLocation(retentionPolicy),
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
      enterpriseDeclared && isSecureEvidenceLocation(backupRestoreEvidence),
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
    authorityAllowedHosts,
    allowedEndpointHosts,
    outboundPolicyMode,
    retentionPolicyUrl: retentionPolicy,
    supportContact,
    backupRestoreEvidenceUrl: backupRestoreEvidence,
    bindings,
    blockers,
    reviews,
  };
}

export const deploymentPosture = evaluateDeploymentPosture(import.meta.env as Environment);

export function deploymentPostureForRuntime(runtime: DeploymentRuntimeEvidence): DeploymentPosture {
  return evaluateDeploymentPosture(import.meta.env as Environment, runtime);
}
