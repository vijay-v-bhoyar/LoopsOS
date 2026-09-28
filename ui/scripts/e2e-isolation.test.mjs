import assert from "node:assert/strict";
import { after, test } from "node:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve, sep } from "node:path";
import {
  assertE2EIsolation,
  buildE2EEnvironment,
  completeIsolatedE2ERun,
  createIsolatedE2ERun,
  sanitizeE2EChildEnvironment,
  validatePlaywrightArgs,
} from "./e2e-isolation.mjs";

const tempRoot = mkdtempSync(join(tmpdir(), "loopsos-e2e-isolation-test-"));
after(() => {
  const root = resolve(tmpdir());
  const target = resolve(tempRoot);
  const relative = target.slice(root.length);
  assert.ok(target.startsWith(`${root}${sep}`) || target === root, "test cleanup stays inside the OS temp directory");
  assert.ok(relative.length > 0);
  rmSync(target, { recursive: true, force: true });
});

function environmentFor(run, overrides = {}) {
  return {
    LOOPOS_E2E_ISOLATION_VERSION: "1",
    LOOPOS_E2E_RUN_ID: run.runId,
    LOOPOS_E2E_RUNNER_PID: String(process.pid),
    LOOPOS_E2E_RUN_MANIFEST: run.manifestPath,
    LOOPOS_E2E_OUTPUT_DIR: run.artifactsDirectory,
    LOOPOS_DATABASE_PATH: run.databasePath,
    ...overrides,
  };
}

test("child environment drops ambient credentials, loader hooks, provider settings, and arbitrary Vite config", () => {
  const built = buildE2EEnvironment({
    PATH: "C:\\safe\\bin",
    OPENAI_API_KEY: "must-not-pass",
    SUPABASE_SERVICE_ROLE_KEY: "must-not-pass",
    NODE_OPTIONS: "--require attacker.js",
    LOOPOS_POSTGRES_DSN: "must-not-pass",
    VITE_LOOPOS_LLM_ENDPOINT: "https://provider.example/secret",
    VITE_LOOPOS_DEPLOYMENT_MODE: "production",
    LOOPOS_E2E_LLM_ATTESTATION_FIXTURE: "1",
  });
  assert.equal(built.PATH, "C:\\safe\\bin");
  assert.equal(built.VITE_LOOPOS_DEPLOYMENT_MODE, "evaluation");
  for (const key of ["OPENAI_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "NODE_OPTIONS", "LOOPOS_POSTGRES_DSN", "VITE_LOOPOS_LLM_ENDPOINT"]) {
    assert.equal(Object.hasOwn(built, key), false, `${key} must not reach E2E children`);
  }
  const child = sanitizeE2EChildEnvironment({ ...built, ...environmentFor({
    runId: "b2148df5-a47b-4591-8b96-2930017223dc",
    runDirectory: join(tempRoot, "fake"),
    manifestPath: join(tempRoot, "fake", "run-manifest.json"),
    databasePath: join(tempRoot, "fake", "authority.sqlite"),
  }) });
  assert.equal(Object.hasOwn(child, "OPENAI_API_KEY"), false);
  assert.equal(Object.hasOwn(child, "NODE_OPTIONS"), false);
});

test("enterprise profile is fixed and cannot be replaced by ambient public configuration", () => {
  const built = buildE2EEnvironment({
    OPENAI_API_KEY: "must-not-pass",
    VITE_LOOPOS_DEPLOYMENT_MODE: "production",
    VITE_LOOPOS_SUPPORT_CONTACT: "attacker@example.invalid",
    VITE_LOOPOS_OUTBOUND_POLICY_MODE: "unrestricted",
  }, { enterpriseGate: true });
  assert.equal(built.VITE_LOOPOS_DEPLOYMENT_MODE, "enterprise");
  assert.equal(built.VITE_LOOPOS_SUPPORT_CONTACT, "loopos-ops@example.com");
  assert.equal(built.LOOPOS_OUTBOUND_POLICY_MODE, "deny_all");
  assert.equal(built.VITE_LOOPOS_OUTBOUND_POLICY_MODE, "allowlist");
  assert.equal(Object.hasOwn(built, "OPENAI_API_KEY"), false);
});

test("each run gets a fresh database and parent-bound manifest; completed runs cannot be reused", () => {
  const first = createIsolatedE2ERun({ workspaceRoot: tempRoot, runnerPid: process.pid });
  const second = createIsolatedE2ERun({ workspaceRoot: tempRoot, runnerPid: process.pid });
  assert.notEqual(first.databasePath, second.databasePath);
  assert.equal(dirname(first.databasePath), first.runDirectory);
  assert.equal(dirname(first.artifactsDirectory), first.runDirectory);
  assert.notEqual(first.artifactsDirectory, first.runDirectory);
  const firstEnv = environmentFor(first);
  assert.equal(assertE2EIsolation(firstEnv, { expectedParentPid: process.pid, workspaceRoot: tempRoot }).runId, first.runId);
  assert.throws(() => assertE2EIsolation(firstEnv, { expectedParentPid: process.pid + 1, workspaceRoot: tempRoot }), /launched directly/);
  completeIsolatedE2ERun(first, 0);
  assert.throws(() => assertE2EIsolation(firstEnv, { expectedParentPid: process.pid, workspaceRoot: tempRoot }), /stale or no longer active/);
});

test("E2E assertion rejects missing markers, stale database paths, and forged manifest identity", () => {
  assert.throws(() => assertE2EIsolation({}), /without the isolated runner marker/);
  const run = createIsolatedE2ERun({ workspaceRoot: tempRoot, runnerPid: process.pid });
  const valid = environmentFor(run);
  assert.throws(() => assertE2EIsolation({ ...valid, LOOPOS_DATABASE_PATH: resolve(tempRoot, "authority", "loopos-authority.db") }, { workspaceRoot: tempRoot }), /does not match the fresh run directory/);
  assert.throws(() => assertE2EIsolation({ ...valid, LOOPOS_E2E_RUNNER_PID: "99999999" }, { workspaceRoot: tempRoot }), /manifest does not match/);
});

test("Playwright arguments cannot replace config, widen test paths, or raise runner resources", () => {
  assert.deepEqual(validatePlaywrightArgs(["e2e/example.spec.ts", "--project=desktop-chromium", "--grep", "smoke"]), ["e2e/example.spec.ts", "--project=desktop-chromium", "--grep", "smoke"]);
  assert.throws(() => validatePlaywrightArgs(["--config=other.config.ts"]), /Unsupported E2E option/);
  assert.throws(() => validatePlaywrightArgs(["--workers=32"]), /Unsupported E2E option/);
  assert.throws(() => validatePlaywrightArgs(["../other.spec.ts"]), /must stay inside/);
});