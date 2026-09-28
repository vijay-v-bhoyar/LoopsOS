import { useEffect, useState } from "react";
import { Button } from "../../components/Button";
import type { EnterpriseUser } from "../../types";
import type { ReleaseInitiativeRecord } from "./types";

interface Props {
  record: ReleaseInitiativeRecord;
  user: EnterpriseUser;
  busy: boolean;
  onReview: (record: ReleaseInitiativeRecord, decision: "approve" | "reject", basis: string) => Promise<void>;
}

export function ReleaseReviewPanel({ record, user, busy, onReview }: Props) {
  const context = record.review_context;
  const blockingCheckEventIds = context?.blocking_observed_check_event_ids ?? [];
  const uncorrelatableCheck = context?.blocking_reasons.some((reason) => reason.includes("<invalid-check-name>")) ?? false;
  const identity = JSON.stringify([record.initiative_id, context?.subject_digest, context?.policy_digest, context?.evidence_digest,
    context?.latest_review?.review_id, user.user_id, user.role, user.signed_in_at]);
  const [basis, setBasis] = useState("");
  const [confirmedIdentity, setConfirmedIdentity] = useState("");
  useEffect(() => { setBasis(""); setConfirmedIdentity(""); }, [identity]);
  const hasReviewRole = user.role === "Approver" || user.role === "Executive";
  const separateReviewer = record.created_by !== user.user_id;
  const ready = Boolean(context && hasReviewRole && separateReviewer && basis.trim().length >= 10
    && basis.length <= 4000 && confirmedIdentity === identity && !busy);
  return (
    <section className="mt-3 min-w-0 space-y-3 rounded-panel border border-border2 bg-bg1 p-3 [overflow-wrap:anywhere]" aria-label="Authenticated release review">
      <h3 className="text-sm font-semibold text-fg1">Review release readiness</h3>
      <p className="text-sm text-fg2">Review {record.release_name} against its recorded evidence. This decision does not deploy the release.</p>
      <details className="text-sm text-fg2">
        <summary className="cursor-pointer font-semibold text-fg1">Inspect gates and evidence</summary>
        <div className="mt-2 space-y-3">
          {record.release_assurance.gates.map((gate) => (
            <div key={gate.gate_id} className="break-words rounded-panel border border-border2 p-2">
              <p className="font-semibold text-fg1">{gate.label}: {gate.status}</p>
              <p>{gate.blocker}</p>
              <p>Requirements: {gate.required_evidence.join("; ") || "None recorded"}</p>
              {record.release_assurance.evidence_artifacts.filter((artifact) => artifact.gate_id === gate.gate_id).map((artifact) => (
                <p key={artifact.artifact_id}>{artifact.label} — {artifact.freshness}; source {artifact.source_ref}; observed {artifact.observed_at ?? "not recorded"}</p>
              ))}
            </div>
          ))}
          {record.release_assurance.external_refs.map((ref) => (
            <p key={ref.ref_id} className="break-all">{ref.label} ({ref.system}, {ref.object_type}): {ref.ref_id}; hash {ref.evidence_hash}</p>
          ))}
          <p>Recorded exceptions: {record.release_assurance.exceptions.length}. Open or unsupported exceptions prevent approval.</p>
          {record.release_assurance.exceptions.map((exception) => <p key={exception.exception_id}>{exception.reason}; {exception.status}; expires {exception.expires_at}</p>)}
          {context ? <div className="space-y-1 break-all text-xs">
            <p>Release identity: {context.subject_digest}</p>
            <p>Required policy: {context.policy_digest}</p>
            <p>Evidence identity: {context.evidence_digest}</p>
          </div> : null}
        </div>
      </details>
      {!context ? <p className="text-warning">Refresh from an authority that supports authenticated release review. This historical record cannot be approved here.</p> : null}
      {context?.blocking_reasons.length ? <ul className="list-disc space-y-1 pl-5 text-sm text-danger">{context.blocking_reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul> : null}
      {blockingCheckEventIds.length ? (
        <aside className="space-y-2 rounded-panel border border-danger/40 bg-danger/5 p-3 text-sm text-fg2" role="status" aria-label="Provider check recovery guidance">
          <h4 className="font-semibold text-fg1">Provider check evidence blocks approval</h4>
          <p>{uncorrelatableCheck
            ? "A signed provider event cannot be linked to a check name and the exact release subject. The system keeps it blocking because it may describe a relevant check."
            : "The latest signed provider check state is failed, pending, stale, or invalid for this release."}</p>
          <p>Blocking event IDs: {blockingCheckEventIds.map((eventId) => <code key={eventId} className="mr-2 break-all">{eventId}</code>)}</p>
          <p>Compare each event with GitHub for the recorded repository and commit. Preserve the original event; do not delete it or override the block. {uncorrelatableCheck
            ? "This app has no complete provider-inventory reconciliation path yet, so keep the release at NO_GO and escalate these IDs to the platform/provider owner."
            : "Correct the provider check state and submit current signed evidence."} Readiness must be recalculated, and a separate authorized reviewer must review the new evidence identity before GO.</p>
        </aside>
      ) : null}
      {context?.latest_review ? <p className="text-sm text-fg2">Latest authenticated review: {context.latest_review.decision} by {context.latest_review.reviewer_id} ({context.latest_review.reviewer_role}) at {context.latest_review.reviewed_at}. {context.latest_review.basis}</p> : null}
      {!hasReviewRole ? <p className="text-sm text-fg2">An Approver or Executive must review this record.</p>
        : !separateReviewer ? <p className="text-sm text-warning">A different authorized person must review a record you created.</p>
          : <>
            <label className="block text-sm font-semibold text-fg1">Review rationale
              <textarea className="control mt-1 min-h-20 w-full p-2 text-sm" value={basis} onChange={(event) => setBasis(event.target.value)} minLength={10} maxLength={4000} disabled={busy} />
            </label>
            <label className="flex items-start gap-2 text-sm text-fg2">
              <input type="checkbox" checked={confirmedIdentity === identity} disabled={busy || !context}
                onChange={(event) => setConfirmedIdentity(event.target.checked ? identity : "")} />
              I reviewed this release, its required gates, evidence and exceptions.
            </label>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => onReview(record, "approve", basis.trim())} disabled={!ready || !context?.reviewable}>Approve release readiness</Button>
              <Button variant="ghost" onClick={() => onReview(record, "reject", basis.trim())} disabled={!ready}>Reject release readiness</Button>
            </div>
          </>}
    </section>
  );
}
