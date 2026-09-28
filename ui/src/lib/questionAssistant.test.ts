import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { signedResponse, testCrypto, testPin } from "../test/ephemeralLlmAttestation";
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
  beforeEach(() => {
    vi.stubGlobal("crypto", testCrypto);
    vi.stubEnv("VITE_LOOPOS_LLM_ENDPOINT", "https://enterprise.example/questions");
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([testPin("https://enterprise.example/questions", "loopos_use_case_questions")]));
  });
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("records gateway-attested identity on questions and uses deterministic fallback for unsigned output", async () => {
    const { getQuestionSuggestions } = await import("./questionAssistant");
    const result = { questions: [{ question: "Which evidence is required?", why_it_matters: "Preserve evidence.", target_field: "ownerEvidence" }] };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => new Response(JSON.stringify(signedResponse(options?.body as string, result))));
    const questions = await getQuestionSuggestions({ ...input, dataSensitivity: "internal" }, recommendations, { consent: true });
    expect(questions).toHaveLength(1);
    expect(questions[0].provenance.gateway_attestation?.verification).toBe("configured-gateway-signature");
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(result)));
    const fallback = await getQuestionSuggestions({ ...input, dataSensitivity: "internal" }, recommendations, { consent: true });
    expect(fallback.every((question) => question.provenance.source === "deterministic" && !question.provenance.gateway_attestation)).toBe(true);
  });
  it("builds deterministic questions with recorded source and target fields", () => {
    const questions = buildDeterministicQuestions(input, recommendations);

    expect(questions.length).toBeGreaterThan(0);
    expect(questions.every((question) => question.source === "deterministic fallback")).toBe(true);
    expect(questions.every((question) => question.provenance.source === "deterministic" && !question.provenance.consent_granted)).toBe(true);
    expect(questions.map((question) => question.target_field)).toContain("ownerEvidence");
    expect(questions.map((question) => question.target_field)).toContain("approval");
    expect(questions.map((question) => question.target_field)).toContain("execution");
  });

  it("falls back when an LLM returns an invalid question contract", async () => {
    vi.stubEnv("VITE_LOOPOS_LLM_ENDPOINT", "https://enterprise.example/questions");
    vi.resetModules();
    const { getQuestionSuggestions: getSuggestions } = await import("./questionAssistant");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => new Response(JSON.stringify(signedResponse(options?.body as string, {
      questions: [{ question: "Unsafe target", why_it_matters: "bad", target_field: "admin" }],
    })), { status: 200 }));

    const questions = await getSuggestions({ ...input, dataSensitivity: "internal" }, recommendations, { consent: true });

    expect(questions.every((question) => question.source === "deterministic fallback")).toBe(true);
    expect(questions.every((question) => question.provenance.source === "deterministic")).toBe(true);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
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

  it("does not send sensitive use cases to an external model even with consent", async () => {
    vi.stubEnv("VITE_LOOPOS_LLM_ENDPOINT", "https://enterprise.example/questions");
    vi.resetModules();
    const { getQuestionSuggestions: getSuggestions } = await import("./questionAssistant");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ questions: [] }), { status: 200 }));

    const questions = await getSuggestions(input, recommendations, { consent: true });

    expect(questions.every((question) => question.provenance.source === "deterministic")).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
    vi.resetModules();
  });
});
