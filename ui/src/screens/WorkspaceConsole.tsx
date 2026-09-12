import * as Dialog from "@radix-ui/react-dialog";
import { CheckCircle2, CirclePlus, ClipboardList, Download, FilePenLine, HelpCircle, Save, Trash2, X, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, riskTone } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, SectionHeader } from "../components/Card";
import { HelpPopover, InlineNote } from "../components/Help";
import { getQuestionSuggestions } from "../lib/questionAssistant";
import { recommendLoops } from "../lib/recommendation";
import { llmEndpoint } from "../lib/runtimeConfig";
import { canApprove, createApproval, createOwnerEvidenceEdit } from "../lib/workspaceStore";
import type { WorkspacePersistenceResult } from "../lib/workspaceStore";
import { downloadWorkspaceExport } from "../lib/workspaceExport";
import { GovernedExecutionPanel } from "../features/governedExecution/GovernedExecutionPanel";
import type {
  ApprovalRecord,
  EnterpriseUser,
  LoopOSData,
  OwnerEvidenceEdit,
  QuestionSuggestion,
  SavedWorkspace,
  UseCaseInput,
} from "../types";

export function WorkspaceConsole({
  data,
  user,
  activeWorkspace,
  workspaces,
  onCreateWorkspace,
  onSetActiveWorkspace,
  onMutateWorkspace,
  onUseCaseChange,
  onDeleteWorkspace,
  onSessionExpired,
  onRetryPersistence,
  persistence,
}: {
  data: LoopOSData;
  user: EnterpriseUser;
  activeWorkspace: SavedWorkspace | null;
  workspaces: SavedWorkspace[];
  onCreateWorkspace: (name: string, useCase: UseCaseInput) => void;
  onSetActiveWorkspace: (workspaceId: string) => void;
  onMutateWorkspace: (updater: (workspace: SavedWorkspace) => SavedWorkspace) => void;
  onUseCaseChange: (useCase: UseCaseInput) => void;
  onDeleteWorkspace: (workspaceId: string) => void;
  onSessionExpired?: () => void;
  onRetryPersistence?: () => void;
  persistence: WorkspacePersistenceResult;
}) {
  const workspace = activeWorkspace;
  const [newWorkspaceName, setNewWorkspaceName] = useState("New LoopOS Workspace");

  if (!workspace) {
    return (
      <Card>
        <SectionHeader title="Saved Workspaces" description="Create a workspace to persist use-case analysis, approval drafts, edits, and execution drafts." />
        <div className="flex gap-2">
          <input className="control min-h-10 flex-1 px-3 text-sm" value={newWorkspaceName} onChange={(event) => setNewWorkspaceName(event.target.value)} />
          <Button variant="primary" onClick={() => onCreateWorkspace(newWorkspaceName, data.use_cases[0] ? { title: data.use_cases[0].title, description: data.use_cases[0].summary, environment: "enterprise portfolio", aiScope: "AI readiness", dataSensitivity: "sensitive", businessOutcome: "Prepare an enterprise action path.", maturity: "discovery", constraints: "Created from v2 workspace." } : workspaceSeed())}>
            <CirclePlus className="h-4 w-4" aria-hidden="true" />
            Create
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <SectionHeader
          title="Saved Workspace Console"
          description={persistence.location === "authority"
            ? "Tenant-scoped authoritative workspace for v2 governance work. Use this to persist proposed owners, evidence references, approval drafts, and governed execution records."
            : "Persisted browser-local workspace for evaluation work. Use this to prepare proposed owners, evidence references, approval drafts, and evaluation records before authority activation."}
          action={<HelpPopover helpKey="evidence" />}
        />
        <InlineNote tone={persistence.location === "authority" ? "info" : "warning"}>
          {persistence.location === "authority"
            ? "Authoritative records still require role, evidence, approval, and execution gates before any governed action."
            : "These browser-local drafts cannot authorize tools or change an authority run."}
        </InlineNote>
        <div className="grid gap-3 lg:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Active workspace</span>
            <select className="control min-h-10 w-full px-3 text-sm" value={workspace.workspace_id} onChange={(event) => onSetActiveWorkspace(event.target.value)}>
              {workspaces.map((item) => (
                <option key={item.workspace_id} value={item.workspace_id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Create workspace</span>
            <input className="control min-h-10 w-full px-3 text-sm" value={newWorkspaceName} onChange={(event) => setNewWorkspaceName(event.target.value)} />
          </label>
          <div className="flex items-end">
            <Button variant="primary" onClick={() => onCreateWorkspace(newWorkspaceName, workspace.use_case)}>
              <CirclePlus className="h-4 w-4" aria-hidden="true" />
              Add
            </Button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <WorkspaceMetric label="Signed in as" value={`${user.name} (${user.role})`} />
          <WorkspaceMetric label="Saved loops" value={String(workspace.selected_loop_ids.length)} />
          <WorkspaceMetric label="Approval drafts" value={String(workspace.approvals.length)} />
          <WorkspaceMetric label={persistence.location === "authority" ? "Execution drafts" : "Legacy local executions"} value={String(workspace.execution_records.length)} />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border2 pt-4">
          <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-fg2">
            <Badge tone={persistence.status === "saved" ? "success" : persistence.status === "error" ? "danger" : "neutral"}>
              {persistence.status === "saved"
                ? persistence.location === "authority" ? "Saved to authority" : "Saved locally"
                : persistence.status === "error" ? "Save failed" : "Save pending"}
            </Badge>
            {persistence.message
              ? <span>{persistence.message}</span>
              : <span>{Math.ceil(persistence.bytes / 1024)} KB {persistence.location === "authority" ? "authoritative record" : "browser-local record"}</span>}
          </div>
          <div className="flex flex-wrap gap-2">
            {persistence.location === "authority" && persistence.status === "error" && persistence.code === "authority_unavailable" && onRetryPersistence ? (
              <Button variant="primary" onClick={onRetryPersistence}>
                Retry save
              </Button>
            ) : null}
            <Button onClick={() => downloadWorkspaceExport(workspace)}>
              <Download className="h-4 w-4" aria-hidden="true" />
              Export data
            </Button>
            <DeleteWorkspaceDialog workspace={workspace} onDelete={onDeleteWorkspace} location={persistence.location} />
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <QuestionAssistantCard
          data={data}
          workspace={workspace}
          onMutateWorkspace={onMutateWorkspace}
          onUseCaseChange={onUseCaseChange}
        />
        <OwnerEvidenceEditor data={data} user={user} workspace={workspace} onMutateWorkspace={onMutateWorkspace} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ApprovalPanel data={data} user={user} workspace={workspace} onMutateWorkspace={onMutateWorkspace} />
        <GovernedExecutionPanel data={data} user={user} workspace={workspace} onSessionExpired={onSessionExpired} />
      </div>
    </div>
  );
}

function DeleteWorkspaceDialog({ workspace, onDelete, location }: { workspace: SavedWorkspace; onDelete: (workspaceId: string) => void; location?: WorkspacePersistenceResult["location"] }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button variant="ghost">
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          Delete workspace
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-fg1/50" />
        <Dialog.Content className="surface fixed left-1/2 top-1/2 z-50 w-11/12 max-w-lg -translate-x-1/2 -translate-y-1/2 p-5" aria-describedby="delete-workspace-description">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-lg font-semibold text-fg1">Delete workspace?</Dialog.Title>
              <Dialog.Description id="delete-workspace-description" className="mt-2 text-sm text-fg2">
                 {location === "authority"
                   ? <>This permanently removes {workspace.name} from tenant-scoped authority storage. Export it first when a record must be retained.</>
                   : <>This permanently removes {workspace.name} from this browser. Export it first when a record must be retained.</>}
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" aria-label="Close deletion dialog"><X className="h-4 w-4" aria-hidden="true" /></Button>
            </Dialog.Close>
          </div>
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Dialog.Close asChild><Button>Cancel</Button></Dialog.Close>
            <Dialog.Close asChild>
              <Button variant="danger" onClick={() => onDelete(workspace.workspace_id)}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                Delete permanently
              </Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function workspaceSeed(): UseCaseInput {
  return {
    title: "Enterprise AI Readiness",
    description: "Prepare a governed LoopOS workspace.",
    environment: "enterprise portfolio",
    aiScope: "AI readiness",
    dataSensitivity: "sensitive",
    businessOutcome: "Create a safe enterprise action path.",
    maturity: "discovery",
    constraints: "Local-first v2 workspace.",
  };
}

function WorkspaceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-fg3">{label}</div>
      <div className="mt-1 text-sm font-semibold text-fg1">{value}</div>
    </div>
  );
}

function QuestionAssistantCard({
  data,
  workspace,
  onMutateWorkspace,
  onUseCaseChange,
}: {
  data: LoopOSData;
  workspace: SavedWorkspace;
  onMutateWorkspace: (updater: (workspace: SavedWorkspace) => SavedWorkspace) => void;
  onUseCaseChange: (useCase: UseCaseInput) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [outboundAiConsent, setOutboundAiConsent] = useState(false);
  const recommendations = useMemo(() => recommendLoops(workspace.use_case, data), [workspace.use_case, data]);
  const questionEndpoint = llmEndpoint();
  const outboundAiConsentKey = JSON.stringify({ useCase: workspace.use_case, recommendationIds: recommendations.map((item) => item.loop_id) });

  useEffect(() => {
    setOutboundAiConsent(false);
  }, [outboundAiConsentKey]);

  const ask = async () => {
    if (questionEndpoint && !outboundAiConsent) return;
    setLoading(true);
    const questions = await getQuestionSuggestions(workspace.use_case, recommendations, { consent: outboundAiConsent });
    onMutateWorkspace((current) => ({ ...current, question_suggestions: questions }));
    setLoading(false);
    if (questionEndpoint) setOutboundAiConsent(false);
  };

  const applyQuestion = (question: QuestionSuggestion) => {
    if (question.target_field === "businessOutcome") {
      onUseCaseChange({ ...workspace.use_case, businessOutcome: `${workspace.use_case.businessOutcome} ${question.question}`.trim() });
    }
    if (question.target_field === "constraints") {
      onUseCaseChange({ ...workspace.use_case, constraints: `${workspace.use_case.constraints} ${question.question}`.trim() });
    }
  };

  return (
    <Card>
      <SectionHeader title="LLM-Assisted Questioning" description="Uses an optional LLM endpoint when configured; otherwise falls back to deterministic LoopOS questions." action={<HelpPopover helpKey="why" />} />
      <InlineNote>
        Provider state: {questionEndpoint ? "LLM endpoint configured" : "deterministic fallback active"}. Questions are saved into the active workspace.
      </InlineNote>
      {questionEndpoint ? (
        <label className="mt-3 flex items-start gap-2 text-sm text-fg2">
          <input
            type="checkbox"
            aria-label="Allow this request to send workspace details to enterprise AI"
            checked={outboundAiConsent}
            onChange={(event) => setOutboundAiConsent(event.target.checked)}
          />
          <span>Allow this request to send the current use-case fields, including data sensitivity, and selected recommendations to the configured enterprise AI endpoint.</span>
        </label>
      ) : null}
      <Button variant="primary" className="mt-4" onClick={ask} disabled={loading || Boolean(questionEndpoint && !outboundAiConsent)}>
        <HelpCircle className="h-4 w-4" aria-hidden="true" />
        {loading ? "Generating..." : "Generate Questions"}
      </Button>
      <div className="mt-4 space-y-3">
        {workspace.question_suggestions.map((question) => (
          <div key={question.question_id} className="rounded-panel border border-border2 bg-bg1 p-3">
            <div className="mb-2 flex flex-wrap gap-2">
              <Badge tone="brand">{question.source}</Badge>
              <Badge>{question.target_field}</Badge>
            </div>
            <div className="font-semibold text-fg1">{question.question}</div>
            <div className="mt-1 text-sm text-fg2">{question.why_it_matters}</div>
            {(question.target_field === "businessOutcome" || question.target_field === "constraints") && (
              <Button className="mt-3" onClick={() => applyQuestion(question)}>
                <FilePenLine className="h-4 w-4" aria-hidden="true" />
                Add To Use Case
              </Button>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function OwnerEvidenceEditor({
  data,
  user,
  workspace,
  onMutateWorkspace,
}: {
  data: LoopOSData;
  user: EnterpriseUser;
  workspace: SavedWorkspace;
  onMutateWorkspace: (updater: (workspace: SavedWorkspace) => SavedWorkspace) => void;
}) {
  const [loopId, setLoopId] = useState(workspace.selected_loop_ids[0] ?? data.loops[0]?.loop_id ?? "");
  const [policyOwner, setPolicyOwner] = useState(user.name);
  const [gateOwner, setGateOwner] = useState(user.role === "Approver" ? user.name : "");
  const [riskOwner, setRiskOwner] = useState("");
  const [location, setLocation] = useState("GRC / evidence store URL");
  const loop = data.loops.find((item) => item.loop_id === loopId) ?? data.loops[0];

  const save = () => {
    const edit = createOwnerEvidenceEdit({
      loop_id: loop.loop_id,
      owner_ref: `workspace-owner-${loop.loop_id}`,
      policy_owner: policyOwner,
      gate_owner: gateOwner,
      risk_owner: riskOwner,
      evidence_ref: `workspace-evidence-${loop.loop_id}`,
      authoritative_location: location,
      freshness_policy: "current within gate or observation window",
      retention_policy: "retain through audit and incident reconstruction",
      edited_by: user.name,
    });
    onMutateWorkspace((current) => ({ ...current, owner_evidence_edits: [edit, ...current.owner_evidence_edits] }));
  };

  return (
    <Card>
      <SectionHeader title="Owner And Evidence Draft Editing" description="Workspace overlay edits preserve the immutable source corpus while proposing enterprise owners and evidence references." action={<HelpPopover helpKey="evidence" />} />
      <div className="space-y-3">
        <SelectLoop data={data} value={loopId} onChange={setLoopId} />
        <TextField label="Policy owner" value={policyOwner} onChange={setPolicyOwner} />
        <TextField label="Gate owner" value={gateOwner} onChange={setGateOwner} />
        <TextField label="Risk owner" value={riskOwner} onChange={setRiskOwner} />
        <TextField label="Proposed evidence location" value={location} onChange={setLocation} />
        <Button variant="primary" onClick={save}>
          <Save className="h-4 w-4" aria-hidden="true" />
          Save Owner/Evidence Edit
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        {workspace.owner_evidence_edits.slice(0, 4).map((edit) => (
          <RecordRow key={edit.edit_id} title={data.loops.find((item) => item.loop_id === edit.loop_id)?.name ?? edit.loop_id} detail={`${edit.policy_owner} / ${edit.authoritative_location}`} />
        ))}
      </div>
    </Card>
  );
}

function ApprovalPanel({
  data,
  user,
  workspace,
  onMutateWorkspace,
}: {
  data: LoopOSData;
  user: EnterpriseUser;
  workspace: SavedWorkspace;
  onMutateWorkspace: (updater: (workspace: SavedWorkspace) => SavedWorkspace) => void;
}) {
  const [loopId, setLoopId] = useState(workspace.selected_loop_ids[0] ?? data.loops[0]?.loop_id ?? "");
  const [title, setTitle] = useState("Pilot approval request");
  const [evidence, setEvidence] = useState("Evidence packet pending");
  const loop = data.loops.find((item) => item.loop_id === loopId) ?? data.loops[0];

  const requestApproval = () => {
    const approval = createApproval({
      loop_id: loop.loop_id,
      request_title: title,
      requested_by: user.name,
      approver: user.role === "Approver" || user.role === "Executive" ? user.name : "Named approver required",
      risk_tier: loop.baseline_risk_tier,
      evidence_summary: evidence,
      decision_reason: "",
    });
    onMutateWorkspace((current) => ({ ...current, approvals: [approval, ...current.approvals] }));
  };

  const decide = (approvalId: string, status: ApprovalRecord["status"]) => {
    if (!canApprove(user)) return;
    onMutateWorkspace((current) => ({
      ...current,
      approvals: current.approvals.map((approval) =>
        approval.approval_id === approvalId
          ? { ...approval, status, approver: user.name, decision_reason: status === "Approved" ? "Approved in a non-authoritative workspace draft gate." : "Rejected in a non-authoritative workspace draft gate.", decided_at: new Date().toISOString() }
          : approval,
      ),
    }));
  };

  return (
    <Card>
      <SectionHeader title="Approval Drafts (Non-authoritative)" description="Prepare non-authoritative decision notes. Only a payload-bound decision inside Governed Execution Authority can authorize a run." action={<HelpPopover helpKey="readiness" />} />
      <InlineNote tone="warning">These workspace drafts cannot authorize tools or change an authority run.</InlineNote>
      <div className="space-y-3">
        <SelectLoop data={data} value={loopId} onChange={setLoopId} />
        <TextField label="Approval title" value={title} onChange={setTitle} />
        <TextField label="Evidence summary" value={evidence} onChange={setEvidence} />
        <Button variant="primary" onClick={requestApproval}>
          <ClipboardList className="h-4 w-4" aria-hidden="true" />
          Save Approval Draft
        </Button>
        {!canApprove(user) && <InlineNote tone="warning">Your role can request approvals but cannot approve or reject them in this local workspace.</InlineNote>}
      </div>
      <div className="mt-4 space-y-3">
        {workspace.approvals.map((approval) => (
          <div key={approval.approval_id} className="rounded-panel border border-border2 bg-bg1 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={approval.status === "Approved" ? "success" : approval.status === "Rejected" ? "danger" : "warning"}>{approval.status}</Badge>
              <Badge tone={riskTone(approval.risk_tier)}>{approval.risk_tier}</Badge>
            </div>
            <div className="mt-2 font-semibold text-fg1">{approval.request_title}</div>
            <div className="text-sm text-fg2">{data.loops.find((item) => item.loop_id === approval.loop_id)?.name}</div>
            <div className="mt-2 flex gap-2">
              <Button onClick={() => decide(approval.approval_id, "Approved")} disabled={!canApprove(user) || approval.status !== "Pending"}>
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Approve
              </Button>
              <Button onClick={() => decide(approval.approval_id, "Rejected")} disabled={!canApprove(user) || approval.status !== "Pending"}>
                <XCircle className="h-4 w-4" aria-hidden="true" />
                Reject
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function SelectLoop({ data, value, onChange }: { data: LoopOSData; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-fg1">Loop</span>
      <select className="control min-h-10 w-full px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        {data.loops.map((loop) => (
          <option key={loop.loop_id} value={loop.loop_id}>
            {loop.number}. {loop.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-fg1">{label}</span>
      <input className="control min-h-10 w-full px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function RecordRow({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="font-semibold text-fg1">{title}</div>
      <div className="text-sm text-fg2">{detail}</div>
    </div>
  );
}
