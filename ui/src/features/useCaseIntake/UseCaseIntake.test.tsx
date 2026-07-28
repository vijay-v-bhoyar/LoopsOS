import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { UseCaseInput, UseCaseSource } from "../../types";
import { UseCaseIntake } from "./UseCaseIntake";

const input: UseCaseInput = {
  title: "Current use case",
  description: "Current workflow description",
  environment: "development",
  aiScope: "AI readiness",
  dataSensitivity: "internal",
  businessOutcome: "Current outcome",
  maturity: "idea",
  constraints: "Current constraints",
};

const brief = [
  "# Agentic claims triage",
  "Workflow: Use AI agents with retrieval and delegated tools to triage incoming insurance claims.",
  "Environment: production",
  "AI scope: Agentic AI",
  "Data sensitivity: regulated",
  "Business outcome: Reduce claim cycle time by 30 percent.",
  "Maturity: pilot",
  "Constraints: Must preserve audit evidence, privacy, access controls, and human approval.",
].join("\n");

function renderIntake(sources: UseCaseSource[] = []) {
  const onApply = vi.fn();
  const onRemoveSource = vi.fn();
  render(
    <UseCaseIntake
      input={input}
      sources={sources}
      workspaceId="workspace-test"
      onApply={onApply}
      onRemoveSource={onRemoveSource}
    />,
  );
  return { onApply, onRemoveSource };
}

function activateTab(name: string) {
  fireEvent.mouseDown(screen.getByRole("tab", { name }), { button: 0, ctrlKey: false });
}

describe("UseCaseIntake", () => {
  it("reviews freeform text and applies only selected fields", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { onApply } = renderIntake();
    fireEvent.change(screen.getByLabelText("Describe the use case"), { target: { value: brief } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze and review" }));

    expect(await screen.findByRole("dialog", { name: "Review proposed use case" })).toBeInTheDocument();
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Apply Workflow and problem" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply selected fields" }));

    expect(onApply).toHaveBeenCalledTimes(1);
    const [source, nextInput] = onApply.mock.calls[0] as [UseCaseSource, UseCaseInput];
    expect(source).toMatchObject({ kind: "text", status: "accepted", label: "Typed use case" });
    expect(nextInput.title).toBe("Agentic claims triage");
    expect(nextInput.description).toBe(input.description);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("extracts a local text document before opening review", async () => {
    const { onApply } = renderIntake();
    activateTab("Document");
    const upload = screen.getByLabelText("Choose documents");
    fireEvent.change(upload, { target: { files: [new File([brief], "claims-brief.md", { type: "text/markdown" })] } });

    expect(await screen.findByText("Review proposed use case")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Apply selected fields" }));

    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1));
    expect(onApply.mock.calls[0][0]).toMatchObject({ kind: "document", label: "claims-brief.md", status: "accepted" });
  });

  it("routes dropped documents through the same review flow", async () => {
    renderIntake();
    activateTab("Document");
    const dropZone = screen.getByText("Choose documents").closest("label");
    expect(dropZone).not.toBeNull();

    fireEvent.drop(dropZone as HTMLLabelElement, {
      dataTransfer: { files: [new File([brief], "dropped-brief.txt", { type: "text/plain" })] },
    });

    const dialog = await screen.findByRole("dialog", { name: "Review proposed use case" });
    expect(dialog).toHaveTextContent("dropped-brief.txt");
  });

  it("shows retained source provenance and removes it without changing fields", () => {
    const source: UseCaseSource = {
      source_id: "source-1",
      kind: "document",
      label: "agent-brief.md",
      mime_type: "text/markdown",
      status: "accepted",
      accepted_text: brief,
      extraction_method: "browser text reader",
      character_count: brief.length,
      created_at: "2026-07-18T00:00:00.000Z",
      warnings: [{ code: "truncated", message: "Text was limited." }],
      truncated: true,
    };
    const { onRemoveSource } = renderIntake([source]);

    expect(screen.getByText("agent-brief.md")).toBeInTheDocument();
    expect(screen.getByText("Text was limited.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove agent-brief.md" }));
    expect(onRemoveSource).toHaveBeenCalledWith("source-1");
  });

  it("shows an honest unavailable state when no voice capability exists", () => {
    renderIntake();
    activateTab("Voice");
    expect(screen.getByText(/Voice input is unavailable in this browser/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Voice state: Unavailable");
  });

  it("returns focus to the intake command when review is dismissed", async () => {
    renderIntake();
    fireEvent.change(screen.getByLabelText("Describe the use case"), { target: { value: brief } });
    const analyze = screen.getByRole("button", { name: "Analyze and review" });
    analyze.focus();
    fireEvent.click(analyze);
    expect(await screen.findByRole("dialog", { name: "Review proposed use case" })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => expect(analyze).toHaveFocus());
  });
});
