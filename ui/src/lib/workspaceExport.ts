import { isSavedWorkspaceDocument } from "./workspaceDocument";
import type { SavedWorkspace } from "../types";

export const MAX_WORKSPACE_EXPORT_BYTES = 4_000_000;

export interface WorkspaceExportEnvelope {
  format: "loopos-workspace";
  version: 1;
  exported_at: string;
  workspace: SavedWorkspace;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isIsoTimestamp(value: unknown): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}

function assertExportSize(value: unknown): void {
  const bytes = new TextEncoder().encode(JSON.stringify(value)).byteLength;
  if (bytes > MAX_WORKSPACE_EXPORT_BYTES) {
    throw new Error("Workspace export exceeds the 4 MB portability limit.");
  }
}

export function isWorkspaceExportEnvelope(value: unknown): value is WorkspaceExportEnvelope {
  if (!isRecord(value)
    || value.format !== "loopos-workspace"
    || value.version !== 1
    || !isIsoTimestamp(value.exported_at)
    || !isSavedWorkspaceDocument(value.workspace)) {
    return false;
  }
  try {
    assertExportSize(value);
    return true;
  } catch {
    return false;
  }
}

export function createWorkspaceExport(workspace: SavedWorkspace, exportedAt = new Date().toISOString()): WorkspaceExportEnvelope {
  const envelope = {
    format: "loopos-workspace",
    version: 1,
    exported_at: exportedAt,
    workspace,
  };
  if (!isWorkspaceExportEnvelope(envelope)) throw new Error("Workspace export failed its portability contract.");
  return envelope;
}

export function parseWorkspaceExport(value: unknown): SavedWorkspace {
  if (!isWorkspaceExportEnvelope(value)) throw new Error("Workspace export is malformed or exceeds the portability limit.");
  return value.workspace;
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
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadMarkdown(filename: string, markdown: string): void {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
