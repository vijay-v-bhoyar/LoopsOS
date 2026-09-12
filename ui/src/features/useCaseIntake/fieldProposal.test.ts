import { describe, expect, it, vi } from "vitest";
import type { UseCaseInput, UseCaseSource } from "../../types";
import { applyUseCaseDraft, enhanceUseCaseProposal, proposeUseCaseFields } from "./fieldProposal";

const current: UseCaseInput = {
  title: "Current title",
  description: "Current workflow description",
  environment: "development",
  aiScope: "AI readiness",
  dataSensitivity: "internal",
  businessOutcome: "Current outcome",
  maturity: "idea",
  constraints: "Current constraints",
};

const source: UseCaseSource = {
  source_id: "source-brief",
  kind: "document",
  label: "claims-brief.md",
  mime_type: "text/markdown",
  status: "ready_for_review",
  accepted_text: [
    "# Agentic claims triage",
    "Workflow: Use AI agents with retrieval and delegated tools to triage incoming insurance claims.",
    "Environment: production",
    "AI scope: Agentic AI",
    "Data sensitivity: regulated",
    "Business outcome: Reduce claim cycle time by 30 percent while preserving review quality.",
    "Maturity: pilot",
    "Constraints: Must preserve audit evidence, human approval, privacy, and access controls.",
  ].join("\n"),
  extraction_method: "browser text reader",
  character_count: 402,
  created_at: "2026-07-18T00:00:00.000Z",
  warnings: [],
  truncated: false,
};

describe("proposeUseCaseFields", () => {
  it("proposes all eight advisor fields with source evidence", () => {
    const draft = proposeUseCaseFields(source, current);

    expect(draft.fields.map((field) => field.field)).toEqual([
      "title",
      "description",
      "environment",
      "aiScope",
      "dataSensitivity",
      "businessOutcome",
      "maturity",
      "constraints",
    ]);
    expect(draft.fields.find((field) => field.field === "aiScope")?.value).toBe("Agentic AI");
    expect(draft.fields.every((field) => field.method === "deterministic" && field.source_ids[0] === source.source_id)).toBe(true);
    expect(draft.fields.every((field) => field.evidence_excerpt.length > 0)).toBe(true);
  });

  it("only applies fields the user selected", () => {
    const draft = proposeUseCaseFields(source, current);
    const next = applyUseCaseDraft(current, draft, new Set<keyof UseCaseInput>(["title", "businessOutcome"]));

    expect(next.title).toBe("Agentic claims triage");
    expect(next.businessOutcome).toContain("Reduce claim cycle time");
    expect(next.description).toBe(current.description);
    expect(current.title).toBe("Current title");
  });

  it("offers a bounded source-backed description for a short unlabeled source", () => {
    const shortSource = { ...source, source_id: "source-short", accepted_text: "Enterprise claims triage with approval" };
    const draft = proposeUseCaseFields(shortSource, current);

    expect(draft.fields).toHaveLength(1);
    expect(draft.fields[0]).toMatchObject({
      field: "description",
      value: "Enterprise claims triage with approval",
      method: "deterministic",
      source_ids: ["source-short"],
    });
    expect(draft.fields[0].evidence_excerpt).toContain("Enterprise claims triage with approval");
  });

  it("uses a validated enterprise response only when enhancement is explicitly called", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        proposal: {
          title: "Enterprise claims copilot",
          aiScope: "Agentic AI",
          dataSensitivity: "not-an-allowed-value",
        },
      }),
    });

    const deterministic = proposeUseCaseFields(source, current);
    expect(fetchImpl).not.toHaveBeenCalled();

    const enhanced = await enhanceUseCaseProposal(source, current, deterministic, {
      endpoint: "https://enterprise.example/intake",
      consent: true,
      fetchImpl: fetchImpl as never,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(enhanced.fields.find((field) => field.field === "title")).toMatchObject({ value: "Enterprise claims copilot", method: "enterprise LLM" });
    expect(enhanced.fields.find((field) => field.field === "dataSensitivity")?.value).toBe("regulated");
  });

  it("preserves the deterministic draft when the endpoint fails or returns malformed JSON", async () => {
    const deterministic = proposeUseCaseFields(source, current);
    const failed = await enhanceUseCaseProposal(source, current, deterministic, {
      endpoint: "https://enterprise.example/intake",
      consent: true,
      fetchImpl: vi.fn().mockRejectedValue(new Error("offline")) as never,
    });
    const malformed = await enhanceUseCaseProposal(source, current, deterministic, {
      endpoint: "https://enterprise.example/intake",
      consent: true,
      fetchImpl: vi.fn().mockResolvedValue({ ok: true, json: async () => ({ proposal: "bad" }) }) as never,
    });

    expect(failed).toEqual(deterministic);
    expect(malformed).toEqual(deterministic);
  });

  it("does not send source text without explicit outbound consent", async () => {
    const deterministic = proposeUseCaseFields(source, current);
    const fetchImpl = vi.fn();

    const result = await enhanceUseCaseProposal(source, current, deterministic, {
      endpoint: "https://enterprise.example/intake",
      consent: false,
      fetchImpl: fetchImpl as never,
    });

    expect(result).toEqual(deterministic);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
