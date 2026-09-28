import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("container UI build preparation", () => {
  it("uses checked-in generated data when the container build has no Python runtime", () => {
    const result = spawnSync(process.execPath, [resolve("scripts/export-data-if-local.mjs")], {
      cwd: resolve("."),
      encoding: "utf8",
      env: {
        ...process.env,
        VERCEL: "",
        LOOPOS_USE_CHECKED_IN_DATA: "1",
        PATH: "",
        Path: "",
      },
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("using checked-in loopos-data.json");
  });
});
