import { describe, expect, it, vi } from "vitest";
import { createUser, createWorkspace, DEFAULT_WORKSPACE_USE_CASE } from "./workspaceStore";
import { createWorkspaceExport, downloadWorkspaceExport, isWorkspaceExportEnvelope, parseWorkspaceExport, workspaceExportFilename } from "./workspaceExport";

describe("workspace export", () => {
  it("creates a versioned portable record without browser objects", () => {
    const workspace = createWorkspace(createUser("Owner", "owner@example.local", "Operator"), "Claims / Pilot", DEFAULT_WORKSPACE_USE_CASE);
    const exported = createWorkspaceExport(workspace, "2026-07-19T00:00:00.000Z");
    const serialized = JSON.stringify(exported);

    expect(exported).toMatchObject({ format: "loopos-workspace", version: 1, exported_at: "2026-07-19T00:00:00.000Z" });
    expect(exported.workspace.workspace_id).toBe(workspace.workspace_id);
    expect(serialized).not.toContain("blob:");
    expect(workspaceExportFilename(workspace)).toBe("claims-pilot.loopos.json");
    expect(isWorkspaceExportEnvelope(JSON.parse(serialized))).toBe(true);
    expect(parseWorkspaceExport(JSON.parse(serialized))).toEqual(workspace);
  });

  it("rejects malformed portability envelopes before they can be consumed", () => {
    const workspace = createWorkspace(createUser("Owner", "owner@example.local", "Operator"), "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const exported = createWorkspaceExport(workspace, "2026-07-19T00:00:00.000Z");

    expect(isWorkspaceExportEnvelope({ ...exported, exported_at: "not-a-timestamp" })).toBe(false);
    expect(() => parseWorkspaceExport({ ...exported, workspace: { ...workspace, workspace_id: "" } })).toThrow(/malformed/);
  });

  it("keeps the download object URL alive until the browser has a chance to start", () => {
    vi.useFakeTimers();
    const workspace = createWorkspace(createUser("Owner", "owner@example.local", "Operator"), "Claims", DEFAULT_WORKSPACE_USE_CASE);
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:workspace-export");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadWorkspaceExport(workspace);

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:workspace-export");

    click.mockRestore();
    revokeObjectURL.mockRestore();
    createObjectURL.mockRestore();
    vi.useRealTimers();
  });
});
