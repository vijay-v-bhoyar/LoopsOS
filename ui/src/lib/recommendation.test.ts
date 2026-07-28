import { describe, expect, it } from "vitest";
import { looposData } from "./loopos";
import { recommendLoops } from "./recommendation";
import type { UseCaseInput } from "../types";

function input(overrides: Partial<UseCaseInput>): UseCaseInput {
  return {
    title: "",
    description: "",
    environment: "enterprise portfolio",
    aiScope: "",
    dataSensitivity: "sensitive",
    businessOutcome: "",
    maturity: "discovery",
    constraints: "",
    ...overrides,
  };
}

function idsFor(useCase: UseCaseInput): string[] {
  return recommendLoops(useCase, looposData).map((item) => item.loop_id);
}

describe("LoopOS UI data", () => {
  it("exports the required corpus counts", () => {
    expect(looposData.stats.loops).toBe(108);
    expect(looposData.stats.categories).toBe(13);
    expect(looposData.stats.controls).toBe(109);
    expect(looposData.stats.operation_cards).toBe(108);
    expect(looposData.stats.playbooks).toBe(6);
  });
});

describe("recommendLoops", () => {
  it("recommends agent governance loops for enterprise agentic AI readiness", () => {
    const ids = idsFor(
      input({
        title: "Prepare enterprise for agentic AI",
        description: "Govern tool execution, agent memory, access, guardrails, audit, and evaluation for agentic AI.",
        aiScope: "Agentic AI",
      }),
    );
    expect(ids).toContain("loop-069-tool-execution-validation-loop");
    expect(ids).toContain("loop-071-agent-memory-loop");
    expect(ids).toContain("loop-079-agent-guardrail-loop");
    expect(ids).toContain("loop-081-access-governance-loop");
    expect(ids).toContain("loop-089-audit-logging-and-forensic-readiness-loop");
  });

  it("recommends RAG quality and truth loops for existing RAG improvement", () => {
    const ids = idsFor(
      input({
        title: "Improve existing RAG use case",
        description: "Improve RAG quality, citations, hallucination reduction, knowledge freshness, drift, feedback, lineage, and privacy.",
        aiScope: "RAG improvement",
      }),
    );
    expect(ids).toContain("loop-055-knowledge-base-freshness-and-rag-content-lifecycle-loop");
    expect(ids).toContain("loop-059-rag-quality-loop");
    expect(ids).toContain("loop-061-hallucination-reduction-loop");
    expect(ids).toContain("loop-062-model-and-data-drift-monitoring-loop");
    expect(ids).toContain("loop-088-privacy-engineering-and-data-protection-loop");
  });

  it("recommends GenAI intake, data, prompt, eval, safety, release, monitoring, and compliance loops", () => {
    const ids = idsFor(
      input({
        title: "Build new GenAI use case",
        description: "Create a new GenAI copilot with prompt engineering, model eval, safety, data preparation, release readiness, monitoring, and compliance evidence.",
        aiScope: "GenAI use case",
      }),
    );
    expect(ids).toContain("loop-002-ai-use-case-validation-loop");
    expect(ids).toContain("loop-051-ai-data-preparation-loop");
    expect(ids).toContain("loop-057-prompt-engineering-loop");
    expect(ids).toContain("loop-058-model-evaluation-and-benchmarking-loop");
    expect(ids).toContain("loop-060-ai-safety-and-responsible-ai-loop");
    expect(ids).toContain("loop-104-compliance-evidence-loop");
  });

  it("only returns valid loop ids", () => {
    const validIds = new Set(looposData.loops.map((loop) => loop.loop_id));
    const recommendations = recommendLoops(input({ title: "Agentic AI release governance", description: "Need controls and validation." }), looposData);
    expect(recommendations.length).toBeGreaterThan(0);
    for (const recommendation of recommendations) {
      expect(validIds.has(recommendation.loop_id)).toBe(true);
    }
  });

  it("records capped source evidence without changing source-free recommendations", () => {
    const useCase = input({ title: "Enterprise assistant", description: "Improve an enterprise AI workflow." });
    const baseline = recommendLoops(useCase, looposData);
    const source = {
      source_id: "source-agent-policy",
      kind: "document",
      label: "agent-policy.md",
      mime_type: "text/markdown",
      status: "accepted",
      accepted_text: "Agent delegation must require tool execution validation, memory controls, access governance, guardrails, and audit logging.",
      extraction_method: "browser text reader",
      character_count: 118,
      created_at: "2026-07-18T00:00:00.000Z",
      warnings: [],
      truncated: false,
    };

    const recommendations = recommendLoops(useCase, looposData, { sources: [source] } as never);
    const toolValidation = recommendations.find((item) => item.loop_id === "loop-069-tool-execution-validation-loop");

    expect(recommendLoops(useCase, looposData)).toEqual(baseline);
    expect(toolValidation?.factors).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: "source evidence", source: "agent-policy.md", source_ref: "source-agent-policy" }),
      ]),
    );
    expect(toolValidation?.factors.filter((factor) => factor.label === "source evidence")).toHaveLength(1);
    expect(toolValidation?.factors.find((factor) => factor.label === "source evidence")?.weight).toBeLessThanOrEqual(8);
  });

  it("caps all source-derived weight for a loop across multiple documents", () => {
    const useCase = input({ title: "Enterprise workflow", description: "Assess the operating workflow." });
    const sources = ["policy", "architecture", "risk"].map((label, index) => ({
      source_id: `source-${index}`,
      kind: "document",
      label: `${label}.md`,
      mime_type: "text/markdown",
      status: "accepted",
      accepted_text: "Agent tool execution validation requires delegated access controls and audit evidence.",
      extraction_method: "browser text reader",
      character_count: 82,
      created_at: "2026-07-18T00:00:00.000Z",
      warnings: [],
      truncated: false,
    }));

    const recommendation = recommendLoops(useCase, looposData, { sources } as never)
      .find((item) => item.loop_id === "loop-069-tool-execution-validation-loop");
    const sourceWeight = recommendation?.factors
      .filter((factor) => factor.label === "source evidence")
      .reduce((total, factor) => total + factor.weight, 0) ?? 0;

    expect(sourceWeight).toBeGreaterThan(0);
    expect(sourceWeight).toBeLessThanOrEqual(8);
  });

  it("routes RAG and GenAI evidence from accepted documents", () => {
    const useCase = input({ title: "Portfolio capability assessment", description: "Assess a proposed enterprise workflow." });
    const source = (source_id: string, accepted_text: string) => ({
      source_id,
      kind: "document",
      label: `${source_id}.md`,
      mime_type: "text/markdown",
      status: "accepted",
      accepted_text,
      extraction_method: "browser text reader",
      character_count: accepted_text.length,
      created_at: "2026-07-18T00:00:00.000Z",
      warnings: [],
      truncated: false,
    });

    const ragIds = recommendLoops(useCase, looposData, {
      sources: [source("rag-brief", "RAG retrieval quality needs grounded citations, knowledge freshness, hallucination reduction, drift, feedback, lineage, and privacy.")],
    } as never).map((item) => item.loop_id);
    const genAiIds = recommendLoops(useCase, looposData, {
      sources: [source("genai-brief", "A new GenAI copilot needs prompt engineering, model evaluation, AI safety, data preparation, release monitoring, and compliance evidence.")],
    } as never).map((item) => item.loop_id);

    expect(ragIds).toEqual(expect.arrayContaining([
      "loop-055-knowledge-base-freshness-and-rag-content-lifecycle-loop",
      "loop-059-rag-quality-loop",
      "loop-061-hallucination-reduction-loop",
    ]));
    expect(genAiIds).toEqual(expect.arrayContaining([
      "loop-002-ai-use-case-validation-loop",
      "loop-057-prompt-engineering-loop",
      "loop-060-ai-safety-and-responsible-ai-loop",
    ]));
  });
});
