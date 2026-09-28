import { randomUUID } from "node:crypto";
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const UI_ROOT = resolve(here, "..");
export const WORKSPACE_ROOT = resolve(UI_ROOT, "..");
const RUNS_ROOT = resolve(WORKSPACE_ROOT, "output", "loopsos-e2e");
const ISOLATION_VERSION = "1";
const WINDOWS_HOST_ENV = ["PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "USERPROFILE", "LOCALAPPDATA"];
const E2E_FLAGS = ["LOOPOS_E2E_LLM_ATTESTATION_FIXTURE", "LOOPOS_E2E_EFFECT_BUDGET_FIXTURE"];
const VITE_CONFIG_KEYS = [
  "VITE_LOOPOS_DEPLOYMENT_MODE",
  "VITE_LOOPOS_AUTHORITY_URL",
  "VITE_LOOPOS_AUTH_MODE",
  "VITE_LOOPOS_PERSISTENCE_MODE",
  "VITE_LOOPOS_AUDIT_MODE",
  "VITE_LOOPOS_CREDENTIAL_INJECTION_MODE",
  "VITE_LOOPOS_RETENTION_POLICY_URL",
  "VITE_LOOPOS_SUPPORT_CONTACT",
  "VITE_LOOPOS_OUTBOUND_POLICY_MODE",
  "VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS",
  "VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL",
];

function isWithin(parent, candidate) {
  const rel = relative(parent, candidate);
  return rel === "" || (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel));
}

function copyNonempty(target, source, key) {
  const value = source[key];
  if (typeof value === "string" && value.length > 0) target[key] = value;
}

function copySyntheticFixtureEnvironment(target, source) {
  if (source.VITE_LOOPOS_DEPLOYMENT_MODE !== "evaluation" || source.LOOPOS_E2E_ENTERPRISE_GATE === "1") return;
  const webhookSecrets = {
    "local-evaluation:github": "loopos-e2e-webhook-fixture-secret",
    "loopos-e2e-desktop:github": "loopos-e2e-desktop-webhook-fixture-secret",
    "loopos-e2e-mobile:github": "loopos-e2e-mobile-webhook-fixture-secret",
  };
  if (source.LOOPOS_WEBHOOK_SECRETS_JSON === JSON.stringify(webhookSecrets)) target.LOOPOS_WEBHOOK_SECRETS_JSON = source.LOOPOS_WEBHOOK_SECRETS_JSON;
  if (source.LOOPOS_GITHUB_RELEASE_ATTESTOR_APP_ID === "4242" && source.LOOPOS_GITHUB_RELEASE_WORKFLOW_IDS === "7007") {
    target.LOOPOS_GITHUB_RELEASE_ATTESTOR_APP_ID = "4242";
    target.LOOPOS_GITHUB_RELEASE_WORKFLOW_IDS = "7007";
  }
  if (source.LOOPOS_E2E_EFFECT_BUDGET_FIXTURE === "1" && source.LOOPOS_EFFECT_BUDGET_POLICY_JSON) {
    const policy = JSON.parse(source.LOOPOS_EFFECT_BUDGET_POLICY_JSON);
    const endpoints = policy?.tenants?.["local-evaluation"]?.routes?.map((route) => route.endpoint) ?? [];
    if (policy.version !== 1 || policy.scope !== "cumulative" || endpoints.length !== 2 || endpoints.some((endpoint) => !/^https:\/\/unknown\.example\.com\/(actions|compensate)$/.test(endpoint))) {
      throw new Error("Refusing non-synthetic effect-budget policy in isolated E2E.");
    }
    target.LOOPOS_EFFECT_BUDGET_POLICY_JSON = source.LOOPOS_EFFECT_BUDGET_POLICY_JSON;
  }
  if (source.LOOPOS_E2E_LLM_ATTESTATION_FIXTURE === "1" && source.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS) {
    const contracts = JSON.parse(source.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS);
    if (!Array.isArray(contracts) || contracts.length !== 2 || contracts.some((contract) => contract.fixture_only !== true || contract.provider !== "fixture-provider" || contract.model !== "fixture-model" || contract.key_id !== "fixture-gateway-only")) {
      throw new Error("Refusing non-synthetic LLM trust contracts in isolated E2E.");
    }
    target.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS = source.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS;
  }
}

function copyPythonPath(target, source) {
  const configured = typeof source.LOOPOS_PYTHON === "string" ? source.LOOPOS_PYTHON.trim() : "";
  if (!configured) return;
  if (!isAbsolute(configured) || !existsSync(configured)) {
    throw new Error("LOOPOS_PYTHON must be an existing absolute executable path for isolated E2E.");
  }
  target.LOOPOS_PYTHON = configured;
}

export function buildHostProcessEnvironment(source = process.env) {
  const environment = {};
  for (const key of WINDOWS_HOST_ENV) copyNonempty(environment, source, key);
  copyPythonPath(environment, source);
  return environment;
}

export function buildE2EEnvironment(source = process.env, { enterpriseGate = false } = {}) {
  const environment = buildHostProcessEnvironment(source);
  for (const key of E2E_FLAGS) {
    if (source[key] === "1") environment[key] = "1";
  }

  environment.BROWSER = "none";
  environment.LOOPOS_E2E_ISOLATION_VERSION = ISOLATION_VERSION;
  environment.LOOPOS_REPO_ROOT = WORKSPACE_ROOT;
  environment.LOOPOS_STORAGE_BACKEND = "sqlite";
  environment.LOOPOS_OUTBOUND_POLICY_MODE = "deny_all";
  environment.LOOPOS_ALLOWED_HTTP_HOSTS = "";
  environment.LOOPOS_CORS_ORIGINS = "http://127.0.0.1:4273,http://localhost:4273";
  environment.PYTHONDONTWRITEBYTECODE = "1";
  environment.PYTHONUTF8 = "1";

  environment.VITE_LOOPOS_DEPLOYMENT_MODE = enterpriseGate ? "enterprise" : "evaluation";
  environment.VITE_LOOPOS_AUTHORITY_URL = "/api";
  if (enterpriseGate) {
    Object.assign(environment, {
      LOOPOS_E2E_ENTERPRISE_GATE: "1",
      VITE_LOOPOS_AUTH_MODE: "bff-session",
      VITE_LOOPOS_PERSISTENCE_MODE: "api",
      VITE_LOOPOS_AUDIT_MODE: "server",
      VITE_LOOPOS_CREDENTIAL_INJECTION_MODE: "broker",
      VITE_LOOPOS_RETENTION_POLICY_URL: "https://policy.example.com/retention",
      VITE_LOOPOS_SUPPORT_CONTACT: "loopos-ops@example.com",
      VITE_LOOPOS_OUTBOUND_POLICY_MODE: "allowlist",
      VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS: "api.example.com",
      VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL: "https://evidence.example.com/restore-test",
    });
  }
  return environment;
}

export function sanitizeE2EChildEnvironment(source = process.env) {
  if (source.LOOPOS_E2E_ISOLATION_VERSION !== ISOLATION_VERSION) {
    throw new Error("E2E child process requires the isolated runner environment.");
  }
  const environment = buildHostProcessEnvironment(source);
  for (const key of E2E_FLAGS) {
    if (source[key] === "1") environment[key] = "1";
  }
  for (const key of VITE_CONFIG_KEYS) copyNonempty(environment, source, key);
  copySyntheticFixtureEnvironment(environment, source);
  for (const key of ["LOOPOS_E2E_RUN_ID", "LOOPOS_E2E_RUNNER_PID", "LOOPOS_E2E_RUN_MANIFEST", "LOOPOS_E2E_OUTPUT_DIR", "LOOPOS_DATABASE_PATH"]) {
    copyNonempty(environment, source, key);
  }
  Object.assign(environment, {
    BROWSER: "none",
    LOOPOS_E2E_ISOLATION_VERSION: ISOLATION_VERSION,
    LOOPOS_REPO_ROOT: WORKSPACE_ROOT,
    LOOPOS_STORAGE_BACKEND: "sqlite",
    LOOPOS_OUTBOUND_POLICY_MODE: "deny_all",
    LOOPOS_ALLOWED_HTTP_HOSTS: "",
    LOOPOS_CORS_ORIGINS: "http://127.0.0.1:4273,http://localhost:4273",
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONUTF8: "1",
  });
  if (source.LOOPOS_E2E_ENTERPRISE_GATE === "1") environment.LOOPOS_E2E_ENTERPRISE_GATE = "1";
  return environment;
}

function ensureSafeDirectory(root, target) {
  if (existsSync(target)) {
    const actual = realpathSync(target);
    if (!isWithin(root, actual)) throw new Error("E2E output path resolves outside the workspace.");
    return actual;
  }
  mkdirSync(target);
  const actual = realpathSync(target);
  if (!isWithin(root, actual)) throw new Error("E2E output path resolves outside the workspace.");
  return actual;
}

export function createIsolatedE2ERun({ workspaceRoot = WORKSPACE_ROOT, runnerPid = process.pid, now = new Date() } = {}) {
  const workspace = realpathSync(workspaceRoot);
  const outputRoot = ensureSafeDirectory(workspace, resolve(workspace, "output"));
  const runsRoot = ensureSafeDirectory(workspace, resolve(outputRoot, "loopsos-e2e"));
  const runId = randomUUID();
  const runDirectory = resolve(runsRoot, runId);
  mkdirSync(runDirectory);
  const actualRunDirectory = realpathSync(runDirectory);
  if (!isWithin(runsRoot, actualRunDirectory)) throw new Error("E2E run directory escaped its controlled output root.");

  const databasePath = resolve(actualRunDirectory, "authority.sqlite");
  const artifactsDirectory = resolve(actualRunDirectory, "playwright-output");
  const manifestPath = resolve(actualRunDirectory, "run-manifest.json");
  if (existsSync(databasePath) || existsSync(manifestPath)) throw new Error("Refusing to reuse an existing E2E database or manifest.");
  const manifest = {
    schema_version: 1,
    run_id: runId,
    runner_pid: runnerPid,
    created_at: now.toISOString(),
    status: "running",
    database_path: databasePath,
    artifacts_directory: artifactsDirectory,
  };
  const fd = openSync(manifestPath, "wx", 0o600);
  try {
    writeFileSync(fd, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  } finally {
    closeSync(fd);
  }
  return { runId, runDirectory: actualRunDirectory, databasePath, artifactsDirectory, manifestPath, manifest };
}

export function assertE2EIsolation(environment = process.env, { expectedParentPid, requireLiveRunner = true, workspaceRoot = WORKSPACE_ROOT } = {}) {
  if (environment.LOOPOS_E2E_ISOLATION_VERSION !== ISOLATION_VERSION) {
    throw new Error("Refusing E2E execution without the isolated runner marker.");
  }
  const manifestValue = environment.LOOPOS_E2E_RUN_MANIFEST;
  const databaseValue = environment.LOOPOS_DATABASE_PATH;
  const artifactsValue = environment.LOOPOS_E2E_OUTPUT_DIR;
  const runId = environment.LOOPOS_E2E_RUN_ID;
  const runnerPid = Number(environment.LOOPOS_E2E_RUNNER_PID);
  if (!manifestValue || !isAbsolute(manifestValue) || !databaseValue || !isAbsolute(databaseValue) || !artifactsValue || !isAbsolute(artifactsValue) || !runId || !Number.isSafeInteger(runnerPid) || runnerPid < 1) {
    throw new Error("E2E isolation manifest, run ID, runner identity, and absolute database path are required.");
  }
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(runId)) {
    throw new Error("E2E run ID is invalid.");
  }
  const workspace = realpathSync(workspaceRoot);
  const expectedRunsRoot = resolve(workspace, "output", "loopsos-e2e");
  const manifestPath = resolve(manifestValue);
  if (!existsSync(manifestPath)) throw new Error("E2E isolation manifest does not exist.");
  const realManifestPath = realpathSync(manifestPath);
  const runDirectory = dirname(realManifestPath);
  if (!isWithin(expectedRunsRoot, runDirectory) || basenameFor(runDirectory) !== runId) {
    throw new Error("E2E manifest is outside the run's controlled workspace directory.");
  }
  const expectedDatabasePath = resolve(runDirectory, "authority.sqlite");
  const expectedArtifactsDirectory = resolve(runDirectory, "playwright-output");
  if (resolve(databaseValue) !== expectedDatabasePath) throw new Error("E2E database path does not match the fresh run directory.");
  if (resolve(artifactsValue) !== expectedArtifactsDirectory) throw new Error("Playwright artifacts must stay in a child directory separate from the isolation manifest.");
  const manifest = JSON.parse(readFileSync(realManifestPath, "utf8"));
  if (manifest.schema_version !== 1 || manifest.run_id !== runId || manifest.runner_pid !== runnerPid || resolve(manifest.database_path) !== expectedDatabasePath || resolve(manifest.artifacts_directory) !== expectedArtifactsDirectory) {
    throw new Error("E2E isolation manifest does not match the child process environment.");
  }
  const age = Date.now() - Date.parse(manifest.created_at);
  if (!Number.isFinite(age) || age < -60_000 || age > 6 * 60 * 60 * 1000 || manifest.status !== "running") {
    throw new Error("E2E isolation manifest is stale or no longer active.");
  }
  if (expectedParentPid !== undefined && runnerPid !== expectedParentPid) {
    throw new Error("Playwright must be launched directly by the isolated E2E runner.");
  }
  if (requireLiveRunner) {
    try {
      process.kill(runnerPid, 0);
    } catch {
      throw new Error("E2E runner process is not alive.");
    }
  }
  return { runId, runDirectory, databasePath: expectedDatabasePath, artifactsDirectory: expectedArtifactsDirectory, manifestPath: realManifestPath, manifest };
}

function basenameFor(path) {
  return path.slice(path.lastIndexOf(sep) + 1);
}

export function completeIsolatedE2ERun(run, exitCode, finishedAt = new Date()) {
  const updated = { ...run.manifest, status: "completed", finished_at: finishedAt.toISOString(), exit_code: exitCode };
  writeFileSync(run.manifestPath, `${JSON.stringify(updated, null, 2)}\n`, { encoding: "utf8", flag: "w" });
  return updated;
}

export function validatePlaywrightArgs(args) {
  const accepted = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--project" || arg === "--grep" || arg === "--grep-invert") {
      const value = args[index + 1];
      if (!value || value.startsWith("-")) throw new Error(`${arg} requires a value.`);
      accepted.push(arg, value);
      index += 1;
      continue;
    }
    if (/^--(?:project|grep|grep-invert)=.+/.test(arg)) {
      accepted.push(arg);
      continue;
    }
    if (arg.startsWith("-")) throw new Error(`Unsupported E2E option: ${arg}`);
    const resolved = resolve(UI_ROOT, arg);
    const e2eRoot = resolve(UI_ROOT, "e2e");
    if (!isWithin(e2eRoot, resolved)) throw new Error(`E2E test target must stay inside ${e2eRoot}.`);
    accepted.push(arg);
  }
  return accepted;
}