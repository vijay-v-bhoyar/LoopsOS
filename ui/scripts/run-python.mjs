import { spawn, spawnSync } from "node:child_process";

const pythonArgs = process.argv.slice(2);

if (pythonArgs.length === 0) {
  console.error("Usage: node scripts/run-python.mjs <python arguments>");
  process.exit(2);
}

const configuredPython = process.env.LOOPOS_PYTHON?.trim();
const requiredModule = pythonArgs[0] === "-m" ? pythonArgs[1] : undefined;
const candidates = configuredPython
  ? [{ command: configuredPython, prefix: [] }]
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

const selected = candidates.find(({ command, prefix }) => {
  const probeCode = requiredModule
    ? `import importlib.util, sys; sys.exit(sys.version_info < (3, 12) or importlib.util.find_spec(${JSON.stringify(requiredModule)}) is None)`
    : "import sys; sys.exit(sys.version_info < (3, 12))";
  const probe = spawnSync(command, [...prefix, "-c", probeCode], {
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
  env: process.env,
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
