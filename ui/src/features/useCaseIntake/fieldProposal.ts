import type { AIProvenance, UseCaseDraft, UseCaseFieldProposal, UseCaseInput, UseCaseSource, UseCaseTextField } from "../../types";
import { nowIso, uid } from "../../lib/workspaceStore";
import { requestAttestedLlm } from "../../lib/llmProvenance";

const FIELD_ORDER: UseCaseTextField[] = [
  "title",
  "description",
  "environment",
  "aiScope",
  "dataSensitivity",
  "businessOutcome",
  "maturity",
  "constraints",
];

const ENUM_VALUES: Partial<Record<UseCaseTextField, string[]>> = {
  environment: ["development", "pilot", "production", "enterprise portfolio"],
  aiScope: ["AI readiness", "GenAI use case", "Agentic AI", "RAG improvement", "Existing use-case enhancement", "Release/compliance governance"],
  dataSensitivity: ["low", "internal", "sensitive", "regulated", "restricted"],
  maturity: ["idea", "discovery", "pilot", "production", "scale"],
};

const LABELS: Record<UseCaseTextField, RegExp> = {
  title: /^title\s*:\s*(.+)$/im,
  description: /^(?:workflow|workflow and problem|description)\s*:\s*(.+)$/im,
  environment: /^environment\s*:\s*(.+)$/im,
  aiScope: /^ai scope\s*:\s*(.+)$/im,
  dataSensitivity: /^data sensitivity\s*:\s*(.+)$/im,
  businessOutcome: /^business outcome\s*:\s*(.+)$/im,
  maturity: /^maturity\s*:\s*(.+)$/im,
  constraints: /^constraints?\s*:\s*(.+)$/im,
};

const MAX_LENGTH: Record<UseCaseTextField, number> = {
  title: 160,
  description: 5_000,
  environment: 80,
  aiScope: 120,
  dataSensitivity: 80,
  businessOutcome: 1_000,
  maturity: 80,
  constraints: 2_000,
};

function provenance(source: AIProvenance["source"], consent_granted: boolean, prompt_version: string): AIProvenance {
  return {
    source,
    provider: "LoopOS",
    model: "rules",
    prompt_version,
    consent_granted,
    generated_at: nowIso(),
  };
}

function allowsExternalStructuring(input: UseCaseInput): boolean {
  return input.dataSensitivity === "low" || input.dataSensitivity === "internal";
}

function canonicalEnum(field: UseCaseTextField, value: string): string | null {
  const allowed = ENUM_VALUES[field];
  if (!allowed) return value.trim();
  return allowed.find((candidate) => candidate.toLowerCase() === value.trim().toLowerCase()) ?? null;
}

function evidenceFor(text: string, value: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  const index = normalized.toLowerCase().indexOf(value.toLowerCase());
  const start = Math.max(0, index >= 0 ? index - 40 : 0);
  const end = Math.min(normalized.length, (index >= 0 ? index + value.length : 0) + 140);
  return `${start > 0 ? "..." : ""}${normalized.slice(start, end)}${end < normalized.length ? "..." : ""}`;
}

function inferredValue(field: UseCaseTextField, source: UseCaseSource): string | null {
  const text = source.accepted_text;
  const labeled = text.match(LABELS[field])?.[1]?.trim();
  if (labeled) return canonicalEnum(field, labeled);
  if (field === "title") return text.match(/^#\s+(.+)$/m)?.[1]?.trim().slice(0, MAX_LENGTH.title) ?? null;
  if (field === "description") {
    return text
      .split(/\n+/)
      .map((line) => line.replace(/^#+\s*/, "").trim())
      .find((line) => line.length >= 40 && !/^(environment|ai scope|data sensitivity|business outcome|maturity|constraints?)\s*:/i.test(line)) ?? null;
  }
  const lower = text.toLowerCase();
  if (field === "aiScope") {
    if (/\bagent(ic)?\b/.test(lower)) return "Agentic AI";
    if (/\brag\b|retrieval/.test(lower)) return "RAG improvement";
    if (/genai|generative|\bllm\b|prompt/.test(lower)) return "GenAI use case";
  }
  if (field === "dataSensitivity") {
    return ["restricted", "regulated", "sensitive", "internal", "low"].find((value) => lower.includes(value)) ?? null;
  }
  if (field === "maturity") {
    return ["scale", "production", "pilot", "discovery", "idea"].find((value) => lower.includes(value)) ?? null;
  }
  if (field === "environment") {
    return ["enterprise portfolio", "production", "pilot", "development"].find((value) => lower.includes(value)) ?? null;
  }
  return null;
}

export function proposeUseCaseFields(source: UseCaseSource, _current: UseCaseInput): UseCaseDraft {
  const fields = FIELD_ORDER.flatMap<UseCaseFieldProposal>((field) => {
    const value = inferredValue(field, source);
    if (!value) return [];
    return [{
      field,
      value: value.slice(0, MAX_LENGTH[field]),
      evidence_excerpt: evidenceFor(source.accepted_text, value),
      source_ids: [source.source_id],
      method: "deterministic",
      provenance: provenance("deterministic", false, "loopos_use_case_structuring_rules_v1"),
    }];
  });
  if (!fields.length) {
    const fallbackDescription = source.accepted_text.replace(/\s+/g, " ").trim().slice(0, MAX_LENGTH.description);
    if (fallbackDescription) {
      fields.push({
        field: "description",
        value: fallbackDescription,
        evidence_excerpt: evidenceFor(source.accepted_text, fallbackDescription),
        source_ids: [source.source_id],
        method: "deterministic",
        provenance: provenance("deterministic", false, "loopos_use_case_structuring_rules_v1"),
      });
    }
  }
  return {
    draft_id: uid("draft"),
    source_ids: [source.source_id],
    fields,
    method: "deterministic",
    created_at: nowIso(),
    provenance: provenance("deterministic", false, "loopos_use_case_structuring_rules_v1"),
  };
}

export function applyUseCaseDraft(current: UseCaseInput, draft: UseCaseDraft, selected: Set<keyof UseCaseInput>): UseCaseInput {
  const next = { ...current };
  for (const proposal of draft.fields) {
    if (selected.has(proposal.field)) next[proposal.field] = proposal.value;
  }
  return next;
}

interface EnhancementOptions {
  endpoint: string;
  consent: boolean;
  fetchImpl?: typeof fetch;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export async function enhanceUseCaseProposal(
  source: UseCaseSource,
  current: UseCaseInput,
  deterministic: UseCaseDraft,
  options: EnhancementOptions,
): Promise<UseCaseDraft> {
  const proposed = applyUseCaseDraft(current, deterministic, new Set(deterministic.fields.map((field) => field.field)));
  // Source-derived fields may raise the restriction but cannot downgrade the saved classification.
  if (!options.consent || !allowsExternalStructuring(current) || !allowsExternalStructuring(proposed)) return deterministic;
  try {
    const attested = await requestAttestedLlm(options.endpoint, "loopos_use_case_structuring", "loopos_use_case_structuring_v1",
      { source, currentUseCase: proposed }, options.fetchImpl);
    const payload = attested.result;
    if (!isRecord(payload) || !isRecord(payload.proposal)) return deterministic;
    const replacements = new Map<UseCaseTextField, UseCaseFieldProposal>();
    for (const field of FIELD_ORDER) {
      const raw = payload.proposal[field];
      if (typeof raw !== "string" || !raw.trim()) continue;
      const value = canonicalEnum(field, raw);
      if (!value) continue;
      replacements.set(field, {
        field,
        value: value.slice(0, MAX_LENGTH[field]),
        evidence_excerpt: evidenceFor(source.accepted_text, value),
        source_ids: [source.source_id],
        method: "enterprise LLM",
        provenance: attested.provenance,
      });
    }
    if (!replacements.size) return deterministic;
    const deterministicByField = new Map(deterministic.fields.map((field) => [field.field, field]));
    const fields = FIELD_ORDER.flatMap<UseCaseFieldProposal>((field) => {
      const proposal = replacements.get(field) ?? deterministicByField.get(field);
      return proposal ? [proposal] : [];
    });
    return {
      draft_id: uid("draft"),
      source_ids: [source.source_id],
      fields,
      method: "enterprise LLM",
      created_at: nowIso(),
      provenance: attested.provenance,
    };
  } catch {
    return deterministic;
  }
}
