import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { HelpRequestLedger } from "./HelpRequestLedger";
import { createWorkspace, DEFAULT_WORKSPACE_USE_CASE } from "../lib/workspaceStore";
import type { EnterpriseUser, SavedWorkspace } from "../types";

const user: EnterpriseUser = {
  user_id: "operator-1",
  name: "Workspace operator",
  email: "operator@example.test",
  role: "Operator",
  signed_in_at: "2026-09-22T10:00:00.000Z",
};

function Harness() {
  const [workspace, setWorkspace] = useState<SavedWorkspace>(() => createWorkspace(user, "Help workflow test", DEFAULT_WORKSPACE_USE_CASE));
  return (
    <HelpRequestLedger
      workspace={workspace}
      user={user}
      onMutateWorkspace={(update) => setWorkspace((current) => update(current))}
    />
  );
}

describe("HelpRequestLedger", () => {
  it("persists a request draft and records delivery only after a manual evidence reference", () => {
    render(<Harness />);
    expect(screen.getByText(/Nothing is sent automatically/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Blocked goal or acceptance criterion"), { target: { value: "Verify production health route" } });
    fireEvent.change(screen.getByLabelText("Requested owner or team"), { target: { value: "Platform operations" } });
    fireEvent.change(screen.getByLabelText("Specific action needed"), { target: { value: "Provide authenticated route evidence" } });
    fireEvent.change(screen.getByLabelText("Risk while waiting"), { target: { value: "Release remains NO-GO" } });
    fireEvent.change(screen.getByLabelText("Evidence references (one per line or comma-separated)"), { target: { value: "risk:F-06" } });
    fireEvent.change(screen.getByLabelText("Wake condition: what exact response unblocks the next action?"), { target: { value: "Canonical deployment and route evidence are recorded" } });
    fireEvent.change(screen.getByLabelText("Response deadline"), { target: { value: "2030-01-01T10:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save help request draft" }));

    expect(screen.getByText("draft")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record delivery" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Evidence reference is required");

    fireEvent.change(screen.getByLabelText("Delivery reference"), { target: { value: "ticket:123" } });
    fireEvent.change(screen.getByLabelText("Delivery note"), { target: { value: "Sent manually through the approved channel" } });
    fireEvent.click(screen.getByRole("button", { name: "Record delivery" }));
    expect(screen.getByText("waiting")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record delivery" })).not.toBeInTheDocument();
  });
});