import { spawn, spawnSync } from "node:child_process";

const root = process.cwd();
const testArgs = process.argv.slice(2);
const children = new Set();

function findPython() {
  const configured = process.env.LOOPOS_PYTHON?.trim();
  const candidates = configured
    ? [{ command: configured, prefix: [] }]
    : process.platform === "win32"
      ? [
          { command: "py", prefix: ["-3"] },
          { command: "python3", prefix: [] },
          { command: "python", prefix: [] },
        ]
      : [
          { command: "python3", prefix: [] },
          { command: "python", prefix: [] },
        ];
  const probe = "import sys; sys.exit(sys.version_info < (3, 12))";
  const selected = candidates.find(({ command, prefix }) => spawnSync(command, [...prefix, "-c", probe], {
    stdio: "ignore",
    windowsHide: true,
  }).status === 0);
  if (!selected) throw new Error("A Python 3.12+ interpreter is required for the E2E authority server. Set LOOPOS_PYTHON.");
  return selected;
}

function start(command, args) {
  const child = spawn(command, args, {
    cwd: root,
    env: { ...process.env, BROWSER: "none" },
    stdio: "inherit",
    windowsHide: true,
  });
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}

async function waitFor(url, child, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`E2E server exited before ${url} became ready.`);
    try {
      const response = await fetch(url);
      await response.text();
      if (response.ok) return;
    } catch {
      // The server may still be binding its port.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}.`);
}

function stop(child) {
  if (!child || child.exitCode !== null) return;
  child.kill();
}

let runner;
let shuttingDown = false;
function stopAll() {
  if (shuttingDown) return;
  shuttingDown = true;
  stop(runner);
  for (const child of children) stop(child);
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    stopAll();
    process.exit(130);
  });
}

let exitCode = 1;
try {
  const python = findPython();
  const authorityPort = process.env.LOOPOS_E2E_AUTHORITY_PORT?.trim() || "8787";
  const vitePort = process.env.LOOPOS_E2E_VITE_PORT?.trim() || "4273";
  const authority = start(python.command, [
    ...python.prefix,
    "-m",
    "uvicorn",
    "loopos_authority.api:app",
    "--app-dir",
    "../authority",
    "--host",
    "127.0.0.1",
    "--port",
    authorityPort,
  ]);
  const vite = start(process.execPath, ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", vitePort]);
  await waitFor(`http://127.0.0.1:${authorityPort}/health/ready`, authority);
  await waitFor(`http://127.0.0.1:${vitePort}/`, vite);

  process.env.LOOPOS_E2E_EXTERNAL_SERVERS = "1";
  runner = start(process.execPath, ["node_modules/playwright/cli.js", "test", ...testArgs]);
  exitCode = await new Promise((resolve) => {
    runner.once("error", () => resolve(1));
    runner.once("exit", (code, signal) => resolve(code ?? (signal ? 1 : 0)));
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
} finally {
  stopAll();
}

process.exit(exitCode);
