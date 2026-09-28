import { describe, expect, it } from "vitest";
import type { UseCaseInput, UseCaseSource } from "../types";
import { looposData } from "./loopos";
import { recommendLoops } from "./recommendation";
import { hasCompleteOutcomeMeasurementPlan, validateUseCase } from "./validation";

const input: UseCaseInput = {
  title: "Agentic claims triage workflow",
  description: "Use governed AI agents with retrieval and delegated tools to triage incoming insurance claims before human review.",
  environment: "production",
  aiScope: "Agentic AI",
  dataSensitivity: "regulated",
  businessOutcome: "Reduce claim cycle time while preserving review quality.",
  maturity: "pilot",
  constraints: "Require access controls, audit evidence, guardrails, privacy, and human approval.",
};

function source(overrides: Partial<UseCaseSource> = {}): UseCaseSource {
  return {
    source_id: "source-1",
    kind: "document",
    label: "claims-brief.md",
    mime_type: "text/markdown",
    status: "accepted",
    accepted_text: "Agentic claims triage with governed tools and human approval.",
    extraction_method: "browser text reader",
    character_count: 61,
    created_at: "2026-07-18T00:00:00.000Z",
    warnings: [],
    truncated: false,
    ...overrides,
  };
}

describe("validateUseCase input provenance", () => {
  it("requires a structured measurement plan before treating business value as ready", () => {
    const recommendations = recommendLoops(input, looposData);
    const missingPlan = validateUseCase(input, recommendations, looposData);
    expect(hasCompleteOutcomeMeasurementPlan(input)).toBe(false);
    expect(missingPlan.findings.find((finding) => finding.label === "Outcome measurement plan")?.status).toBe("gap");

    const measuredInput = {
      ...input,
      outcomeMeasurement: {
        metric: "Claim cycle time",
        unit: "hours" as const,
        baseline: 40,
        target: 16,
        source: "Claims system report",
        observation_window: "90 days",
      },
    };
    const completePlan = validateUseCase(measuredInput, recommendLoops(measuredInput, looposData), looposData);
    expect(hasCompleteOutcomeMeasurementPlan(measuredInput)).toBe(true);
    expect(completePlan.findings.find((finding) => finding.label === "Outcome measurement plan")?.status).toBe("pass");
  });

  it("keeps extraction warnings and truncation in review state", () => {
    const warnedSource = source({
      warnings: [{ code: "truncated", message: "Text was limited to 50,000 characters." }],
      truncated: true,
    });
    const recommendations = recommendLoops(input, looposData, { sources: [warnedSource] });
    const result = validateUseCase(input, recommendations, looposData, [warnedSource]);

    expect(result.findings.find((finding) => finding.label === "Input provenance")?.status).toBe("pass");
    expect(result.findings.find((finding) => finding.label === "Extraction completeness")?.status).toBe("review");
    expect(result.findings.find((finding) => finding.label === "Extraction completeness")?.detail).toContain("claims-brief.md");
  });

  it("distinguishes missing provenance from corpus validation", () => {
    const recommendations = recommendLoops(input, looposData);
    const result = validateUseCase(input, recommendations, looposData);

    expect(result.corpusStatus).toBe("PASS");
    expect(result.findings.find((finding) => finding.label === "Input provenance")?.status).toBe("review");
  });
});
