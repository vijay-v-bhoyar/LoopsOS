import { spawn } from "node:child_process";

const environment = {
  ...process.env,
  LOOPOS_E2E_ENTERPRISE_GATE: "1",
  VITE_LOOPOS_DEPLOYMENT_MODE: "enterprise",
  VITE_LOOPOS_AUTHORITY_URL: "/api",
  VITE_LOOPOS_AUTH_MODE: "bff-session",
  VITE_LOOPOS_PERSISTENCE_MODE: "api",
  VITE_LOOPOS_AUDIT_MODE: "server",
  VITE_LOOPOS_RETENTION_POLICY_URL: "https://policy.example.com/retention",
  VITE_LOOPOS_SUPPORT_CONTACT: "loopos-ops@example.com",
  VITE_LOOPOS_OUTBOUND_POLICY_MODE: "allowlist",
  VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "api.example.com",
  VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL: "https://evidence.example.com/restore-test",
};

const child = spawn(process.execPath, ["scripts/run-e2e.mjs", "e2e/enterprise-readiness-gate.spec.ts"], {
  cwd: process.cwd(),
  env: environment,
  stdio: "inherit",
  windowsHide: true,
});

child.once("error", (error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});

child.once("exit", (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
