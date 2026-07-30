import { spawnSync } from "node:child_process";

if (process.env.VERCEL || process.env.LOOPOS_USE_CHECKED_IN_DATA === "1") {
  console.log("Generated-data build detected; using checked-in loopos-data.json.");
  process.exit(0);
}

const result = spawnSync("python", ["../scripts/export_ui_data.py", "--out", "ui/src/data/loopos-data.json"], {
  stdio: "inherit",
  shell: process.platform === "win32",
});

process.exit(result.status ?? 1);
