import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const pythonLauncher = fileURLToPath(new URL("./run-python.mjs", import.meta.url));

function runPython(args) {
  const result = spawnSync(process.execPath, [pythonLauncher, ...args], {
    stdio: "inherit",
    env: process.env,
  });
  return result.status ?? 1;
}

const enterpriseBuild = process.env.VITE_LOOPOS_DEPLOYMENT_MODE?.trim().toLowerCase() === "enterprise";
const productionBuild = process.env.VERCEL_ENV?.trim().toLowerCase() === "production";
if (enterpriseBuild || productionBuild) {
  console.log("Production configuration build detected; running fail-closed environment preflight.");
  const preflightStatus = runPython(["../scripts/verify_production_environment.py"]);
  if (preflightStatus !== 0) process.exit(preflightStatus);
}

if (process.env.VERCEL || process.env.LOOPOS_USE_CHECKED_IN_DATA === "1") {
  console.log("Generated-data build detected; using checked-in loopos-data.json.");
  process.exit(0);
}

process.exit(runPython(["../scripts/export_ui_data.py", "--out", "ui/src/data/loopos-data.json"]));
