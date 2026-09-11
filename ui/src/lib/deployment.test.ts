import { describe, expect, it } from "vitest";
import { authorityConfigurationMatches, evaluateDeploymentPosture } from "./deployment";

const enterpriseConfig = {
  VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise",
  VITE_LOOPOS_ENVIRONMENT_NAME: "Production",
  VITE_LOOPOS_API_BASE_URL: "https://loopos.example.com/api",
  VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST: "loopos.example.com",
  VITE_LOOPOS_AUTH_MODE: "bff-session",
  VITE_LOOPOS_PERSISTENCE_MODE: "api",
  VITE_LOOPOS_AUDIT_MODE: "server",
  VITE_LOOPOS_CREDENTIAL_INJECTION_MODE: "broker",
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

  it("does not declare enterprise readiness without a verified credential broker", () => {
    const posture = evaluateDeploymentPosture(enterpriseConfig, {
      apiReachable: true,
      configurationVerified: true,
      credentialInjectionBrokerVerified: false,
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

    expect(posture.enterpriseReady).toBe(false);
    expect(posture.reviews).toContain("credential_injection");
  });

  it("rejects an insecure remote enterprise API", () => {
    const posture = evaluateDeploymentPosture({ ...enterpriseConfig, VITE_LOOPOS_API_BASE_URL: "http://loopos.example.com/api" });

    expect(posture.enterpriseReady).toBe(false);
    expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
  });

  it("rejects a secure authority origin that is not explicitly allowlisted", () => {
    const posture = evaluateDeploymentPosture({ ...enterpriseConfig, VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST: "other.example.com" });

    expect(posture.enterpriseReady).toBe(false);
    expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
  });

  it("rejects local and non-global IP authority origins in enterprise mode", () => {
    for (const authorityUrl of [
      "https://localhost/api",
      "https://localhost./api",
      "https://foo.localhost/api",
      "https://127.0.0.1/api",
      "https://100.64.0.1/api",
      "https://[::1]/api",
      "https://[::ffff:127.0.0.1]/api",
      "https://[::]/api",
    ]) {
      const hostname = new URL(authorityUrl).hostname;
      const posture = evaluateDeploymentPosture({
        ...enterpriseConfig,
        VITE_LOOPOS_API_BASE_URL: authorityUrl,
        VITE_LOOPOS_AUTHORITY_HOST_ALLOWLIST: hostname,
      });

      expect(posture.enterpriseReady).toBe(false);
      expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
    }
  });

  it("rejects same-origin authority paths outside the Vercel API route", () => {
    const { VITE_LOOPOS_API_BASE_URL: _legacy, ...config } = enterpriseConfig;
    for (const authorityUrl of ["/wrong-route", "/api/v1"]) {
      const posture = evaluateDeploymentPosture({
        ...config,
        VITE_LOOPOS_AUTHORITY_URL: authorityUrl,
      });

      expect(posture.enterpriseReady).toBe(false);
      expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
    }
  });

  it("rejects remote authority paths outside the API route", () => {
    const { VITE_LOOPOS_API_BASE_URL: _legacy, ...config } = enterpriseConfig;
    for (const authorityUrl of [
      "https://loopos.example.com/wrong-route",
      "https://loopos.example.com/api/v1",
    ]) {
      const posture = evaluateDeploymentPosture({
        ...config,
        VITE_LOOPOS_AUTHORITY_URL: authorityUrl,
      });

      expect(posture.enterpriseReady).toBe(false);
      expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
    }
  });

  it("rejects relative retention and restore references", () => {
    const posture = evaluateDeploymentPosture({
      ...enterpriseConfig,
      VITE_LOOPOS_RETENTION_POLICY_URL: "/retention-policy",
      VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL: "/restore-evidence",
    });

    expect(posture.enterpriseReady).toBe(false);
    expect(posture.bindings.find((binding) => binding.id === "retention")?.status).toBe("blocked");
    expect(posture.bindings.find((binding) => binding.id === "backup_restore")?.status).toBe("blocked");
  });

  it("rejects local and non-global retention and restore references", () => {
    for (const evidenceUrl of [
      "https://localhost/retention",
      "https://localhost./retention",
      "https://service.localhost/retention",
      "https://127.0.0.1/retention",
      "https://100.64.0.1/retention",
      "https://192.0.2.1/retention",
      "https://[::1]/retention",
      "https://[::ffff:127.0.0.1]/retention",
    ]) {
      const posture = evaluateDeploymentPosture({
        ...enterpriseConfig,
        VITE_LOOPOS_RETENTION_POLICY_URL: evidenceUrl,
        VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL: evidenceUrl,
      });

      expect(posture.bindings.find((binding) => binding.id === "retention")?.status).toBe("blocked");
      expect(posture.bindings.find((binding) => binding.id === "backup_restore")?.status).toBe("blocked");
    }
  });

  it("rejects protocol-relative and backslash-normalized enterprise API URLs", () => {
    for (const apiBaseUrl of ["//untrusted.example/api", "/\\\\untrusted.example/api"]) {
      const posture = evaluateDeploymentPosture({ ...enterpriseConfig, VITE_LOOPOS_API_BASE_URL: apiBaseUrl });

      expect(posture.enterpriseReady).toBe(false);
      expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
    }
  });

  it("rejects credential-bearing, query-bearing, and fragment-bearing enterprise API URLs", () => {
    for (const apiBaseUrl of [
      "https://user:password@loopos.example.com/api",
      "https://loopos.example.com/api?token=secret",
      "https://loopos.example.com/api#fragment",
      "https://loopos.example.com\\api",
      "/api?token=secret",
      "/api#fragment",
    ]) {
      const posture = evaluateDeploymentPosture({ ...enterpriseConfig, VITE_LOOPOS_API_BASE_URL: apiBaseUrl });

      expect(posture.enterpriseReady).toBe(false);
      expect(posture.bindings.find((binding) => binding.id === "transport")?.status).toBe("blocked");
    }
  });

  it("uses the authority client URL as the canonical API binding", () => {
    const { VITE_LOOPOS_API_BASE_URL: _legacy, ...config } = enterpriseConfig;
    const posture = evaluateDeploymentPosture({
      ...config,
      VITE_LOOPOS_AUTHORITY_URL: "https://loopos.example.com/api",
    }, {
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

    expect(posture.apiBaseUrl).toBe("https://loopos.example.com/api");
    expect(posture.enterpriseReady).toBe(true);
  });

  it("requires runtime proof before declaring enterprise readiness", () => {
    const configured = evaluateDeploymentPosture(enterpriseConfig);
    expect(configured.status).toBe("verification_required");
    expect(configured.enterpriseReady).toBe(false);

    const verified = evaluateDeploymentPosture(enterpriseConfig, {
      apiReachable: true,
      configurationVerified: true,
      rateLimitVerified: true,
      sessionVerified: true,
      persistenceVerified: true,
      auditVerified: true,
      credentialInjectionBrokerVerified: true,
      retentionVerified: true,
      supportVerified: true,
      outboundPolicyVerified: true,
      backupRestoreVerified: true,
      workerVerified: true,
    });
    expect(verified.status).toBe("enterprise_ready");
    expect(verified.enterpriseReady).toBe(true);
    expect(verified.blockers).toEqual([]);
  });

  it("blocks readiness when the authority binding contract differs from the compiled UI", () => {
    const configured = evaluateDeploymentPosture(enterpriseConfig);
    const contract = {
      allowed_http_hosts: ["ai.example.com", "voice.example.com"],
      outbound_policy_mode: "allowlist" as const,
      retention_policy_url: "https://wrong.example/retention",
      support_contact: "loopos-ops@example.com",
      backup_restore_evidence_url: "https://evidence.example.com/restore-test",
    };

    expect(authorityConfigurationMatches(configured, contract)).toBe(false);
    const posture = evaluateDeploymentPosture(enterpriseConfig, {
      apiReachable: true,
      configurationVerified: false,
      rateLimitVerified: true,
      sessionVerified: true,
      persistenceVerified: true,
      auditVerified: true,
      credentialInjectionBrokerVerified: true,
      retentionVerified: true,
      supportVerified: true,
      outboundPolicyVerified: true,
      backupRestoreVerified: true,
      workerVerified: true,
    });
    expect(posture.status).toBe("activation_blocked");
    expect(posture.blockers).toContain("configuration");
  });

  it("accepts a matching authority binding contract", () => {
    const posture = evaluateDeploymentPosture(enterpriseConfig);

    expect(authorityConfigurationMatches(posture, {
      allowed_http_hosts: ["ai.example.com", "voice.example.com"],
      outbound_policy_mode: "allowlist",
      retention_policy_url: "https://policy.example.com/retention",
      support_contact: "loopos-ops@example.com",
      backup_restore_evidence_url: "https://evidence.example.com/restore-test",
    })).toBe(true);
  });

  it("rejects authority endpoint hosts missing from or extra to the UI binding", () => {
    const posture = evaluateDeploymentPosture(enterpriseConfig);
    const baseContract = {
      outbound_policy_mode: "allowlist" as const,
      retention_policy_url: "https://policy.example.com/retention",
      support_contact: "loopos-ops@example.com",
      backup_restore_evidence_url: "https://evidence.example.com/restore-test",
    };

    expect(authorityConfigurationMatches(posture, {
      ...baseContract,
      allowed_http_hosts: ["ai.example.com"],
    })).toBe(false);
    expect(authorityConfigurationMatches(posture, {
      ...baseContract,
      allowed_http_hosts: ["ai.example.com", "voice.example.com", "extra.example.com"],
    })).toBe(false);
  });

  it("accepts an explicitly verified deny-all outbound policy", () => {
    const posture = evaluateDeploymentPosture({
      ...enterpriseConfig,
      VITE_LOOPOS_OUTBOUND_POLICY_MODE: "deny_all",
      VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "",
    }, {
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

    expect(posture.bindings.find((binding) => binding.id === "outbound_policy")?.status).toBe("bound");
    expect(posture.enterpriseReady).toBe(true);
  });

  it("rejects a deny-all authority contract that still contains hosts", () => {
    const posture = evaluateDeploymentPosture({
      ...enterpriseConfig,
      VITE_LOOPOS_OUTBOUND_POLICY_MODE: "deny_all",
      VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "",
    });

    expect(authorityConfigurationMatches(posture, {
      allowed_http_hosts: ["127.0.0.1"],
      outbound_policy_mode: "deny_all",
      retention_policy_url: "https://policy.example.com/retention",
      support_contact: "loopos-ops@example.com",
      backup_restore_evidence_url: "https://evidence.example.com/restore-test",
    })).toBe(false);
  });
});
