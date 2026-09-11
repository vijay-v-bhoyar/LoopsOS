import { describe, expect, it, vi } from "vitest";
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

  it("falls back when an LLM returns an invalid question contract", async () => {
    vi.stubEnv("VITE_LOOPOS_LLM_ENDPOINT", "https://enterprise.example/questions");
    vi.resetModules();
    const { getQuestionSuggestions: getSuggestions } = await import("./questionAssistant");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      questions: [{ question: "Unsafe target", why_it_matters: "bad", target_field: "admin" }],
    }), { status: 200 }));

    const questions = await getSuggestions(input, recommendations, { consent: true });

    expect(questions.every((question) => question.source === "deterministic fallback")).toBe(true);
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("does not send workspace details without explicit outbound consent", async () => {
    vi.stubEnv("VITE_LOOPOS_LLM_ENDPOINT", "https://enterprise.example/questions");
    vi.resetModules();
    const { getQuestionSuggestions: getSuggestions } = await import("./questionAssistant");
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    fetchSpy.mockClear();

    const questions = await getSuggestions(input, recommendations, { consent: false });

    expect(questions.every((question) => question.source === "deterministic fallback")).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
    vi.resetModules();
  });
});
