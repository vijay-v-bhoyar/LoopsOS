import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { assertE2EIsolation, sanitizeE2EChildEnvironment } from "./e2e-isolation.mjs";

const pythonArgs = process.argv.slice(2);

if (pythonArgs.length === 0) {
  console.error("Usage: node scripts/run-python.mjs <python arguments>");
  process.exit(2);
}

const isAuthorityServer = pythonArgs[0] === "-m" && pythonArgs[1] === "uvicorn" && pythonArgs.includes("loopos_authority.api:app");
const isolated = process.env.LOOPOS_E2E_ISOLATION_VERSION === "1";
const localAuthority = process.env.LOOPOS_LOCAL_AUTHORITY === "1";
if (isAuthorityServer && !isolated && !localAuthority) {
  console.error("Refusing to start the E2E authority server without a verified per-run database.");
  process.exit(1);
}

let childEnvironment = process.env;
if (isolated) {
  try {
    assertE2EIsolation(process.env);
    childEnvironment = sanitizeE2EChildEnvironment(process.env);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  }
}
if (isAuthorityServer && localAuthority && !isolated) {
  const workspaceRoot = resolve(fileURLToPath(new URL("../../", import.meta.url)));
  const localDataRoot = resolve(join(workspaceRoot, "output", "loopsos-local"));
  const databasePath = childEnvironment.LOOPOS_DATABASE_PATH?.trim();
  const databaseRoot = databasePath ? resolve(databasePath) : "";
  const relativeDatabasePath = databaseRoot ? relative(localDataRoot, databaseRoot) : "";
  const withinLocalDataRoot = databaseRoot === localDataRoot || (Boolean(relativeDatabasePath) && !relativeDatabasePath.startsWith("..") && !isAbsolute(relativeDatabasePath));
  const hostIndex = pythonArgs.indexOf("--host");
  const host = hostIndex >= 0 ? pythonArgs[hostIndex + 1] : undefined;
  if (!databasePath || !isAbsolute(databasePath) || !withinLocalDataRoot || childEnvironment.LOOPOS_STORAGE_BACKEND !== "sqlite" || childEnvironment.LOOPOS_OUTBOUND_POLICY_MODE !== "deny_all" || childEnvironment.LOOPOS_ALLOW_DEV_AUTH !== "true" || host !== "127.0.0.1") {
    console.error("Refusing local authority startup unless it uses a fresh output/loopsos-local SQLite database, deny_all egress, development auth, and loopback host 127.0.0.1.");
    process.exit(1);
  }
}

const configuredPython = childEnvironment.LOOPOS_PYTHON?.trim();
const requiredModule = pythonArgs[0] === "-m" ? pythonArgs[1] : undefined;
function installedWindowsPythonCandidates() {
  if (process.platform !== "win32") return [];
  const roots = [
    childEnvironment.LOCALAPPDATA ? join(childEnvironment.LOCALAPPDATA, "Programs", "Python") : "",
    childEnvironment.ProgramFiles ? join(childEnvironment.ProgramFiles, "Python") : "",
  ].filter(Boolean);
  const paths = [];
  if (childEnvironment.LOCALAPPDATA) {
    for (const version of ["Python314", "Python313", "Python312", "Python311"]) {
      paths.push(join(childEnvironment.LOCALAPPDATA, "Programs", "Python", version, "python.exe"));
    }
  }
  for (const root of roots) {
    try {
      const versions = readdirSync(root, { withFileTypes: true })
        .filter((entry) => entry.isDirectory() && /^Python3\d+$/.test(entry.name))
        .map((entry) => entry.name)
        .sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
      for (const version of versions) paths.push(join(root, version, "python.exe"));
    } catch {
      // An absent or unreadable conventional install directory is not fatal.
    }
  }
  const workspaceRoot = resolve(fileURLToPath(new URL("../../", import.meta.url)));
  paths.push(join(workspaceRoot, ".venv", "Scripts", "python.exe"));
  return paths.filter((candidate, index) => paths.indexOf(candidate) === index && existsSync(candidate));
}
const candidates = configuredPython
  ? [{ command: configuredPython, prefix: [] }]
  : process.platform === "win32"
    ? [
        { command: "py", prefix: ["-3"] },
        { command: "python3", prefix: [] },
        { command: "python", prefix: [] },
        ...installedWindowsPythonCandidates().map((command) => ({ command, prefix: [] })),
      ]
    : [
        { command: "python3", prefix: [] },
        { command: "python", prefix: [] },
      ];

const selected = candidates.find(({ command, prefix }) => {
  const probeCode = requiredModule
    ? `import importlib.util, sys; sys.exit(sys.version_info < (3, 12) or importlib.util.find_spec(${JSON.stringify(requiredModule)}) is None)`
    : "import sys; sys.exit(sys.version_info < (3, 12))";
  const probe = spawnSync(command, [...prefix, "-c", probeCode], {
    env: childEnvironment,
    stdio: "ignore",
    windowsHide: true,
  });
  return probe.status === 0;
});

if (!selected) {
  const attempted = candidates.map(({ command }) => command).join(", ");
  const requirement = requiredModule ? ` with module ${requiredModule}` : "";
  console.error(`No usable Python 3.12+ interpreter${requirement} found. Tried: ${attempted}. Set LOOPOS_PYTHON to an executable path.`);
  process.exit(1);
}

const child = spawn(selected.command, [...selected.prefix, ...pythonArgs], {
  env: childEnvironment,
  stdio: "inherit",
  windowsHide: true,
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}

child.on("error", (error) => {
  console.error(`Failed to launch Python: ${error.message}`);
  process.exitCode = 1;
});

child.on("exit", (code, signal) => {
  process.exit(code ?? (signal ? 1 : 0));
});
