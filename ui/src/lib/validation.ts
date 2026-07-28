import type { LoopOSData, LoopRecommendation, UseCaseInput, UseCaseSource, UseCaseValidationResult } from "../types";

function hasEnoughText(value: string, minWords: number): boolean {
  return value.trim().split(/\s+/).filter(Boolean).length >= minWords;
}

export function validateUseCase(
  input: UseCaseInput,
  recommendations: LoopRecommendation[],
  data: LoopOSData,
  sources: UseCaseSource[] = [],
): UseCaseValidationResult {
  const findings: UseCaseValidationResult["findings"] = [];
  const gaps: string[] = [];
  const nextActions: string[] = [];

  const add = (status: "pass" | "gap" | "review", label: string, detail: string) => {
    findings.push({ status, label, detail });
    if (status === "gap") gaps.push(label);
    if (status !== "pass") nextActions.push(detail);
  };

  add(hasEnoughText(input.title, 3) ? "pass" : "gap", "Use-case name", "Name the business capability, not only the technology.");
  add(hasEnoughText(input.description, 10) ? "pass" : "gap", "Workflow description", "Describe trigger, user, current workflow, and expected change.");
  add(input.environment ? "pass" : "gap", "Environment", "Choose whether this applies to development, pilot, production, or enterprise portfolio.");
  add(input.businessOutcome ? "pass" : "gap", "Business outcome", "State measurable value such as reduced cycle time, safer release, better grounded answers, or lower incident recurrence.");
  const acceptedSources = sources.filter((source) => source.status === "accepted");
  add(acceptedSources.length ? "pass" : "review", "Input provenance", "Attach or record a named source when the use case depends on enterprise evidence beyond the structured fields.");
  if (acceptedSources.length) {
    const incompleteSources = acceptedSources.filter((source) => source.truncated || source.warnings.length);
    add(
      incompleteSources.length ? "review" : "pass",
      "Extraction completeness",
      incompleteSources.length
        ? `Review extraction limits or warnings for: ${incompleteSources.map((source) => source.label).join(", ")}.`
        : "Accepted sources were extracted without recorded truncation or parser warnings.",
    );
  }
  add(recommendations.length >= 5 ? "pass" : "review", "Loop coverage", "Review the recommendation input if fewer than five loops are identified.");

  const hasGovernance = recommendations.some((item) => item.role === "governance");
  const hasValidation = recommendations.some((item) => item.role === "validation");
  add(hasGovernance ? "pass" : "review", "Governance coverage", "Add security, privacy, compliance, access, or audit loops before pilot approval.");
  add(hasValidation ? "pass" : "review", "Validation coverage", "Add evaluation, proof, test, or readiness loops before execution.");

  const highRisk = ["regulated", "restricted", "production", "customer", "sensitive", "high"].some((term) =>
    `${input.environment} ${input.dataSensitivity} ${input.constraints}`.toLowerCase().includes(term),
  );
  add(!highRisk || hasGovernance ? "pass" : "gap", "High-risk controls", "Sensitive or production use needs governance loops and human handoff rules.");

  const audit = data.validation.audit;
  add(audit.blockers === 0 ? "pass" : "gap", "Corpus practicality audit", "Resolve corpus audit blockers before relying on recommendations.");

  const draftGaps = data.practicality_gaps.map((gap) => String(gap.gap_id)).join(", ");
  add("review", "Activation gaps", `Framework-level DRAFT gaps still need enterprise binding: ${draftGaps}.`);

  let readiness: UseCaseValidationResult["readiness"] = "Discovery Ready";
  if (gaps.length >= 3) readiness = "Blocked";
  else if (highRisk || findings.some((item) => item.status === "review")) readiness = "Governance Review";
  else if (recommendations.length >= 8) readiness = "Pilot Candidate";

  return {
    readiness,
    corpusStatus: data.validation.corpus_status === "pass" ? "PASS" : "UNKNOWN",
    findings,
    gaps,
    nextActions: Array.from(new Set(nextActions)).slice(0, 8),
  };
}
