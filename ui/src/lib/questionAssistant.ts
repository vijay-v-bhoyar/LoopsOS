import type { LoopRecommendation, QuestionSuggestion, UseCaseInput } from "../types";
import { uid } from "./workspaceStore";
import { secureJsonRequest } from "./secureRequest";
import { llmEndpoint, llmTimeoutMs } from "./runtimeConfig";

type QuestionTargetField = QuestionSuggestion["target_field"];

interface QuestionResponse {
  questions: Array<{
    question: string;
    why_it_matters: string;
    target_field: QuestionTargetField;
  }>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isQuestionTargetField(value: unknown): value is QuestionTargetField {
  return value === "businessOutcome" || value === "ownerEvidence" || value === "approval" || value === "execution" || value === "constraints";
}

function isQuestionResponse(value: unknown): value is QuestionResponse {
  return isRecord(value)
    && Array.isArray(value.questions)
    && value.questions.every((question) => isRecord(question)
      && typeof question.question === "string"
      && question.question.trim().length > 0
      && question.question.length <= 1_000
      && typeof question.why_it_matters === "string"
      && question.why_it_matters.trim().length > 0
      && question.why_it_matters.length <= 2_000
      && isQuestionTargetField(question.target_field));
}

export function buildDeterministicQuestions(input: UseCaseInput, recommendations: LoopRecommendation[]): QuestionSuggestion[] {
  const text = `${input.title} ${input.description} ${input.businessOutcome} ${input.constraints}`.toLowerCase();
  const questions: Array<Omit<QuestionSuggestion, "question_id" | "source">> = [];

  if (!input.businessOutcome.trim()) {
    questions.push({
      question: "What measurable business outcome should this use case improve in the first 30 days?",
      why_it_matters: "LoopOS needs an outcome to choose metric packs and decide whether effectiveness is proven.",
      target_field: "businessOutcome",
    });
  }

  if (!/owner|approver|gate|risk owner/.test(text)) {
    questions.push({
      question: "Who is the named policy owner, gate owner, and validator for this use case?",
      why_it_matters: "Approvals and ACTIVE-loop promotion require accountable humans or teams.",
      target_field: "ownerEvidence",
    });
  }

  if (!/evidence|system|source|log|ci|observability|ticket/.test(text)) {
    questions.push({
      question: "Which authoritative systems will provide evidence for trigger, action, validation, and effectiveness?",
      why_it_matters: "The recommendation is only operational when evidence is source-bound and current.",
      target_field: "ownerEvidence",
    });
  }

  if (recommendations.some((item) => item.role === "governance")) {
    questions.push({
      question: "Which governance decision must be approved before this use case can move from discovery to pilot?",
      why_it_matters: "Governance loops should produce explicit approvals, not meeting-memory.",
      target_field: "approval",
    });
  }

  if (recommendations.some((item) => item.role === "validation")) {
    questions.push({
      question: "What proof run will show immediate correctness, and what observation window will prove effectiveness?",
      why_it_matters: "LoopOS separates action applied from effectiveness proven.",
      target_field: "execution",
    });
  }

  questions.push({
    question: "What would make this use case unsafe, non-compliant, or too expensive to continue?",
    why_it_matters: "A clear stop condition prevents silent drift into high-risk execution.",
    target_field: "constraints",
  });

  return questions.slice(0, 6).map((question) => ({
    ...question,
    question_id: uid("question"),
    source: "deterministic fallback",
  }));
}

export async function getQuestionSuggestions(
  input: UseCaseInput,
  recommendations: LoopRecommendation[],
  options: { consent: boolean },
): Promise<QuestionSuggestion[]> {
  const endpoint = llmEndpoint();
  if (!endpoint || !options.consent) {
    return buildDeterministicQuestions(input, recommendations);
  }

  try {
    const payload = await secureJsonRequest<QuestionResponse>(endpoint, {
      init: {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          task: "loopos_use_case_questions",
          useCase: input,
          recommendations: recommendations.slice(0, 10),
        }),
      },
      timeoutMs: llmTimeoutMs(),
      validate: isQuestionResponse,
    });
    const questions = payload.questions;
    if (!questions.length) return buildDeterministicQuestions(input, recommendations);
    return questions.slice(0, 6).map((question) => ({
      ...question,
      question_id: uid("question"),
      source: "LLM endpoint",
    }));
  } catch {
    return buildDeterministicQuestions(input, recommendations);
  }
}
