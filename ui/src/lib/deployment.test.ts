import { describe, expect, it } from "vitest";
import { evaluateDeploymentPosture } from "./deployment";

const enterpriseConfig = {
  VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise",
  VITE_LOOPOS_ENVIRONMENT_NAME: "Production",
  VITE_LOOPOS_API_BASE_URL: "https://loopos.example.com/api",
  VITE_LOOPOS_AUTH_MODE: "bff-session",
  VITE_LOOPOS_PERSISTENCE_MODE: "api",
  VITE_LOOPOS_AUDIT_MODE: "server",
  VITE_LOOPOS_RETENTION_POLICY_URL: "https://policy.example.com/retention",
  VITE_LOOPOS_SUPPORT_CONTACT: "loopos-ops@example.com",
  VITE_LOOPOS_OUTBOUND_POLICY_MODE: "allowlist",
  VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "ai.example.com,voice.example.com",
  VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL: "https://evidence.example.com/restore-test",
};

describe("evaluateDeploymentPosture", () => {
  it("keeps the default browser-local build in evaluation mode", () => {
    const posture = evaluateDeploymentPosture({});

    expect(posture.mode).toBe("evaluation");
    expect(posture.status).toBe("evaluation_only");
    expect(posture.enterpriseReady).toBe(false);
    expect(posture.blockers).toContain("identity");
    expect(posture.blockers).toContain("persistence");
    expect(posture.blockers).toContain("audit");
  });

  it("fails closed when enterprise mode is missing authoritative bindings", () => {
    const posture = evaluateDeploymentPosture({ VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise" });

    expect(posture.status).toBe("activation_blocked");
    expect(posture.bindings.find((binding) => binding.id === "identity")?.status).toBe("blocked");
    expect(posture.bindings.find((binding) => binding.id === "retention")?.status).toBe("blocked");
  });

  it("rejects an insecure remote enterprise API", () => {
    const posture = evaluateDeploymentPosture({ ...enterpriseConfig, VITE_LOOPOS_API_BASE_URL: "http://loopos.example.com/api" });

    expect(posture.enterpriseReady).toBe(false);
    expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
  });

  it("uses the authority client URL as the canonical API binding", () => {
    const { VITE_LOOPOS_API_BASE_URL: _legacy, ...config } = enterpriseConfig;
    const posture = evaluateDeploymentPosture({
      ...config,
      VITE_LOOPOS_AUTHORITY_URL: "https://loopos.example.com/api",
    }, {
      apiReachable: true,
      sessionVerified: true,
      persistenceVerified: true,
      auditVerified: true,
      retentionVerified: true,
      supportVerified: true,
      outboundPolicyVerified: true,
      backupRestoreVerified: true,
    });

    expect(posture.apiBaseUrl).toBe("https://loopos.example.com/api");
    expect(posture.enterpriseReady).toBe(true);
  });

  it("requires runtime proof before declaring enterprise readiness", () => {
    const configured = evaluateDeploymentPosture(enterpriseConfig);
    expect(configured.status).toBe("verification_required");
    expect(configured.enterpriseReady).toBe(false);

    const verified = evaluateDeploymentPosture(enterpriseConfig, {
      apiReachable: true,
      sessionVerified: true,
      persistenceVerified: true,
      auditVerified: true,
      retentionVerified: true,
      supportVerified: true,
      outboundPolicyVerified: true,
      backupRestoreVerified: true,
    });
    expect(verified.status).toBe("enterprise_ready");
    expect(verified.enterpriseReady).toBe(true);
    expect(verified.blockers).toEqual([]);
  });

  it("accepts an explicitly verified deny-all outbound policy", () => {
    const posture = evaluateDeploymentPosture({
      ...enterpriseConfig,
      VITE_LOOPOS_OUTBOUND_POLICY_MODE: "deny_all",
      VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "",
    }, {
      apiReachable: true,
      sessionVerified: true,
      persistenceVerified: true,
      auditVerified: true,
      retentionVerified: true,
      supportVerified: true,
      outboundPolicyVerified: true,
      backupRestoreVerified: true,
    });

    expect(posture.bindings.find((binding) => binding.id === "outbound_policy")?.status).toBe("bound");
    expect(posture.enterpriseReady).toBe(true);
  });
});
