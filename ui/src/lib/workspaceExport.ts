import type { SavedWorkspace } from "../types";

export interface WorkspaceExportEnvelope {
  format: "loopos-workspace";
  version: 1;
  exported_at: string;
  workspace: SavedWorkspace;
}

export function createWorkspaceExport(workspace: SavedWorkspace, exportedAt = new Date().toISOString()): WorkspaceExportEnvelope {
  return {
    format: "loopos-workspace",
    version: 1,
    exported_at: exportedAt,
    workspace,
  };
}

export function workspaceExportFilename(workspace: SavedWorkspace): string {
  const base = workspace.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "workspace";
  return `${base}.loopos.json`;
}

export function downloadWorkspaceExport(workspace: SavedWorkspace): void {
  const blob = new Blob([JSON.stringify(createWorkspaceExport(workspace), null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = workspaceExportFilename(workspace);
  anchor.click();
  URL.revokeObjectURL(url);
}

export function downloadMarkdown(filename: string, markdown: string): void {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
