import { describe, expect, it } from "vitest";
import { createUser, createWorkspace, DEFAULT_WORKSPACE_USE_CASE } from "./workspaceStore";
import { createWorkspaceExport, workspaceExportFilename } from "./workspaceExport";

describe("workspace export", () => {
  it("creates a versioned portable record without browser objects", () => {
    const workspace = createWorkspace(createUser("Owner", "owner@example.local", "Operator"), "Claims / Pilot", DEFAULT_WORKSPACE_USE_CASE);
    const exported = createWorkspaceExport(workspace, "2026-07-19T00:00:00.000Z");
    const serialized = JSON.stringify(exported);

    expect(exported).toMatchObject({ format: "loopos-workspace", version: 1, exported_at: "2026-07-19T00:00:00.000Z" });
    expect(exported.workspace.workspace_id).toBe(workspace.workspace_id);
    expect(serialized).not.toContain("blob:");
    expect(workspaceExportFilename(workspace)).toBe("claims-pilot.loopos.json");
  });
});
