import { AlertTriangle, CheckCircle2, Database, Fingerprint, Gauge, LockKeyhole, Megaphone, ShieldCheck, Sparkles, TestTube2, Workflow, XCircle } from "lucide-react";
import { Badge } from "../components/Badge";
import { SectionHeader } from "../components/Card";
import { InlineNote } from "../components/Help";
import { deploymentPosture, DEPLOYMENT_STATUS_LABELS, type BindingStatus } from "../lib/deployment";
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

export function ReadinessWorkbench({ data }: { data: LoopOSData }) {
  return (
    <div className="space-y-6">
      <section className="surface p-4">
        <SectionHeader
          title="Enterprise Activation Readiness"
          description={`${deploymentPosture.environmentName}. Runtime authority is evaluated separately from corpus validity and use-case readiness.`}
          action={<Badge tone={deploymentPosture.enterpriseReady ? "success" : "warning"}>{DEPLOYMENT_STATUS_LABELS[deploymentPosture.status]}</Badge>}
        />
        {!deploymentPosture.enterpriseReady ? (
          <InlineNote tone="warning">
            Production activation is not authorized. Resolve every blocked binding and pass runtime identity, persistence, and audit probes.
          </InlineNote>
        ) : (
          <InlineNote>All required deployment bindings and runtime probes are recorded as passing.</InlineNote>
        )}
        <div className="mt-4 divide-y divide-border2 border-y border-border2">
          {deploymentPosture.bindings.map((binding) => (
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

function BindingIcon({ status }: { status: BindingStatus }) {
  if (status === "bound") return <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />;
  if (status === "blocked") return <XCircle className="h-4 w-4 text-danger" aria-hidden="true" />;
  return <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />;
}
