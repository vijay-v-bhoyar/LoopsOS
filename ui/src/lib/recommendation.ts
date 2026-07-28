import type { LoopDetail, LoopOSData, LoopRecommendation, MatchFactor, RecommendationContext, UseCaseInput } from "../types";
import { riskRank } from "./loopos";

const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "that",
  "this",
  "into",
  "use",
  "case",
  "build",
  "new",
  "existing",
  "enterprise",
  "ready",
  "readiness",
  "system",
  "platform",
  "improve",
  "enhance",
]);

const ARCHETYPES = [
  {
    id: "agentic-ai-readiness",
    label: "Agentic AI readiness",
    keywords: ["agent", "agentic", "tool", "autonomy", "memory", "credential", "delegation", "multi-agent", "guardrail"],
    loopIds: [
      "loop-066-agent-goal-achievement-loop",
      "loop-067-agent-planning-quality-loop",
      "loop-068-tool-selection-loop",
      "loop-069-tool-execution-validation-loop",
      "loop-070-agent-context-management-loop",
      "loop-071-agent-memory-loop",
      "loop-073-agent-state-consistency-and-idempotency-loop",
      "loop-074-agent-failure-recovery-loop",
      "loop-075-multi-agent-coordination-loop",
      "loop-076-agent-delegation-and-accountability-loop",
      "loop-079-agent-guardrail-loop",
      "loop-080-agent-identity-and-credential-governance-loop",
      "loop-081-access-governance-loop",
      "loop-089-audit-logging-and-forensic-readiness-loop",
      "loop-058-model-evaluation-and-benchmarking-loop",
    ],
  },
  {
    id: "rag-truth",
    label: "RAG and knowledge truth",
    keywords: ["rag", "retrieval", "knowledge", "citation", "grounded", "hallucination", "freshness", "answer"],
    loopIds: [
      "loop-055-knowledge-base-freshness-and-rag-content-lifecycle-loop",
      "loop-056-model-data-and-prompt-lineage-and-reproducibility-loop",
      "loop-059-rag-quality-loop",
      "loop-061-hallucination-reduction-loop",
      "loop-062-model-and-data-drift-monitoring-loop",
      "loop-063-ai-feedback-learning-loop",
      "loop-064-evaluation-dataset-evolution-loop",
      "loop-088-privacy-engineering-and-data-protection-loop",
      "loop-058-model-evaluation-and-benchmarking-loop",
    ],
  },
  {
    id: "genai-new-use-case",
    label: "New GenAI use case",
    keywords: ["genai", "generative", "llm", "prompt", "model", "ai feature", "use-case", "copilot"],
    loopIds: [
      "loop-002-ai-use-case-validation-loop",
      "loop-051-ai-data-preparation-loop",
      "loop-057-prompt-engineering-loop",
      "loop-058-model-evaluation-and-benchmarking-loop",
      "loop-060-ai-safety-and-responsible-ai-loop",
      "loop-065-model-lifecycle-and-upgrade-safety-loop",
      "loop-036-release-readiness-loop",
      "loop-062-model-and-data-drift-monitoring-loop",
      "loop-104-compliance-evidence-loop",
      "loop-089-audit-logging-and-forensic-readiness-loop",
    ],
  },
  {
    id: "release-command-center",
    label: "Release and deployment governance",
    keywords: ["release", "deploy", "deployment", "pipeline", "rollback", "environment", "runbook", "production"],
    loopIds: [
      "loop-008-requirements-traceability-loop",
      "loop-030-regression-testing-loop",
      "loop-031-performance-testing-loop",
      "loop-036-release-readiness-loop",
      "loop-037-operational-readiness-and-runbook-loop",
      "loop-038-deployment-validation-loop",
      "loop-039-environment-drift-loop",
      "loop-040-rollback-backup-and-recovery-loop",
      "loop-041-observability-improvement-loop",
      "loop-043-incident-management-loop",
    ],
  },
  {
    id: "compliance-evidence",
    label: "Compliance evidence and controls",
    keywords: ["audit", "compliance", "regulatory", "evidence", "control", "privacy", "vendor", "license", "access"],
    loopIds: [
      "loop-077-secure-sdlc-loop",
      "loop-081-access-governance-loop",
      "loop-086-software-supply-chain-and-build-integrity-loop",
      "loop-087-ai-supply-chain-security-loop",
      "loop-088-privacy-engineering-and-data-protection-loop",
      "loop-089-audit-logging-and-forensic-readiness-loop",
      "loop-104-compliance-evidence-loop",
      "loop-105-legal-regulatory-and-standards-watch-loop",
      "loop-106-vendor-and-third-party-risk-and-sla-loop",
      "loop-107-ip-copyright-and-license-compliance-loop",
    ],
  },
  {
    id: "incident-prevention",
    label: "Incident prevention and reliability learning",
    keywords: ["incident", "outage", "reliability", "slo", "observability", "problem", "defect", "chaos", "resilience"],
    loopIds: [
      "loop-041-observability-improvement-loop",
      "loop-042-reliability-slo-and-error-budget-management-loop",
      "loop-043-incident-management-loop",
      "loop-044-ai-incident-response-loop",
      "loop-045-problem-management-loop",
      "loop-034-defect-management-loop",
      "loop-030-regression-testing-loop",
      "loop-047-chaos-engineering-and-resilience-testing-loop",
      "loop-014-retrospective-improvement-loop",
    ],
  },
];

function tokenize(value: string): string[] {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter((item) => item.length > 2 && !STOP_WORDS.has(item));
}

function fullText(input: UseCaseInput): string {
  return [
    input.title,
    input.description,
    input.environment,
    input.aiScope,
    input.dataSensitivity,
    input.businessOutcome,
    input.maturity,
    input.constraints,
  ].join(" ");
}

function pushFactor(
  factors: MatchFactor[],
  label: string,
  detail: string,
  weight: number,
  source: string,
  provenance?: Pick<MatchFactor, "source_ref" | "evidence_excerpt">,
): number {
  factors.push({ label, detail, weight, source, ...provenance });
  return weight;
}

function sourceExcerpt(text: string, token: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  const index = normalized.toLowerCase().indexOf(token);
  const start = Math.max(0, index - 48);
  const end = Math.min(normalized.length, index + token.length + 112);
  return `${start > 0 ? "..." : ""}${normalized.slice(start, end)}${end < normalized.length ? "..." : ""}`;
}

function loopSearchText(loop: LoopDetail): string {
  return [
    loop.name,
    loop.category_name,
    loop.trigger,
    loop.run,
    loop.output,
    loop.cadence,
    loop.operation_card.primary_user,
    loop.operation_card.automation_mode,
    loop.operation_card.success_criteria?.join(" "),
    loop.operation_card.evidence_to_collect?.join(" "),
    loop.control_preview.map((control) => `${control.control_name} ${control.section_name}`).join(" "),
  ].join(" ").toLowerCase();
}

function roleFor(loop: LoopDetail, score: number, factors: MatchFactor[]): LoopRecommendation["role"] {
  const haystack = `${loop.name} ${loop.category_name}`.toLowerCase();
  if (/\b(access|audit|compliance|privacy|security|supply-chain|legal|vendor|guardrail|credential)\b/.test(haystack)) {
    return "governance";
  }
  if (/\b(evaluation|testing|validation|quality|regression|benchmark|proof|readiness)\b/.test(haystack)) {
    return "validation";
  }
  if (score >= 20 || factors.some((factor) => factor.label.includes("archetype"))) {
    return "primary";
  }
  return "supporting";
}

export function recommendLoops(input: UseCaseInput, data: LoopOSData, context: RecommendationContext = {}): LoopRecommendation[] {
  const text = fullText(input);
  const acceptedSources = (context.sources ?? []).filter((source) => source.status === "accepted" && source.accepted_text.trim());
  const sourceContextText = acceptedSources.map((source) => source.accepted_text).join(" ");
  const normalized = `${text} ${sourceContextText}`.toLowerCase();
  const tokens = tokenize(text);
  const routingTokens = Array.from(new Set([...tokens, ...tokenize(sourceContextText)]));
  const tokenSet = new Set(tokens);
  const recommendations = new Map<string, { loop: LoopDetail; score: number; factors: MatchFactor[] }>();

  for (const loop of data.loops) {
    let score = 0;
    const factors: MatchFactor[] = [];
    const searchText = loopSearchText(loop);

    for (const token of tokenSet) {
      if (searchText.includes(token)) {
        score += pushFactor(factors, "metadata match", `Matched term "${token}" in loop metadata.`, 2, "loop catalog and operation card");
      }
    }

    if (normalized.includes("enterprise") && loop.category_number === 13) {
      score += pushFactor(factors, "enterprise operating model", "Enterprise scope benefits from adoption, governance, and workforce readiness loops.", 4, "category mapping");
    }

    if (normalized.includes("existing") && /quality|drift|feedback|retrospective|problem|defect/.test(searchText)) {
      score += pushFactor(factors, "existing-use-case improvement", "Existing capabilities need quality, drift, feedback, and learning loops.", 5, "improvement pattern");
    }

    if (input.dataSensitivity && input.dataSensitivity !== "low" && /privacy|access|audit|data governance|security/.test(searchText)) {
      score += pushFactor(factors, "data sensitivity", "Sensitive data needs privacy, access, audit, and security controls.", 6, "risk input");
    }

    if (riskRank(loop.baseline_risk_tier) >= 3 && /agent|security|privacy|compliance|credential|access/.test(normalized)) {
      score += pushFactor(factors, "risk-tier fit", `${loop.baseline_risk_tier} loop aligns with high-control enterprise use.`, 3, "risk tier");
    }

    if (score > 0) {
      recommendations.set(loop.loop_id, { loop, score, factors });
    }
  }

  for (const archetype of ARCHETYPES) {
    const matchedTerms = archetype.keywords.filter((keyword) => normalized.includes(keyword));
    if (!matchedTerms.length) continue;
    for (const loopId of archetype.loopIds) {
      const loop = data.loops.find((item) => item.loop_id === loopId);
      if (!loop) continue;
      const current = recommendations.get(loopId) ?? { loop, score: 0, factors: [] };
      current.score += pushFactor(
        current.factors,
        `archetype: ${archetype.label}`,
        `Matched ${matchedTerms.join(", ")} and routed through the ${archetype.label} pattern.`,
        12 + matchedTerms.length,
        "enterprise archetype map",
      );
      recommendations.set(loopId, current);
    }
  }

  const sourceWeightByLoop = new Map<string, number>();
  for (const source of acceptedSources) {
    const sourceTokens = Array.from(new Set(tokenize(source.accepted_text)));
    for (const loop of data.loops) {
      const matchedTerms = sourceTokens.filter((token) => loopSearchText(loop).includes(token)).slice(0, 4);
      if (!matchedTerms.length) continue;
      const sourceWeightUsed = sourceWeightByLoop.get(loop.loop_id) ?? 0;
      const weight = Math.min(8 - sourceWeightUsed, 2 + matchedTerms.length * 2);
      if (weight <= 0) continue;
      const current = recommendations.get(loop.loop_id) ?? { loop, score: 0, factors: [] };
      current.score += pushFactor(
        current.factors,
        "source evidence",
        `Matched ${matchedTerms.join(", ")} in ${source.label}.`,
        weight,
        source.label,
        { source_ref: source.source_id, evidence_excerpt: sourceExcerpt(source.accepted_text, matchedTerms[0]) },
      );
      sourceWeightByLoop.set(loop.loop_id, sourceWeightUsed + weight);
      recommendations.set(loop.loop_id, current);
    }
  }

  for (const playbook of data.playbooks) {
    const playbookText = `${playbook.title} ${playbook.effort_saving} ${playbook.pilot_scope}`.toLowerCase();
    const playbookMatches = routingTokens.filter((token) => playbookText.includes(token));
    if (!playbookMatches.length) continue;
    for (const loopId of playbook.loops) {
      const loop = data.loops.find((item) => item.loop_id === loopId);
      if (!loop) continue;
      const current = recommendations.get(loopId) ?? { loop, score: 0, factors: [] };
      current.score += pushFactor(
        current.factors,
        "playbook membership",
        `Part of ${playbook.title}, a high-impact pilot playbook.`,
        4,
        playbook.playbook_id,
      );
      recommendations.set(loopId, current);
    }
  }

  return Array.from(recommendations.values())
    .sort((a, b) => b.score - a.score || a.loop.number - b.loop.number)
    .slice(0, 24)
    .map(({ loop, score, factors }, index) => ({
      loop_id: loop.loop_id,
      name: loop.name,
      category_name: loop.category_name,
      risk_tier: loop.baseline_risk_tier,
      role: index > 13 ? "next-step" : roleFor(loop, score, factors),
      score,
      factors: factors.sort((a, b) => b.weight - a.weight).slice(0, 5),
      evidence_refs: [
        loop.descriptor_path,
        `card-${loop.loop_id}`,
        loop.control_profile?.profile_id,
        loop.metric_pack?.metric_pack_ref,
      ].filter(Boolean) as string[],
    }));
}
