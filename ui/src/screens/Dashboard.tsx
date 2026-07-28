import { BookOpenCheck, CheckCircle2, ClipboardList, Download, FileCheck2, FlaskConical, GitBranch, GitPullRequest, Layers3, Link2, LockKeyhole, PlayCircle, ShieldAlert, ShieldCheck, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, SectionHeader } from "../components/Card";
import { HelpPopover } from "../components/Help";
import { StatCard } from "../components/StatCard";
import { deploymentPosture, DEPLOYMENT_STATUS_LABELS } from "../lib/deployment";
import { summarizeGateStatus } from "../lib/releaseAssurance";
import { buildIssueTicketText, workflowLabel } from "../lib/sdlcProductivity";
import type { InitiativeWorkspace, LoopDetail, LoopOSData, LoopRecommendation, PilotPlaybook, SavedWorkspace, UseCaseValidationResult } from "../types";

export function Dashboard({
  data,
  activeWorkspace,
  recommendations,
  validation,
  onOpenAdvisor,
  onOpenPlaybook,
  onOpenWorkspace,
  onOpenValidation,
  onOpenPlan,
  onOpenLoop,
  onRecordDryRun,
  onCreateInitiative,
  onCompleteRunStep,
  onExportProofPack,
}: {
  data: LoopOSData;
  activeWorkspace: SavedWorkspace | null;
  recommendations: LoopRecommendation[];
  validation: UseCaseValidationResult;
  onOpenAdvisor: () => void;
  onOpenPlaybook: (playbook: PilotPlaybook) => void;
  onOpenWorkspace: () => void;
  onOpenValidation: () => void;
  onOpenPlan: () => void;
  onOpenLoop: (loop: LoopDetail) => void;
  onRecordDryRun: () => void;
  onCreateInitiative: () => void;
  onCompleteRunStep: () => void;
  onExportProofPack: () => void;
}) {
  const topRecommendations = recommendations.slice(0, 5);
  const savedPlan = Boolean(activeWorkspace?.action_plan_markdown);
  const selectedLoops = activeWorkspace?.selected_loop_ids.length ?? 0;
  const latestExecution = activeWorkspace?.execution_records[0];
  const activeInitiative = activeWorkspace?.initiatives[0] ?? null;
  const openHandoffs = activeInitiative?.handoffs.filter((handoff) => handoff.status !== "closed").length ?? 0;
  const pendingApprovals = (activeInitiative?.approvals ?? activeWorkspace?.approvals ?? []).filter((approval) => approval.status === "Pending").length;
  const staleEvidence = activeInitiative?.evidence_records.filter((evidence) => evidence.freshness !== "fresh").length ?? 0;
  const activeRun = activeInitiative?.execution_records[0] ?? null;
  const completedSteps = activeRun?.step_records.filter((step) => step.status === "done").length ?? 0;
  const currentStep = activeRun?.step_records.find((step) => step.status === "open") ?? null;
  const releaseAssurance = activeInitiative?.release_assurance;
  const gateCounts = summarizeGateStatus(releaseAssurance);

  return (
    <div className="space-y-6">
      <section className="surface p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge tone="success">Beta pilot ready</Badge>
              <Badge tone="success">Corpus validated</Badge>
              <Badge tone={deploymentPosture.enterpriseReady ? "success" : "warning"}>{DEPLOYMENT_STATUS_LABELS[deploymentPosture.status]}</Badge>
              <Badge>{data.validation.audit.blockers} audit blockers</Badge>
              <Badge>{data.validation.audit.action_required} activation actions</Badge>
            </div>
            <h1 className="text-3xl font-semibold text-fg1">LoopOS Enterprise Console</h1>
            <p className="mt-2 max-w-4xl text-sm text-fg2">
              SDLC Command Center for turning initiatives, incidents, releases, risks, and AI use cases into governed loop bundles with owners, evidence, run records, and measurable effort saved.
            </p>
          </div>
          <button onClick={onOpenAdvisor} className="inline-flex min-h-10 items-center justify-center rounded-control bg-brand px-4 py-2 text-sm font-semibold text-bg1 hover:bg-brandStrong">
            Open Use Case Advisor
          </button>
        </div>
      </section>

      <section className="surface p-5">
        <SectionHeader
          title="SDLC Command Center"
          description="Initiative intake, loop runbooks, handoff control, proof-pack export, and productivity evidence from the active workspace."
          action={<HelpPopover helpKey="readiness" />}
        />
        <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <CommandMetric label="Active initiatives" value={String(activeWorkspace?.initiatives.length ?? 0)} tone="brand" />
          <CommandMetric label="Blocked loops" value={String(validation.gaps.length)} tone={validation.gaps.length ? "warning" : "success"} />
          <CommandMetric label="Stale evidence" value={String(staleEvidence)} tone={staleEvidence ? "warning" : "success"} />
          <CommandMetric label="Pending approvals" value={String(pendingApprovals)} tone={pendingApprovals ? "warning" : "success"} />
          <CommandMetric label="Open handoffs" value={String(openHandoffs)} tone={openHandoffs ? "warning" : "success"} />
          <CommandMetric label="Hours saved" value={String(activeInitiative?.roi_assumptions.hours_saved_estimate ?? 0)} tone="success" />
        </div>
        {releaseAssurance ? (
          <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <CommandMetric label="Release gates passed" value={String(gateCounts.passed)} tone="success" />
            <CommandMetric label="Gate gaps" value={String(gateCounts.gap)} tone={gateCounts.gap ? "warning" : "success"} />
            <CommandMetric label="Review gates" value={String(gateCounts.review_required)} tone={gateCounts.review_required ? "warning" : "success"} />
            <CommandMetric label="Exceptions active" value={String(gateCounts.exception_active)} tone={gateCounts.exception_active ? "warning" : "success"} />
            <CommandMetric label="Release blockers" value={String(gateCounts.blocked)} tone={gateCounts.blocked ? "warning" : "success"} />
          </div>
        ) : null}
        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Badge tone={validation.readiness === "Blocked" ? "danger" : validation.readiness === "Governance Review" ? "warning" : "success"}>{validation.readiness}</Badge>
              <Badge>{recommendations.length} matched loops</Badge>
              <Badge>{selectedLoops} saved loops</Badge>
              <Badge tone={savedPlan ? "success" : "neutral"}>{savedPlan ? "plan saved" : "plan not saved"}</Badge>
              {activeInitiative ? <Badge tone="brand">{workflowLabel(activeInitiative.workflow_type)}</Badge> : null}
            </div>
            <h2 className="text-xl font-semibold text-fg1">{activeInitiative?.title ?? activeWorkspace?.use_case.title ?? "No active workspace"}</h2>
            <p className="mt-2 max-w-4xl text-sm text-fg2">{activeInitiative?.description ?? activeWorkspace?.use_case.description ?? "Create or enter the evaluation workspace to start operating loops."}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <WorkspaceSignal label="Sources" value={String(activeWorkspace?.input_sources.length ?? 0)} />
              <WorkspaceSignal label="Evidence edits" value={String(activeWorkspace?.owner_evidence_edits.length ?? 0)} />
              <WorkspaceSignal label="Approvals" value={String(activeWorkspace?.approvals.length ?? 0)} />
              <WorkspaceSignal label="Executions" value={String(activeWorkspace?.execution_records.length ?? 0)} />
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <Button variant="primary" onClick={onCreateInitiative}>
              <Layers3 className="h-4 w-4" aria-hidden="true" />
              Create SDLC Initiative
            </Button>
            <Button variant="primary" onClick={onOpenAdvisor}>
              <Workflow className="h-4 w-4" aria-hidden="true" />
              Analyze Use Case
            </Button>
            <Button onClick={onOpenPlan}>
              <FileCheck2 className="h-4 w-4" aria-hidden="true" />
              Build Action Plan
            </Button>
            <Button onClick={onOpenValidation}>
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Validate Readiness
            </Button>
            <Button onClick={onOpenWorkspace}>
              <PlayCircle className="h-4 w-4" aria-hidden="true" />
              Prepare Loop Run
            </Button>
            <Button onClick={onRecordDryRun} disabled={!topRecommendations.length || !activeWorkspace}>
              <FlaskConical className="h-4 w-4" aria-hidden="true" />
              Record Dry Run
            </Button>
            <Button onClick={onCompleteRunStep} disabled={!activeRun || !currentStep}>
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Complete Next Run Step
            </Button>
            <Button onClick={onExportProofPack} disabled={!activeInitiative}>
              <Download className="h-4 w-4" aria-hidden="true" />
              Export Proof Pack
            </Button>
          </div>
        </div>
        {activeInitiative ? (
          <InitiativePanel initiative={activeInitiative} currentStep={currentStep} completedSteps={completedSteps} onCompleteRunStep={onCompleteRunStep} />
        ) : null}
        {latestExecution ? (
          <div className="mt-4 rounded-panel border border-border2 bg-bg2 p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge tone="success">latest loop output</Badge>
              <Badge>{latestExecution.validation_result}</Badge>
              <Badge>{latestExecution.proof_state}</Badge>
            </div>
            <div className="text-sm font-semibold text-fg1">{latestExecution.title}</div>
            <div className="mt-1 text-xs text-fg3">Record {latestExecution.correlation_id} owned by {latestExecution.owner}</div>
          </div>
        ) : null}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <HandoffPanel initiative={activeInitiative} data={data} />
        <ProductivityPanel initiative={activeInitiative} />
      </div>

      <ReleaseAssurancePanel initiative={activeInitiative} data={data} />

      <IntegrationReadinessPanel />

      <section className="surface p-5">
        <SectionHeader
          title="Beta Pilot Readiness"
          description="These capabilities are ready for controlled enterprise evaluation. Production authority still depends on the activation bindings below."
        />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PilotReadyItem icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />} title="Advise use cases" detail="Text, document, and voice intake produce reviewable source-backed loop bundles." />
          <PilotReadyItem icon={<PlayCircle className="h-4 w-4" aria-hidden="true" />} title="Run governed loops" detail="Local authority runs durable evidence, validation, effectiveness, approval, recovery, and audit flows." />
          <PilotReadyItem icon={<Download className="h-4 w-4" aria-hidden="true" />} title="Export action plans" detail="Plans retain recommendations, readiness gaps, validation checks, and source provenance." />
          <PilotReadyItem icon={<LockKeyhole className="h-4 w-4" aria-hidden="true" />} title="Respect boundaries" detail="Enterprise mode fails closed until identity, persistence, audit, transport, retention, support, and egress are verified." />
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Loops" value={data.stats.loops} detail="Outcome-owned improvement loops" icon={<GitBranch className="h-5 w-5" aria-hidden="true" />} />
        <StatCard label="Categories" value={data.stats.categories} detail="Enterprise SDLC and AI domains" icon={<Layers3 className="h-5 w-5" aria-hidden="true" />} />
        <StatCard label="Controls" value={data.stats.controls} detail="Validator-backed control catalog" icon={<ShieldCheck className="h-5 w-5" aria-hidden="true" />} />
        <StatCard label="Playbooks" value={data.stats.playbooks} detail="Highest-impact compound use cases" icon={<Workflow className="h-5 w-5" aria-hidden="true" />} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <SectionHeader
            title="Recommended Loop Bundle"
            description="Click a loop to inspect trigger, outcome, controls, golden tasks, metrics, and handoffs."
            action={<HelpPopover helpKey="why" />}
          />
          <div className="grid gap-3">
            {topRecommendations.map((recommendation) => {
              const loop = data.loops.find((item) => item.loop_id === recommendation.loop_id);
              if (!loop) return null;
              return (
                <button key={recommendation.loop_id} type="button" onClick={() => onOpenLoop(loop)} className="interactive-surface p-4 text-left reduced-motion-safe hover:border-brand">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone={recommendation.role === "primary" ? "brand" : recommendation.role === "governance" ? "warning" : "neutral"}>{recommendation.role}</Badge>
                    <Badge>{recommendation.factors.length} factors</Badge>
                    <Badge>{loop.control_profile.applicable_control_ids.length} controls</Badge>
                  </div>
                  <div className="text-base font-semibold text-fg1">{recommendation.name}</div>
                  <div className="mt-1 text-sm text-fg2">{recommendation.factors[0]?.detail ?? loop.output}</div>
                </button>
              );
            })}
          </div>
        </Card>

        <Card>
          <SectionHeader title="Readiness Gaps" description="Gaps remain operationally visible until the use case can move forward." action={<HelpPopover helpKey="readiness" />} />
          <div className="space-y-3">
            {validation.findings.slice(0, 5).map((finding) => (
              <div key={`${finding.label}-${finding.detail}`} className="rounded-panel border border-border2 bg-bg2 p-3">
                <div className="mb-1 flex items-center gap-2">
                  <Badge tone={finding.status === "pass" ? "success" : finding.status === "gap" ? "warning" : "neutral"}>{finding.status}</Badge>
                  <span className="text-sm font-semibold text-fg1">{finding.label}</span>
                </div>
                <div className="text-sm text-fg2">{finding.detail}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <SectionHeader
            title="Top Enterprise Starting Paths"
            description="These playbooks combine multiple loops into practical workflows ranked by effort saving."
            action={<HelpPopover helpKey="why" />}
          />
          <div className="grid gap-3">
            {data.playbooks.map((playbook) => (
              <button
                key={playbook.playbook_id}
                onClick={() => onOpenPlaybook(playbook)}
                className="interactive-surface p-4 text-left reduced-motion-safe hover:border-brand"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="brand">Rank {playbook.impact_rank}</Badge>
                  <Badge>{playbook.loops.length} loops</Badge>
                </div>
                <div className="mt-2 text-base font-semibold text-fg1">{playbook.title}</div>
                <div className="mt-1 text-sm text-fg2">{playbook.effort_saving}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <SectionHeader title="Validation Reality" description="Framework health and activation readiness are deliberately shown separately." action={<HelpPopover helpKey="readiness" />} />
          <div className="space-y-3">
            <RealityRow label="Corpus validator" value={data.validation.corpus_status.toUpperCase()} icon={<ClipboardList className="h-4 w-4" aria-hidden="true" />} />
            <RealityRow label="Line audit blockers" value={String(data.validation.audit.blockers)} icon={<BookOpenCheck className="h-4 w-4" aria-hidden="true" />} />
            <RealityRow label="Known activation gaps" value={String(data.stats.known_activation_gaps)} icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />} />
          </div>
          <div className="mt-4 rounded-panel border border-border2 bg-warningBg p-3 text-sm text-warning">
            DRAFT gaps are not hidden: owners, evidence stores, metric targets, executable probes, and real golden-task fixtures must be bound before ACTIVE enterprise use.
          </div>
        </Card>
      </div>
    </div>
  );
}

function ReleaseAssurancePanel({ initiative, data }: { initiative: InitiativeWorkspace | null; data: LoopOSData }) {
  const profile = initiative?.release_assurance;
  if (!profile) {
    return (
      <section className="surface p-5">
        <SectionHeader title="Release Assurance Workspace" description="Create an SDLC initiative from a release, deployment, or production change to generate release gates." />
        <div className="rounded-panel border border-border2 bg-bg2 p-3 text-sm text-fg2">
          No release assurance profile exists yet. Use release/change wording in intake or create an SDLC initiative from a release workspace.
        </div>
      </section>
    );
  }
  const topGates = profile.gates.slice(0, 6);
  const refs = profile.external_refs;
  return (
    <section className="surface p-5">
      <SectionHeader
        title="Release Assurance Workspace"
        description="Jira and GitHub evidence mapped into release gates, decision records, exceptions, and proof-pack scope."
        action={<Badge tone={profile.operating_mode === "gated_release" ? "success" : "warning"}>{profile.operating_mode}</Badge>}
      />
      <div className="mb-4 grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-panel border border-border2 bg-bg2 p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge tone="brand">{profile.release_name}</Badge>
            <Badge>{profile.gates.length} gates</Badge>
            <Badge>{profile.external_refs.length} evidence refs</Badge>
            <Badge>{profile.exceptions.length} exceptions</Badge>
          </div>
          <div className="grid gap-2">
            {topGates.map((gate) => (
              <div key={gate.gate_id} className="rounded-panel border border-border2 bg-bg1 p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge tone={gateTone(gate.status)}>{gate.status}</Badge>
                  <Badge>{gate.control_ids.length} controls</Badge>
                  <Badge>{gate.required_evidence.length} evidence</Badge>
                </div>
                <div className="text-sm font-semibold text-fg1">{data.loops.find((loop) => loop.loop_id === gate.loop_id)?.name ?? gate.label}</div>
                <div className="mt-1 text-xs text-fg2">{gate.blocker}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-panel border border-border2 bg-bg2 p-3">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-fg1">
            <GitPullRequest className="h-4 w-4 text-brand" aria-hidden="true" />
            Connector posture
          </div>
          <div className="space-y-2">
            {profile.connectors.map((connector) => (
              <div key={connector.connector_id} className="rounded-panel border border-border2 bg-bg1 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={connector.mode === "gated_write" ? "success" : connector.mode === "shadow_read" ? "warning" : "neutral"}>{connector.mode}</Badge>
                  <span className="text-sm font-semibold text-fg1">{connector.label}</span>
                </div>
                <div className="mt-1 text-xs text-fg2">{connector.trust_boundary}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-panel border border-border2 bg-bg2 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1"><FileCheck2 className="h-4 w-4 text-brand" aria-hidden="true" />Evidence graph seeds</div>
          <div className="space-y-2">
            {refs.map((ref) => (
              <div key={ref.ref_id} className="rounded-panel border border-border2 bg-bg1 p-2 text-xs">
                <div className="font-semibold text-fg1">{ref.label}</div>
                <div className="mt-1 text-fg3">{ref.system} / {ref.object_type} / {ref.evidence_hash}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-panel border border-border2 bg-bg2 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1"><ShieldAlert className="h-4 w-4 text-warning" aria-hidden="true" />Risk exceptions</div>
          <div className="space-y-2">
            {profile.exceptions.length ? profile.exceptions.map((exception) => (
              <div key={exception.exception_id} className="rounded-panel border border-warning bg-warningBg p-2 text-xs text-warning">
                <div className="font-semibold">{exception.status} until {new Date(exception.expires_at).toLocaleDateString()}</div>
                <div className="mt-1">{exception.reason}</div>
              </div>
            )) : <div className="text-sm text-fg2">No temporary exceptions recorded.</div>}
          </div>
        </div>
        <div className="rounded-panel border border-border2 bg-bg2 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1"><ShieldCheck className="h-4 w-4 text-success" aria-hidden="true" />Measured ROI basis</div>
          <div className="space-y-2">
            {profile.metric_observations.map((metric) => (
              <div key={metric.metric_id} className="rounded-panel border border-border2 bg-bg1 p-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-fg1">{metric.label}</span>
                  <Badge tone="success">{metric.value} {metric.unit}</Badge>
                </div>
                <div className="mt-1 text-fg2">{metric.basis}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function gateTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "passed") return "success";
  if (status === "blocked") return "danger";
  if (status === "gap" || status === "review_required" || status === "exception_active") return "warning";
  return "neutral";
}

function CommandMetric({ label, value, tone }: { label: string; value: string; tone: "brand" | "success" | "warning" }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="mb-2"><Badge tone={tone}>{label}</Badge></div>
      <div className="text-2xl font-semibold text-fg1">{value}</div>
    </div>
  );
}

function InitiativePanel({
  initiative,
  currentStep,
  completedSteps,
  onCompleteRunStep,
}: {
  initiative: InitiativeWorkspace;
  currentStep: InitiativeWorkspace["execution_records"][number]["step_records"][number] | null;
  completedSteps: number;
  onCompleteRunStep: () => void;
}) {
  const run = initiative.execution_records[0];
  const issueText = buildIssueTicketText(initiative);
  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_0.8fr]">
      <div className="rounded-panel border border-border2 bg-bg2 p-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge tone="brand">{initiative.status}</Badge>
          <Badge>{initiative.loop_bundle_ids.length} loops</Badge>
          <Badge>{completedSteps}/{run?.step_records.length ?? 0} steps</Badge>
        </div>
        <div className="text-sm font-semibold text-fg1">Actionable loop runbook</div>
        <div className="mt-1 text-sm text-fg2">{currentStep ? `${currentStep.label}: ${currentStep.required_evidence}` : "Primary loop checklist is complete."}</div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={onCompleteRunStep} disabled={!currentStep}>
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Complete step
          </Button>
          <Badge tone={run?.validation_result === "Passed" ? "success" : "warning"}>{run?.validation_result ?? "Not Run"}</Badge>
        </div>
      </div>
      <div className="rounded-panel border border-border2 bg-bg2 p-3">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
          <ClipboardList className="h-4 w-4 text-brand" aria-hidden="true" />
          Issue-ticket-ready output
        </div>
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-panel border border-border2 bg-bg1 p-3 text-xs text-fg2">{issueText}</pre>
      </div>
    </div>
  );
}

function HandoffPanel({ initiative, data }: { initiative: InitiativeWorkspace | null; data: LoopOSData }) {
  const handoffs = initiative?.handoffs.slice(0, 5) ?? [];
  return (
    <Card>
      <SectionHeader title="Handoff And Blocker Control" description="Loop-to-loop transitions converted into owned actions." />
      <div className="space-y-3">
        {handoffs.length ? handoffs.map((handoff) => (
          <div key={handoff.handoff_id} className="rounded-panel border border-border2 bg-bg2 p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge tone={handoff.status === "blocked" ? "danger" : handoff.status === "closed" ? "success" : "warning"}>{handoff.status}</Badge>
              <Badge>{handoff.evidence_ref}</Badge>
            </div>
            <div className="text-sm font-semibold text-fg1">{data.loops.find((loop) => loop.loop_id === handoff.from_loop_id)?.name ?? handoff.from_loop_id}</div>
            <div className="mt-1 text-sm text-fg2">{handoff.reason} {"->"} {data.loops.find((loop) => loop.loop_id === handoff.to_loop_id)?.name ?? handoff.to_loop_id}</div>
            <div className="mt-1 text-xs text-fg3">Owner {handoff.owner}; due {new Date(handoff.due_date).toLocaleDateString()}</div>
          </div>
        )) : <div className="rounded-panel border border-border2 bg-bg2 p-3 text-sm text-fg2">Create an SDLC initiative to generate handoff actions from the selected loop bundle.</div>}
      </div>
    </Card>
  );
}

function ProductivityPanel({ initiative }: { initiative: InitiativeWorkspace | null }) {
  const estimate = initiative?.roi_assumptions;
  return (
    <Card>
      <SectionHeader title="SDLC Productivity Scorecard" description="Transparent effort-saving estimate from visible workspace records." />
      <div className="grid gap-3 md:grid-cols-2">
        <WorkspaceSignal label="Meetings avoided" value={String(estimate?.meetings_avoided ?? 0)} />
        <WorkspaceSignal label="Review cycles reduced" value={String(estimate?.review_cycles_reduced ?? 0)} />
        <WorkspaceSignal label="Evidence reused" value={String(estimate?.evidence_items_reused ?? 0)} />
        <WorkspaceSignal label="Hours saved" value={String(estimate?.hours_saved_estimate ?? 0)} />
      </div>
      <div className="mt-3 rounded-panel border border-border2 bg-bg2 p-3 text-sm text-fg2">
        {estimate?.assumptions ?? "Create an initiative to calculate SDLC productivity impact."}
        {estimate ? <div className="mt-2 text-xs text-fg3">{estimate.confidence_basis}</div> : null}
      </div>
    </Card>
  );
}

const CONNECTORS = ["Jira / Azure DevOps", "GitHub / GitLab", "ServiceNow", "Slack / Teams", "Confluence / SharePoint", "GRC", "CI/CD", "Observability", "Identity", "Audit store"];

function IntegrationReadinessPanel() {
  return (
    <section className="surface p-5">
      <SectionHeader title="Enterprise Integration Readiness" description="Connector readiness for production value; v1 exposes export-ready artifacts before live integrations." />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {CONNECTORS.map((connector, index) => (
          <div key={connector} className="rounded-panel border border-border2 bg-bg2 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1">
              <Link2 className="h-4 w-4 text-brand" aria-hidden="true" />
              {connector}
            </div>
            <Badge tone={index < 2 ? "warning" : "neutral"}>{index < 2 ? "export-ready" : "connector placeholder"}</Badge>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-panel border border-border2 bg-warningBg p-3 text-sm text-warning">
        Production authority remains blocked until identity, persistence, audit, retention, secure transport, support, and outbound policy are configured.
      </div>
    </section>
  );
}

function WorkspaceSignal({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-fg3">{label}</div>
      <div className="mt-1 text-lg font-semibold text-fg1">{value}</div>
    </div>
  );
}

function RealityRow({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return (
    <div className="flex items-center justify-between rounded-panel border border-border2 bg-bg2 p-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-fg1">
        <span className="text-brand">{icon}</span>
        {label}
      </div>
      <Badge tone={value === "0" || value === "PASS" ? "success" : "warning"}>{value}</Badge>
    </div>
  );
}

function PilotReadyItem({ title, detail, icon }: { title: string; detail: string; icon: ReactNode }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-fg1">
        <span className="text-success">{icon}</span>
        {title}
      </div>
      <p className="mt-2 text-xs leading-5 text-fg2">{detail}</p>
    </div>
  );
}
