import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DeleteWorkspaceDialog } from "./DeleteWorkspaceDialog";

const workspace = { workspace_id: "synthetic-workspace", name: "Synthetic workspace" };
const acknowledgment = "I understand that related records and copies are not erased.";

describe("workspace removal boundary", () => {
  it.each(["browser", "authority"] as const)("requires acknowledgment and preserves cancellation for %s storage", (location) => {
    const onDelete = vi.fn();
    render(<DeleteWorkspaceDialog workspace={workspace} onDelete={onDelete} location={location} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete workspace" }));
    expect(screen.getByRole("button", { name: "Remove workspace record" })).toBeDisabled();
    expect(screen.getByText(/Release proof packs, audit events/)).toBeInTheDocument();
    expect(screen.getByText(/Downloaded exports, other browser copies or caches/)).toBeInTheDocument();
    expect(screen.getByText(location === "authority" ? /Removal depends on the authority accepting/ : /does not remove an enterprise authority workspace/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove workspace record" }));
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox", { name: acknowledgment }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete workspace" }));
    expect(screen.getByRole("checkbox", { name: acknowledgment })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Remove workspace record" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: acknowledgment }));
    fireEvent.click(screen.getByRole("button", { name: "Remove workspace record" }));
    expect(onDelete).toHaveBeenCalledExactlyOnceWith(workspace.workspace_id);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("invalidates acknowledgment when the subject or storage boundary changes", () => {
    const onDelete = vi.fn();
    const { rerender } = render(<DeleteWorkspaceDialog workspace={workspace} onDelete={onDelete} location="browser" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete workspace" }));
    fireEvent.click(screen.getByRole("checkbox", { name: acknowledgment }));
    rerender(<DeleteWorkspaceDialog workspace={{ ...workspace, workspace_id: "other-workspace" }} onDelete={onDelete} location="authority" />);
    expect(screen.getByRole("button", { name: "Remove workspace record" })).toBeDisabled();
    rerender(<DeleteWorkspaceDialog workspace={workspace} onDelete={onDelete} location="browser" />);
    expect(screen.getByRole("button", { name: "Remove workspace record" })).toBeDisabled();
    expect(onDelete).not.toHaveBeenCalled();
  });
});
