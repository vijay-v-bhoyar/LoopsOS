import { describe, expect, it } from "vitest";
import type { LoopRecommendation, UseCaseInput } from "../types";
import { buildDeterministicQuestions } from "./questionAssistant";

const input: UseCaseInput = {
  title: "Prepare enterprise for agentic AI",
  description: "Assess agentic AI readiness for tools, retrieval, memory, and delegated workflows.",
  environment: "enterprise portfolio",
  aiScope: "Agentic AI",
  dataSensitivity: "sensitive",
  businessOutcome: "Reduce governance cycle time without unsafe execution.",
  maturity: "discovery",
  constraints: "Must satisfy audit and compliance needs.",
};

const recommendations: LoopRecommendation[] = [
  {
    loop_id: "loop-079-agent-guardrail-loop",
    name: "Agent Guardrail Loop",
    category_name: "AI Agent Governance",
    risk_tier: "R3",
    role: "governance",
    score: 5,
    factors: [],
    evidence_refs: [],
  },
  {
    loop_id: "loop-058-model-evaluation-and-benchmarking-loop",
    name: "Model Evaluation And Benchmarking Loop",
    category_name: "AI Lifecycle",
    risk_tier: "R2",
    role: "validation",
    score: 4,
    factors: [],
    evidence_refs: [],
  },
];

describe("questionAssistant", () => {
  it("builds deterministic questions with recorded source and target fields", () => {
    const questions = buildDeterministicQuestions(input, recommendations);

    expect(questions.length).toBeGreaterThan(0);
    expect(questions.every((question) => question.source === "deterministic fallback")).toBe(true);
    expect(questions.map((question) => question.target_field)).toContain("ownerEvidence");
    expect(questions.map((question) => question.target_field)).toContain("approval");
    expect(questions.map((question) => question.target_field)).toContain("execution");
  });
});
