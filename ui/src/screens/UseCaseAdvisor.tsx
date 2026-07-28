import { ClipboardCheck, Download, ListChecks, PencilLine, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef } from "react";
import { Badge, riskTone } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, SectionHeader } from "../components/Card";
import { HelpPopover, InlineNote } from "../components/Help";
import { UseCaseIntake } from "../features/useCaseIntake/UseCaseIntake";
import { buildEnterpriseActionPlan } from "../lib/actionPlan";
import { recommendLoops } from "../lib/recommendation";
import { validateUseCase } from "../lib/validation";
import type { EnterpriseActionPlan, LoopDetail, LoopOSData, LoopRecommendation, UseCaseInput, UseCaseSource } from "../types";

const AI_SCOPES = ["AI readiness", "GenAI use case", "Agentic AI", "RAG improvement", "Existing use-case enhancement", "Release/compliance governance"];
const SENSITIVITY = ["low", "internal", "sensitive", "regulated", "restricted"];
const MATURITY = ["idea", "discovery", "pilot", "production", "scale"];
const ENVIRONMENTS = ["development", "pilot", "production", "enterprise portfolio"];

export type AdvisorPane = "input" | "results";

export const DEFAULT_USE_CASE: UseCaseInput = {
  title: "Prepare enterprise for agentic AI",
  description: "We want to assess whether our enterprise is ready to let AI agents use tools, memory, retrieval, and delegated workflows while keeping security, audit, and human approval controls clear.",
  environment: "enterprise portfolio",
  aiScope: "Agentic AI",
  dataSensitivity: "sensitive",
  businessOutcome: "Reduce time to govern agentic AI use cases while preventing unsafe tool execution and missing evidence.",
  maturity: "discovery",
  constraints: "Must support compliance evidence, access controls, audit logging, and human handoffs before production.",
};

export function UseCaseAdvisor({
  data,
  input,
  inputSources,
  workspaceId,
  onInputChange,
  onApplyInputSource,
  onRemoveInputSource,
  onPlanChange,
  onSelectLoop,
  activePane,
  onPaneChange,
}: {
  data: LoopOSData;
  input: UseCaseInput;
  inputSources: UseCaseSource[];
  workspaceId: string;
  onInputChange: (input: UseCaseInput) => void;
  onApplyInputSource: (source: UseCaseSource, input: UseCaseInput) => void;
  onRemoveInputSource: (sourceId: string) => void;
  onPlanChange: (plan: EnterpriseActionPlan) => void;
  onSelectLoop: (loop: LoopDetail) => void;
  activePane: AdvisorPane;
  onPaneChange: (pane: AdvisorPane) => void;
}) {
  const recommendations = useMemo(() => recommendLoops(input, data, { sources: inputSources }), [input, inputSources, data]);
  const validation = useMemo(() => validateUseCase(input, recommendations, data, inputSources), [input, inputSources, recommendations, data]);
  const actionPlan = useMemo(() => buildEnterpriseActionPlan(input, recommendations, validation), [input, recommendations, validation]);
  const resultsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (activePane !== "results") return;
    const frame = window.requestAnimationFrame(() => {
      const results = resultsRef.current;
      if (!results) return;
      if (typeof results.scrollIntoView === "function") {
        const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
        results.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      }
      results.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activePane]);

  const update = (field: keyof UseCaseInput, value: string) => onInputChange({ ...input, [field]: value });

  const downloadPlan = () => {
    onPlanChange(actionPlan);
    const blob = new Blob([actionPlan.exportMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${input.title.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "loopos-action-plan"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const applySourceAndShowResults = (source: UseCaseSource, nextInput: UseCaseInput) => {
    onApplyInputSource(source, nextInput);
    onPaneChange("results");
  };

  return (
    <div>
      <div className="control-muted mb-4 grid grid-cols-2 p-1 xl:hidden" aria-label="Advisor view">
        <button
          type="button"
          aria-controls="advisor-input"
          aria-pressed={activePane === "input"}
          onClick={() => onPaneChange("input")}
          className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-control px-3 text-sm font-semibold ${activePane === "input" ? "bg-bg1 text-brand shadow-card" : "text-fg2 hover:bg-bg1"}`}
        >
          <PencilLine className="h-4 w-4" aria-hidden="true" />
          Show input
        </button>
        <button
          type="button"
          aria-controls="advisor-results"
          aria-pressed={activePane === "results"}
          onClick={() => onPaneChange("results")}
          className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-control px-3 text-sm font-semibold ${activePane === "results" ? "bg-bg1 text-brand shadow-card" : "text-fg2 hover:bg-bg1"}`}
        >
          <ListChecks className="h-4 w-4" aria-hidden="true" />
          Show recommendations ({recommendations.length})
        </button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <div id="advisor-input" className={activePane === "input" ? "" : "hidden xl:block"}>
        <Card>
        <SectionHeader title="Use Case Advisor" description="Enter, attach, or dictate an enterprise use case and receive an explainable loop bundle. Optional AI may structure inputs; loop selection remains deterministic." action={<HelpPopover helpKey="why" />} />
        <UseCaseIntake
          input={input}
          sources={inputSources}
          workspaceId={workspaceId}
          onApply={applySourceAndShowResults}
          onRemoveSource={onRemoveInputSource}
        />
        <div className="space-y-4">
          <Field label="Use-case title">
            <input className="control min-h-10 w-full px-3 text-sm" value={input.title} onChange={(event) => update("title", event.target.value)} />
          </Field>
          <Field label="Workflow and problem">
            <textarea className="control min-h-28 w-full px-3 py-2 text-sm" value={input.description} onChange={(event) => update("description", event.target.value)} />
          </Field>
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="AI scope" value={input.aiScope} values={AI_SCOPES} onChange={(value) => update("aiScope", value)} />
            <SelectField label="Environment" value={input.environment} values={ENVIRONMENTS} onChange={(value) => update("environment", value)} />
            <SelectField label="Data sensitivity" value={input.dataSensitivity} values={SENSITIVITY} onChange={(value) => update("dataSensitivity", value)} />
            <SelectField label="Maturity" value={input.maturity} values={MATURITY} onChange={(value) => update("maturity", value)} />
          </div>
          <Field label="Business outcome">
            <input className="control min-h-10 w-full px-3 text-sm" value={input.businessOutcome} onChange={(event) => update("businessOutcome", event.target.value)} />
          </Field>
          <Field label="Constraints">
            <textarea className="control min-h-20 w-full px-3 py-2 text-sm" value={input.constraints} onChange={(event) => update("constraints", event.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => onPaneChange("results")}>
              <ListChecks className="h-4 w-4" aria-hidden="true" />
              View {recommendations.length} Recommendations
            </Button>
            <Button variant="primary" onClick={() => onPlanChange(actionPlan)}>
              <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
              Send To Action Plan
            </Button>
            <Button onClick={downloadPlan}>
              <Download className="h-4 w-4" aria-hidden="true" />
              Export Markdown
            </Button>
            <Button variant="ghost" onClick={() => onInputChange(DEFAULT_USE_CASE)}>
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Reset Example
            </Button>
          </div>
        </div>
        </Card>
      </div>

      <div
        id="advisor-results"
        ref={resultsRef}
        role="region"
        aria-label="Loop recommendations"
        tabIndex={-1}
        className={`${activePane === "results" ? "" : "hidden xl:block"} scroll-mt-24 space-y-4 focus:outline-none`}
      >
        <Card>
          <SectionHeader
            title="Recommendation Result"
            description={`${recommendations.length} loops matched by metadata, archetypes, playbooks, and risk controls.`}
            action={(
              <>
                <Button className="xl:hidden" variant="ghost" onClick={() => onPaneChange("input")}>
                  <PencilLine className="h-4 w-4" aria-hidden="true" />
                  Edit use case
                </Button>
                <HelpPopover helpKey="readiness" />
              </>
            )}
          />
          <InlineNote tone={validation.readiness === "Blocked" ? "critical" : validation.readiness === "Governance Review" ? "warning" : "info"}>
            Use-case readiness: <strong>{validation.readiness}</strong>. Corpus validation: <strong>{validation.corpusStatus}</strong>.
          </InlineNote>
        </Card>

        <RecommendationGroups recommendations={recommendations} data={data} onSelectLoop={onSelectLoop} />
      </div>
      </div>
    </div>
  );
}

const ROLE_GROUPS: Array<{ role: LoopRecommendation["role"]; title: string }> = [
  { role: "primary", title: "Primary loops" },
  { role: "supporting", title: "Supporting loops" },
  { role: "governance", title: "Governance loops" },
  { role: "validation", title: "Validation loops" },
  { role: "next-step", title: "Next-step loops" },
];

function RecommendationGroups({ recommendations, data, onSelectLoop }: { recommendations: LoopRecommendation[]; data: LoopOSData; onSelectLoop: (loop: LoopDetail) => void }) {
  return (
    <div className="space-y-5">
      {ROLE_GROUPS.map((group) => {
        const items = recommendations.filter((item) => item.role === group.role);
        if (!items.length) return null;
        return (
          <section key={group.role} aria-labelledby={`recommendation-${group.role}`}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 id={`recommendation-${group.role}`} className="text-base font-semibold text-fg1">{group.title}</h3>
              <span className="text-xs text-fg3">{items.length}</span>
            </div>
            <div className="grid gap-3">
              {items.map((item) => (
                <RecommendationRow key={item.loop_id} item={item} onOpen={() => {
                  const loop = data.loops.find((candidate) => candidate.loop_id === item.loop_id);
                  if (loop) onSelectLoop(loop);
                }} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-fg1">{label}</span>
      {children}
    </label>
  );
}

function SelectField({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return (
    <Field label={label}>
      <select className="control min-h-10 w-full px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        {values.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
    </Field>
  );
}

function RecommendationRow({ item, onOpen }: { item: LoopRecommendation; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="surface w-full p-4 text-left hover:border-brand">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge tone={item.role === "primary" ? "brand" : item.role === "governance" ? "warning" : item.role === "validation" ? "success" : "neutral"}>{item.role}</Badge>
        <Badge tone={riskTone(item.risk_tier)}>{item.risk_tier}</Badge>
        <Badge>{item.factors.length} recorded factors</Badge>
      </div>
      <div className="text-base font-semibold text-fg1">{item.name}</div>
      <div className="text-sm text-fg2">{item.category_name}</div>
      <div className="mt-3 rounded-panel border border-border2 bg-bg2 p-3">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg3">Why this loop</div>
        <ul className="space-y-1 text-sm text-fg2">
          {item.factors.slice(0, 3).map((factor) => (
            <li key={`${factor.label}-${factor.detail}`}>
              <div>{factor.detail}</div>
              {factor.source_ref ? <div className="mt-1 text-xs text-fg3">Source record: {factor.source_ref}</div> : null}
              {factor.evidence_excerpt ? <div className="mt-1 border-l border-border1 pl-2 text-xs text-fg3">{factor.evidence_excerpt}</div> : null}
            </li>
          ))}
        </ul>
      </div>
    </button>
  );
}
