import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardList, FileCheck2, GitBranch, Gauge, ListChecks, MonitorCheck, Route, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, riskTone } from "./Badge";
import { Card, SectionHeader } from "./Card";
import { HelpPopover } from "./Help";
import type { LoopDetail } from "../types";
import { compactList } from "../lib/loopos";

const RUN_SEQUENCE = [
  "Trigger",
  "Qualify",
  "Observe",
  "Diagnose",
  "Prioritize",
  "Plan",
  "Authorize",
  "Execute",
  "Validate",
  "Recover if needed",
  "Record",
  "Learn",
  "Standardize",
  "Monitor effectiveness",
  "Repeat, pause, or retire",
];

export function LoopDetailPanel({ loop }: { loop: LoopDetail | null }) {
  if (!loop) {
    return (
      <Card className="h-full">
        <SectionHeader title="Loop Detail" description="Select a loop to inspect controls, proof, metrics, and graph handoffs." />
        <div className="rounded-panel border border-dashed border-border1 bg-bg2 p-6 text-sm text-fg2">No loop selected.</div>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge tone="brand">Loop {loop.number}</Badge>
            <Badge tone={riskTone(loop.baseline_risk_tier)}>{loop.baseline_risk_tier}</Badge>
            <Badge>{loop.cadence}</Badge>
          </div>
          <h2 className="text-xl font-semibold text-fg1">{loop.name}</h2>
          <p className="mt-1 text-sm text-fg2">{loop.category_name}</p>
        </div>
        <HelpPopover helpKey="risk" />
      </div>

      <div className="grid gap-3">
        <InfoBlock title="Trigger" body={loop.trigger} />
        <InfoBlock title="Outcome" body={loop.output} />
        <InfoBlock title="Run Summary" body={loop.run} />
      </div>

      <section className="mt-5" aria-labelledby="loop-run-sequence">
        <div className="mb-2 flex items-center gap-2">
          <Route className="h-4 w-4 text-brand" aria-hidden="true" />
          <h3 id="loop-run-sequence" className="text-base font-semibold text-fg1">Production-Grade Run Sequence</h3>
        </div>
        <ol className="grid gap-2 md:grid-cols-3">
          {RUN_SEQUENCE.map((step, index) => (
            <li key={step} className="rounded-panel border border-border2 bg-bg2 p-3">
              <div className="text-xs font-semibold text-brand">Step {index + 1}</div>
              <div className="mt-1 text-sm font-semibold text-fg1">{step}</div>
            </li>
          ))}
        </ol>
      </section>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <DetailList
          icon={<ClipboardList className="h-4 w-4" aria-hidden="true" />}
          title="First 10 Minutes"
          values={loop.operation_card.first_10_minutes}
        />
        <DetailList
          icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
          title="Evidence To Collect"
          values={loop.operation_card.evidence_to_collect}
        />
        <DetailList
          icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
          title="Proof To Run"
          values={loop.operation_card.proof_to_run}
        />
        <DetailList
          icon={<ListChecks className="h-4 w-4" aria-hidden="true" />}
          title="Success Criteria"
          values={loop.operation_card.success_criteria}
        />
        <DetailList
          icon={<AlertTriangle className="h-4 w-4" aria-hidden="true" />}
          title="Do Not Run If"
          values={loop.operation_card.when_to_run.do_not_run_if}
        />
        <DetailList
          icon={<AlertTriangle className="h-4 w-4" aria-hidden="true" />}
          title="Common Failure Modes"
          values={loop.operation_card.common_failure_modes}
        />
        <DetailList
          icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
          title="Handoff Rules"
          values={loop.operation_card.handoff_rules}
        />
        <DetailList
          icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
          title="Minimum Viable Record"
          values={loop.operation_card.minimum_viable_record}
        />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <MetricPanel loop={loop} />
        <GoldenTaskPanel loop={loop} />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <ControlPanel loop={loop} />
        <GraphPanel loop={loop} />
      </div>
    </Card>
  );
}

function InfoBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-fg3">{title}</div>
      <div className="mt-1 text-sm text-fg1">{body}</div>
    </div>
  );
}

function DetailList({ icon, title, values }: { icon: ReactNode; title: string; values: string[] }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg1 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
        <span className="text-brand">{icon}</span>
        {title}
      </div>
      <ul className="space-y-1 text-sm text-fg2">
        {(values.length ? values : [compactList(values)]).map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </div>
  );
}

function MetricPanel({ loop }: { loop: LoopDetail }) {
  return (
    <section className="rounded-panel border border-border2 bg-bg2 p-3" aria-labelledby="loop-metrics">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
        <Gauge className="h-4 w-4 text-brand" aria-hidden="true" />
        <h3 id="loop-metrics">Metrics And Monitoring</h3>
      </div>
      <div className="rounded-panel border border-border2 bg-bg1 p-3 text-sm">
        <div className="font-semibold text-fg1">{loop.metric_pack.primary_metric.name}</div>
        <div className="mt-1 text-fg2">{loop.metric_pack.primary_metric.formula}</div>
        <div className="mt-2 text-xs text-fg3">Target: {loop.metric_pack.primary_metric.target_value}</div>
        <div className="mt-1 text-xs text-fg3">Window: {loop.metric_pack.primary_metric.observation_window}</div>
      </div>
      <div className="mt-3 grid gap-3">
        <MiniList title="Guardrails" values={loop.metric_pack.guardrails} />
        <MiniList title="Health metrics" values={loop.metric_pack.health_metrics} />
      </div>
    </section>
  );
}

function GoldenTaskPanel({ loop }: { loop: LoopDetail }) {
  return (
    <section className="rounded-panel border border-border2 bg-bg2 p-3" aria-labelledby="loop-golden-tasks">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
        <MonitorCheck className="h-4 w-4 text-brand" aria-hidden="true" />
        <h3 id="loop-golden-tasks">Golden Tasks And Expected Outputs</h3>
      </div>
      <div className="space-y-2">
        {loop.golden_tasks.tasks.map((task) => (
          <div key={task.task_id} className="rounded-panel border border-border2 bg-bg1 p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge>{task.type}</Badge>
              <Badge>{task.task_id}</Badge>
            </div>
            <div className="text-sm font-semibold text-fg1">{task.scenario}</div>
            <div className="mt-1 text-sm text-fg2">{task.expected}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ControlPanel({ loop }: { loop: LoopDetail }) {
  return (
    <section className="rounded-panel border border-border2 bg-bg2 p-3" aria-labelledby="loop-controls">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
        <ShieldCheck className="h-4 w-4 text-brand" aria-hidden="true" />
        <h3 id="loop-controls">Controls This Loop Must Satisfy</h3>
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        <Badge>{loop.control_profile.applicable_control_ids.length} controls in profile</Badge>
        <Badge tone={riskTone(loop.control_profile.baseline_risk_tier)}>{loop.control_profile.baseline_risk_tier}</Badge>
      </div>
      <div className="mb-3 rounded-panel border border-border2 bg-bg1 p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg3">Applicable control IDs</div>
        <div className="flex max-h-32 flex-wrap gap-1 overflow-auto">
          {loop.control_profile.applicable_control_ids.map((controlId) => (
            <span key={controlId} className="rounded-control border border-border2 bg-bg2 px-2 py-1 text-xs font-semibold text-fg2">{controlId}</span>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {loop.control_preview.map((control) => (
          <div key={control.control_id} className="rounded-panel border border-border2 bg-bg1 p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge>{control.control_id}</Badge>
              <Badge>{control.proof_required}</Badge>
              <Badge tone={riskTone(control.minimum_risk_tier)}>{control.minimum_risk_tier}+</Badge>
            </div>
            <div className="text-sm font-semibold text-fg1">{control.control_name}</div>
            <div className="mt-1 text-xs text-fg2">{control.minimum_proof}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function GraphPanel({ loop }: { loop: LoopDetail }) {
  const outgoing = loop.outgoing_edges.map((edge) => `${edge.event} -> ${edge.to} (${edge.evidence})`);
  const incoming = loop.incoming_edges.map((edge) => `${edge.from} -> ${edge.event} (${edge.evidence})`);
  return (
    <section className="rounded-panel border border-border2 bg-bg2 p-3" aria-labelledby="loop-graph">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
        <GitBranch className="h-4 w-4 text-brand" aria-hidden="true" />
        <h3 id="loop-graph">Connected Loop Handoffs</h3>
      </div>
      <div className="grid gap-3">
        <MiniList title="Incoming" values={incoming} />
        <MiniList title="Outgoing" values={outgoing} />
      </div>
    </section>
  );
}

function MiniList({ title, values }: { title: string; values: string[] }) {
  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg3">{title}</div>
      <ul className="space-y-1 text-sm text-fg2">
        {(values.length ? values : ["No recorded items."]).map((value) => (
          <li key={value} className="break-words">{value}</li>
        ))}
      </ul>
    </div>
  );
}
