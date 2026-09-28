import { useState } from "react";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card, SectionHeader } from "./Card";
import { InlineNote } from "./Help";
import { downloadMarkdown } from "../lib/workspaceExport";
import {
  createHelpRequestDraft,
  helpRequestMarkdown,
  planHelpRevalidation,
  recordHelpDelivery,
  recordHelpRevalidation,
  recordHelpResponse,
} from "../lib/helpRequestWorkflow";
import type { EnterpriseUser, HelpRequest, HelpRevalidationResult, SavedWorkspace } from "../types";

interface HelpRequestLedgerProps {
  workspace: SavedWorkspace;
  user: EnterpriseUser;
  onMutateWorkspace: (updater: (workspace: SavedWorkspace) => SavedWorkspace) => void;
}

const EMPTY_FORM = {
  blocked_goal: "",
  destination: "",
  requested_action: "",
  evidence_refs: "",
  risk_while_waiting: "",
  deadline: "",
  wake_condition: "",
};

export function HelpRequestLedger({ workspace, user, onMutateWorkspace }: HelpRequestLedgerProps) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const requests = workspace.help_requests ?? [];

  const saveDraft = () => {
    try {
      const request = createHelpRequestDraft({
        ...form,
        deadline: new Date(form.deadline).toISOString(),
        evidence_refs: form.evidence_refs.split(/[\n,]/).map((reference) => reference.trim()).filter(Boolean),
      }, user);
      onMutateWorkspace((current) => ({ ...current, help_requests: [request, ...(current.help_requests ?? [])] }));
      setForm(EMPTY_FORM);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The help request could not be saved.");
    }
  };

  const update = (requestId: string, transform: (request: HelpRequest) => HelpRequest) => {
    onMutateWorkspace((current) => ({
      ...current,
      help_requests: (current.help_requests ?? []).map((request) => request.help_request_id === requestId ? transform(request) : request),
    }));
  };

  return (
    <Card>
      <SectionHeader title="Help And Recovery Requests" description="Create a durable help draft, record owner responses, then hand results to separate revalidation. This ledger cannot authorize work or close a release gate." />
      <InlineNote tone="warning">Nothing is sent automatically. Download the draft and deliver it through an approved help channel yourself. Record references only; do not paste secrets, customer data, or evidence contents. Delivery and response entries are user assertions, not independently verified receipts.</InlineNote>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <TextArea label="Blocked goal or acceptance criterion" value={form.blocked_goal} onChange={(value) => setForm({ ...form, blocked_goal: value })} />
        <TextField label="Requested owner or team" value={form.destination} onChange={(value) => setForm({ ...form, destination: value })} />
        <TextArea label="Specific action needed" value={form.requested_action} onChange={(value) => setForm({ ...form, requested_action: value })} />
        <TextArea label="Risk while waiting" value={form.risk_while_waiting} onChange={(value) => setForm({ ...form, risk_while_waiting: value })} />
        <TextArea label="Evidence references (one per line or comma-separated)" value={form.evidence_refs} onChange={(value) => setForm({ ...form, evidence_refs: value })} />
        <TextArea label="Wake condition: what exact response unblocks the next action?" value={form.wake_condition} onChange={(value) => setForm({ ...form, wake_condition: value })} />
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-fg1">Response deadline</span>
          <input className="control min-h-10 w-full px-3 text-sm" type="datetime-local" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} />
        </label>
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      <div className="mt-3"><Button variant="primary" onClick={saveDraft}>Save help request draft</Button></div>
      <div className="mt-5 space-y-4">
        {requests.length === 0 ? <p className="text-sm text-fg2">No help requests are recorded for this workspace.</p> : requests.map((request) => (
          <HelpRequestCard key={request.help_request_id} request={request} user={user} onUpdate={(updated) => update(request.help_request_id, () => updated)} />
        ))}
      </div>
    </Card>
  );
}

function HelpRequestCard({ request, user, onUpdate }: { request: HelpRequest; user: EnterpriseUser; onUpdate: (request: HelpRequest) => void }) {
  const [error, setError] = useState("");
  const [evidenceRef, setEvidenceRef] = useState("");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<HelpRevalidationResult>("inconclusive");
  const overdue = Date.parse(request.deadline) < Date.now() && request.status !== "closure_review_requested";

  const apply = (transition: (current: HelpRequest) => HelpRequest) => {
    try {
      onUpdate(transition(request));
      setError("");
      setEvidenceRef("");
      setNote("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The help request could not be updated.");
    }
  };

  return (
    <div className="rounded-panel border border-border2 bg-bg1 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={request.status === "closure_review_requested" ? "success" : overdue ? "danger" : "warning"}>{request.status.replace(/_/g, " ")}</Badge>
        <span className="text-xs text-fg3">{request.attempts}/3 delivery attempts · due {new Date(request.deadline).toLocaleString()}</span>
      </div>
      {overdue && <p role="status" className="mt-2 text-sm font-semibold text-danger">Overdue. This app has no scheduler; the lifecycle owner must follow up manually.</p>}
      <p className="mt-2 font-semibold text-fg1">{request.blocked_goal}</p>
      <p className="mt-1 text-sm text-fg2">Owner: {request.destination}. Waiting risk: {request.risk_while_waiting}</p>
      <p className="mt-1 text-sm text-fg2">Wake condition: {request.wake_condition}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => downloadMarkdown(`help-request-${request.help_request_id}.md`, helpRequestMarkdown(request))}>Download request</Button>
      </div>
      {(request.status === "draft" || request.status === "delivery_failed") && (
        <div className="mt-4 space-y-2 border-t border-border2 pt-3">
          <p className="text-sm font-semibold text-fg1">After you attempt delivery, record the channel reference here.</p>
          <TextField label="Delivery reference" value={evidenceRef} onChange={setEvidenceRef} />
          <TextArea label="Delivery note" value={note} onChange={setNote} />
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={request.attempts >= 3} onClick={() => apply((current) => recordHelpDelivery(current, user, true, evidenceRef, note))}>Record delivery</Button>
            <Button disabled={request.attempts >= 3} onClick={() => apply((current) => recordHelpDelivery(current, user, false, evidenceRef, note))}>Record failed attempt</Button>
          </div>
          {request.attempts >= 3 && <p className="text-sm text-danger">Attempt ceiling reached. Escalate to the lifecycle owner; this UI will not retry.</p>}
        </div>
      )}
      {request.status === "waiting" && (
        <div className="mt-4 space-y-2 border-t border-border2 pt-3">
          <TextField label="Response evidence reference" value={evidenceRef} onChange={setEvidenceRef} />
          <TextArea label="Response summary (no sensitive content)" value={note} onChange={setNote} />
          <Button variant="primary" onClick={() => apply((current) => recordHelpResponse(current, user, evidenceRef, note))}>Record response received</Button>
        </div>
      )}
      {request.status === "response_recorded" && (
        <div className="mt-4 space-y-2 border-t border-border2 pt-3">
          <p className="text-sm text-fg2">A different person must plan a concrete retest against the blocked criterion.</p>
          <TextField label="Revalidation plan evidence reference" value={evidenceRef} onChange={setEvidenceRef} />
          <TextArea label="Revalidation plan and owner" value={note} onChange={setNote} />
          <Button variant="primary" onClick={() => apply((current) => planHelpRevalidation(current, user, evidenceRef, note))}>Plan independent revalidation</Button>
        </div>
      )}
      {request.status === "revalidation_needed" && (
        <div className="mt-4 space-y-2 border-t border-border2 pt-3">
          <p className="text-sm text-fg2">A third person, different from the requester and planner, must record the test result.</p>
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Revalidation outcome</span>
            <select className="control min-h-10 w-full px-3 text-sm" value={result} onChange={(event) => setResult(event.target.value as HelpRevalidationResult)}>
              <option value="pass">Pass</option><option value="fail">Fail</option><option value="inconclusive">Inconclusive</option>
            </select>
          </label>
          <TextField label="Retest evidence reference" value={evidenceRef} onChange={setEvidenceRef} />
          <TextArea label="What was tested and what happened?" value={note} onChange={setNote} />
          <Button variant="primary" onClick={() => apply((current) => recordHelpRevalidation(current, user, result, evidenceRef, note))}>Record revalidation result</Button>
        </div>
      )}
      {request.status === "closure_review_requested" && (
        <InlineNote tone="warning">A revalidation pass is recorded. The request remains open until an independently authenticated assurance authority verifies and records closure. This workspace UI cannot close the gate.</InlineNote>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      <details className="mt-3 border-t border-border2 pt-3">
        <summary className="cursor-pointer text-sm font-semibold text-fg2">History ({request.events.length})</summary>
        <ol className="mt-2 space-y-2">
          {[...request.events].reverse().map((event) => (
            <li key={event.event_id} className="text-xs text-fg2">
              <span className="font-semibold">{event.type.replace(/_/g, " ")}</span> · {event.actor_name} · {new Date(event.at).toLocaleString()}
              {event.result ? ` · ${event.result}` : ""}{event.evidence_ref ? ` · ref: ${event.evidence_ref}` : ""}<br />{event.note}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block"><span className="mb-1 block text-sm font-semibold text-fg1">{label}</span><input className="control min-h-10 w-full px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block"><span className="mb-1 block text-sm font-semibold text-fg1">{label}</span><textarea className="control min-h-20 w-full px-3 py-2 text-sm" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}