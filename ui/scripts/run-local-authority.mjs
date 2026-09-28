import { mkdirSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const uiRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const repoRoot = resolve(uiRoot, "..");
const dataRoot = join(repoRoot, "output", "loopsos-local");
const databasePath = resolve(process.env.LOOPOS_DATABASE_PATH?.trim() || join(dataRoot, "authority.sqlite"));
mkdirSync(dirname(databasePath), { recursive: true });

const environment = {
  ...process.env,
  LOOPOS_LOCAL_AUTHORITY: "1",
  LOOPOS_DATABASE_PATH: databasePath,
  LOOPOS_STORAGE_BACKEND: "sqlite",
  LOOPOS_OUTBOUND_POLICY_MODE: "deny_all",
  LOOPOS_ALLOW_DEV_AUTH: "true",
  LOOPOS_CORS_ORIGINS: "http://127.0.0.1:5173,http://localhost:5173",
  LOOPOS_ALLOWED_HTTP_HOSTS: "",
  PYTHONPATH: join(repoRoot, "authority"),
};

const runner = spawn(process.execPath, [join(uiRoot, "scripts", "run-python.mjs"), "-m", "uvicorn", "loopos_authority.api:app", "--app-dir", join(repoRoot, "authority"), "--host", "127.0.0.1", "--port", "8787"], {
  cwd: uiRoot,
  env: environment,
  stdio: "inherit",
  windowsHide: false,
});

for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => runner.kill(signal));
runner.on("error", (error) => {
  console.error(`Failed to launch the local authority: ${error.message}`);
  process.exitCode = 1;
});
runner.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
