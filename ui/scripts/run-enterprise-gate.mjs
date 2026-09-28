import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { buildHostProcessEnvironment, UI_ROOT } from "./e2e-isolation.mjs";

const runnerPath = fileURLToPath(new URL("./run-e2e.mjs", import.meta.url));
const child = spawn(process.execPath, [runnerPath, "--loopos-enterprise-gate", "e2e/enterprise-readiness-gate.spec.ts", ...process.argv.slice(2)], {
  cwd: UI_ROOT,
  env: buildHostProcessEnvironment(process.env),
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