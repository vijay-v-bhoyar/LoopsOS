import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  UI_ROOT,
  assertE2EIsolation,
  buildE2EEnvironment,
  completeIsolatedE2ERun,
  createIsolatedE2ERun,
  sanitizeE2EChildEnvironment,
  validatePlaywrightArgs,
} from "./e2e-isolation.mjs";

const suppliedArgs = process.argv.slice(2);
const enterpriseFlag = "--loopos-enterprise-gate";
const enterpriseGate = suppliedArgs[0] === enterpriseFlag;
if (suppliedArgs.some((arg, index) => arg === enterpriseFlag && index !== 0)) {
  throw new Error("The enterprise gate marker must be the first internal runner argument.");
}
const testArgs = validatePlaywrightArgs(enterpriseGate ? suppliedArgs.slice(1) : suppliedArgs);
const environment = buildE2EEnvironment(process.env, { enterpriseGate });

if (environment.LOOPOS_E2E_EFFECT_BUDGET_FIXTURE === "1") {
  if (enterpriseGate) throw new Error("Effect-budget fixtures are evaluation-only.");
  environment.LOOPOS_EFFECT_BUDGET_POLICY_JSON = JSON.stringify({
    version: 1,
    scope: "cumulative",
    policy_epoch: 1,
    tenants: {
      "local-evaluation": {
        ceilings: { dispatch_count: 10 },
        routes: ["actions", "compensate"].map((path) => ({
          endpoint: `https://unknown.example.com/${path}`,
          method: "POST",
          evidence_ref: "synthetic-browser-allowlist-negative",
          charges: [{ unit: "dispatch_count", fixed: 1 }],
        })),
      },
    },
  });
}

if (!enterpriseGate) {
  environment.LOOPOS_WEBHOOK_SECRETS_JSON = JSON.stringify({
    "local-evaluation:github": "loopos-e2e-webhook-fixture-secret",
    "loopos-e2e-desktop:github": "loopos-e2e-desktop-webhook-fixture-secret",
    "loopos-e2e-mobile:github": "loopos-e2e-mobile-webhook-fixture-secret",
  });
  environment.LOOPOS_GITHUB_RELEASE_ATTESTOR_APP_ID = "4242";
  environment.LOOPOS_GITHUB_RELEASE_WORKFLOW_IDS = "7007";
}

if (environment.LOOPOS_E2E_LLM_ATTESTATION_FIXTURE === "1") {
  if (enterpriseGate) throw new Error("LLM signing fixtures are evaluation-only.");
  if (environment.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS) throw new Error("Refusing to replace configured LLM trust with fixture trust.");
  const keys = JSON.parse(readFileSync(new URL("../src/test/llmAttestationKeys.json", import.meta.url), "utf8"));
  environment.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS = JSON.stringify([
    ["/api/mock-llm-questions", "loopos_use_case_questions"],
    ["/api/mock-field-enhancement", "loopos_use_case_structuring"],
  ].map(([endpoint, task]) => ({
    endpoint,
    task,
    fixture_only: true,
    provider: "fixture-provider",
    model: "fixture-model",
    model_revision: `sha256:${"a".repeat(64)}`,
    prompt_version: `${task}_v1`,
    prompt_sha256: "b".repeat(64),
    capability_profile_sha256: "c".repeat(64),
    evaluation_receipt_sha256: "d".repeat(64),
    capability_evaluated_at: new Date(Date.now() - 60_000).toISOString(),
    capability_expires_at: new Date(Date.now() + 86_400_000).toISOString(),
    lifecycle_status: "approved",
    key_id: "fixture-gateway-only",
    public_key_spki: keys.publicKeySpki,
  })));
}

const run = createIsolatedE2ERun();
Object.assign(environment, {
  LOOPOS_E2E_RUN_ID: run.runId,
  LOOPOS_E2E_RUNNER_PID: String(process.pid),
  LOOPOS_E2E_RUN_MANIFEST: run.manifestPath,
  LOOPOS_E2E_OUTPUT_DIR: run.artifactsDirectory,
  LOOPOS_DATABASE_PATH: run.databasePath,
});
const childEnvironment = sanitizeE2EChildEnvironment(environment);
assertE2EIsolation(childEnvironment);
console.log(`Isolated E2E run ${run.runId}; SQLite and Playwright artifacts are scoped to ${run.runDirectory}.`);

const playwrightCli = resolve(UI_ROOT, "node_modules", "playwright", "cli.js");
let child;
let exitCode = 1;
try {
  child = spawn(process.execPath, [playwrightCli, "test", ...testArgs], {
    cwd: UI_ROOT,
    env: childEnvironment,
    stdio: "inherit",
    windowsHide: true,
  });
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.once(signal, () => child?.kill(signal));
  }
  exitCode = await new Promise((resolveExit) => {
    child.once("error", (error) => {
      console.error(`Failed to launch Playwright: ${error.message}`);
      resolveExit(1);
    });
    child.once("exit", (code, signal) => resolveExit(code ?? (signal ? 1 : 0)));
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
} finally {
  completeIsolatedE2ERun(run, exitCode);
}

process.exitCode = exitCode;