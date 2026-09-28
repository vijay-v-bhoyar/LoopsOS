import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceConsole } from "./WorkspaceConsole";
import { looposData } from "../lib/loopos";

describe("empty workspace persistence feedback", () => {
  it("keeps a failed authority removal visible and offers a bounded retry", () => {
    const retry = vi.fn();
    render(<WorkspaceConsole data={looposData} user={{ user_id: "synthetic-user", name: "Synthetic user", email: "fixture@example.invalid", role: "Operator", signed_in_at: "2026-09-21T00:00:00Z" }}
      activeWorkspace={null} workspaces={[]} onCreateWorkspace={vi.fn()} onSetActiveWorkspace={vi.fn()}
      onMutateWorkspace={vi.fn()} onUseCaseChange={vi.fn()} onDeleteWorkspace={vi.fn()}
      onRetryPersistence={retry} persistence={{ location: "authority", status: "error", code: "authority_unavailable", bytes: 0, message: "Synthetic authority unavailable" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("An empty list does not confirm removal from storage.");
    fireEvent.click(screen.getByRole("button", { name: "Retry save" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
