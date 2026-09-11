import { AlertTriangle, CheckCircle2, Database, Fingerprint, Gauge, LockKeyhole, Megaphone, ShieldCheck, Sparkles, TestTube2, Workflow, XCircle } from "lucide-react";
import { Badge } from "../components/Badge";
import { SectionHeader } from "../components/Card";
import { InlineNote } from "../components/Help";
import { deploymentPosture, DEPLOYMENT_STATUS_LABELS, type BindingStatus, type DeploymentPosture } from "../lib/deployment";
import type { LoopOSData } from "../types";

const CAPABILITIES = [
  { title: "AI use-case intake", icon: Sparkles, terms: ["AI Use-Case Validation", "Business Value", "Responsible AI"] },
  { title: "Data and RAG readiness", icon: Database, terms: ["Data Governance", "Knowledge Base Freshness", "RAG Quality"] },
  { title: "Model lifecycle", icon: Gauge, terms: ["Model Evaluation", "Drift Monitoring", "Model Lifecycle"] },
  { title: "Agent governance", icon: Workflow, terms: ["Tool Execution", "Agent Memory", "Agent Guardrail"] },
  { title: "Security and access", icon: LockKeyhole, terms: ["Access Governance", "Credential", "Secure SDLC"] },
  { title: "Compliance evidence", icon: ShieldCheck, terms: ["Compliance Evidence", "Audit Logging", "Legal"] },
  { title: "Evaluation and tests", icon: TestTube2, terms: ["Regression Testing", "Evaluation Dataset", "Golden"] },
  { title: "Adoption and workforce", icon: Megaphone, terms: ["Adoption", "Workforce", "Human Oversight"] },
  { title: "Identity and accountability", icon: Fingerprint, terms: ["Delegation", "Accountability", "Forensic"] },
];

export function ReadinessWorkbench({ data, posture = deploymentPosture }: { data: LoopOSData; posture?: DeploymentPosture }) {
  const knownActivationGaps = data.stats.known_activation_gaps;

  return (
    <div className="space-y-6">
      <section className="surface p-4">
        <SectionHeader
          title="Enterprise Activation Readiness"
          description={`${posture.environmentName}. Runtime authority is evaluated separately from corpus validity and use-case readiness.`}
          action={<Badge tone={posture.enterpriseReady ? "success" : "warning"}>{DEPLOYMENT_STATUS_LABELS[posture.status]}</Badge>}
        />
        {!posture.enterpriseReady ? (
          <InlineNote tone="warning">
            Production activation is not authorized. Resolve every blocked binding and pass runtime identity, persistence, and audit probes.
          </InlineNote>
        ) : (
          <InlineNote>
            Runtime deployment bindings and probes are passing. This proves the authority plane only; it does not authorize a pilot or production use case.
          </InlineNote>
        )}
        {knownActivationGaps > 0 ? (
          <InlineNote tone="warning">
            Pilot activation remains separately gated by {knownActivationGaps} known corpus activation gap{knownActivationGaps === 1 ? "" : "s"}. Bind named owners, authoritative evidence, metric targets, executable probes, and real fixtures before treating a use case as ready.
          </InlineNote>
        ) : null}
        <div className="mt-4 divide-y divide-border2 border-y border-border2">
          {posture.bindings.map((binding) => (
            <div key={binding.id} className="grid gap-2 py-3 md:grid-cols-[minmax(12rem,0.45fr)_1fr_auto] md:items-center">
              <div className="flex items-center gap-2 text-sm font-semibold text-fg1">
                <BindingIcon status={binding.status} />
                {binding.label}
              </div>
              <div className="text-sm text-fg2">{binding.detail}</div>
              <Badge tone={binding.status === "bound" ? "success" : binding.status === "blocked" ? "danger" : "warning"}>{binding.status}</Badge>
            </div>
          ))}
        </div>
      </section>

      {data.practicality_gaps.length > 0 ? (
        <section className="surface p-4" aria-label="Pilot Activation Gate">
          <SectionHeader
            title="Pilot Activation Gate"
            description="The corpus is structurally valid, but these organization-owned bindings must be resolved before a pilot can become authoritative."
          />
          <div className="grid gap-3 md:grid-cols-2">
            {data.practicality_gaps.map((gap) => {
              const severity = gap.severity ?? "activation review";
              return (
                <article key={gap.gap_id} className="rounded-panel border border-border2 bg-bg1 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="font-semibold capitalize text-fg1">{formatGapLabel(gap.gap_id)}</h3>
                    <Badge tone={severity.includes("blocker") ? "danger" : "warning"}>{formatGapLabel(severity)}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-fg2">{gap.description}</p>
                  <p className="mt-3 text-sm text-fg1">
                    <span className="font-semibold">Required next step:</span> {gap.required_fix}
                  </p>
                </article>
              );
            })}
          </div>
          <InlineNote tone="warning">
            Workspace owner/evidence edits are proposals only. They do not promote placeholders, bind external systems, or authorize production use.
          </InlineNote>
        </section>
      ) : null}

      <section>
        <SectionHeader
          title="AI, GenAI, And Agentic Readiness Workbench"
          description="Capability areas and the LoopOS loops that make each enterprise outcome operational."
        />
        <div className="grid gap-4 lg:grid-cols-3">
        {CAPABILITIES.map((capability) => {
          const matches = data.loops.filter((loop) => capability.terms.some((term) => `${loop.name} ${loop.category_name}`.toLowerCase().includes(term.toLowerCase())));
          const Icon = capability.icon;
          return (
            <div key={capability.title} className="rounded-panel border border-border2 bg-bg1 p-4">
              <div className="mb-3 flex items-center gap-3">
                <div className="rounded-panel bg-brandSubtle p-2 text-brand">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div className="font-semibold text-fg1">{capability.title}</div>
              </div>
              <ul className="space-y-2 text-sm text-fg2">
                {matches.slice(0, 5).map((loop) => (
                  <li key={loop.loop_id}>{loop.name}</li>
                ))}
              </ul>
            </div>
          );
        })}
        </div>
      </section>
    </div>
  );
}

function formatGapLabel(value: string | undefined): string {
  return (value ?? "").replace(/[_-]+/g, " ");
}

function BindingIcon({ status }: { status: BindingStatus }) {
  if (status === "bound") return <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />;
  if (status === "blocked") return <XCircle className="h-4 w-4 text-danger" aria-hidden="true" />;
  return <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />;
}
