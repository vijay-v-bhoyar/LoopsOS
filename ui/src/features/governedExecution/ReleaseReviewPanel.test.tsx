import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EnterpriseUser } from "../../types";
import { listReleaseInitiatives, reviewReleaseInitiative } from "./authorityClient";
import { ReleaseReviewPanel } from "./ReleaseReviewPanel";
import type { ReleaseInitiativeRecord } from "./types";

const user: EnterpriseUser = { user_id: "reviewer", name: "Reviewer", email: "reviewer@example.test", role: "Approver", signed_in_at: "2026-09-21T01:00:00Z" };
function record(): ReleaseInitiativeRecord {
  return {
    initiative_id: "release-test", workspace_id: "workspace-test", tenant_id: "tenant-test", title: "Release review", description: "Current release",
    workflow_type: "release", business_outcome: "Verified readiness", maturity: "pilot", risk_tier: "R2", status: "planned", release_name: "Release test",
    loop_bundle_ids: ["loop-036-release-readiness-loop"], source_event_ids: [],
    release_assurance: { profile_id: "profile-test", initiative_id: "release-test", release_name: "Release test", operating_mode: "shadow_release",
      connectors: [], external_refs: [], gates: [], evidence_artifacts: [], decisions: [], exceptions: [], metric_observations: [], proof_pack_scope: [] },
    review_context: { subject_digest: "a".repeat(64), policy_digest: "b".repeat(64), evidence_digest: "c".repeat(64), reviewable: true, blocking_reasons: [], latest_review: null },
    created_by: "producer", created_at: "2026-09-21T01:00:00Z", updated_at: "2026-09-21T01:00:00Z",
  };
}

afterEach(() => vi.restoreAllMocks());

describe("authenticated release review UI", () => {
  it("binds explicit confirmation to current evidence and resets it on change", () => {
    const onReview = vi.fn().mockResolvedValue(undefined);
    const current = record();
    const { rerender } = render(<ReleaseReviewPanel record={current} user={user} busy={false} onReview={onReview} />);
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review rationale"), { target: { value: "Inspected required evidence" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Approve release readiness" }));
    expect(onReview).toHaveBeenCalledWith(current, "approve", "Inspected required evidence");
    const changed = { ...current, review_context: { ...current.review_context!, evidence_digest: "d".repeat(64) } };
    rerender(<ReleaseReviewPanel record={changed} user={user} busy={false} onReview={onReview} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
  });

  it("allows a reasoned rejection while evidence blocks approval", () => {
    const current = record();
    current.review_context!.reviewable = false;
    current.review_context!.blocking_reasons = ["Required evidence expired"];
    const onReview = vi.fn().mockResolvedValue(undefined);
    render(<ReleaseReviewPanel record={current} user={user} busy={false} onReview={onReview} />);
    expect(screen.getByText("Required evidence expired")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Review rationale"), { target: { value: "Evidence expired" } });
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Reject release readiness" }));
    expect(onReview).toHaveBeenCalledWith(current, "reject", "Evidence expired");
  });

  it("shows blocking provider event IDs and the no-bypass recovery path", () => {
    const current = record();
    current.review_context!.reviewable = false;
    current.review_context!.blocking_reasons = ["observed check <invalid-check-name>: current provider state is invalid"];
    current.review_context!.blocking_observed_check_event_ids = ["connector-event-blocking-1"];
    render(<ReleaseReviewPanel record={current} user={user} busy={false} onReview={vi.fn()} />);
    expect(screen.getByRole("status", { name: "Provider check recovery guidance" })).toHaveTextContent("connector-event-blocking-1");
    expect(screen.getByText(/no complete provider-inventory reconciliation path yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
  });

  it("prevents self-review and keeps legacy records unreviewable", () => {
    const current = record();
    const { rerender } = render(<ReleaseReviewPanel record={current} user={{ ...user, user_id: "producer" }} busy={false} onReview={vi.fn()} />);
    expect(screen.getByText("A different authorized person must review a record you created.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve release readiness" })).not.toBeInTheDocument();
    delete current.review_context;
    rerender(<ReleaseReviewPanel record={current} user={user} busy={false} onReview={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
  });

  it("requires a server-valid rationale and renewed acknowledgment after reviewer changes", () => {
    const current = record();
    const onReview = vi.fn();
    const { rerender } = render(<ReleaseReviewPanel record={current} user={user} busy={false} onReview={onReview} />);
    fireEvent.change(screen.getByLabelText("Review rationale"), { target: { value: "too short" } });
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review rationale"), { target: { value: "Evidence reviewed" } });
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeEnabled();
    rerender(<ReleaseReviewPanel record={current} user={{ ...user, user_id: "second-reviewer" }} busy={false} onReview={onReview} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Approve release readiness" })).toBeDisabled();
  });
});

describe("authenticated release review client", () => {
  function reviewed(current: ReleaseInitiativeRecord) {
    return { ...current, review_context: { ...current.review_context!, latest_review: {
      review_id: "review-server", decision: "approve" as const, reviewer_id: "reviewer", reviewer_role: "Approver" as const, reviewed_at: "2026-09-21T02:00:00Z",
      basis: "Evidence reviewed", subject_digest: current.review_context!.subject_digest, policy_digest: current.review_context!.policy_digest,
      evidence_digest: current.review_context!.evidence_digest,
    } } };
  }

  it("sends exact binding and reuses idempotency identity after an uncertain response", async () => {
    const current = record();
    const fetcher = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("lost response"))
      .mockResolvedValueOnce(new Response(JSON.stringify(reviewed(current)), { status: 200 }));
    await expect(reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "reviewer")).rejects.toThrow();
    await reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "reviewer");
    const attempts = fetcher.mock.calls.map(([, init]) => init!);
    expect(attempts[0].body).toEqual(attempts[1].body);
    expect(new Headers(attempts[0].headers).get("idempotency-key")).toEqual(new Headers(attempts[1].headers).get("idempotency-key"));
    expect(JSON.parse(String(attempts[1].body))).toEqual({ decision: "approve", basis: "Evidence reviewed", previous_review_id: null,
      subject_digest: "a".repeat(64), policy_digest: "b".repeat(64), evidence_digest: "c".repeat(64) });
  });

  it("distinguishes informed reapproval from retrying an approval before an intervening review", async () => {
    const current = record();
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(reviewed(current)), { status: 200 }));
    await reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "reviewer");
    current.review_context!.latest_review = { ...reviewed(current).review_context.latest_review, review_id: "intervening-rejection", decision: "reject" };
    await reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "reviewer");
    const [first, second] = fetcher.mock.calls.map(([, init]) => init!);
    expect(new Headers(first.headers).get("idempotency-key")).not.toEqual(new Headers(second.headers).get("idempotency-key"));
    expect(JSON.parse(String(second.body)).previous_review_id).toBe("intervening-rejection");
  });

  it.each(["reviewer_id", "subject_digest", "policy_digest", "evidence_digest"])("rejects a response with substituted %s", async (field) => {
    const current = record();
    const response = reviewed(current);
    Object.assign(response.review_context.latest_review, { [field]: field === "reviewer_id" ? "other" : "d".repeat(64) });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
    await expect(reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "reviewer")).rejects.toThrow("different subject");
  });

  it("rejects malformed context during record loading", async () => {
    const current = record();
    current.review_context!.policy_digest = "short";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([current]), { status: 200 }));
    await expect(listReleaseInitiatives("token", "workspace-test", "tenant-test")).rejects.toThrow("invalid release");
  });

  it("accepts a passed gate with no blocker but rejects a non-text blocker", async () => {
    const current = record();
    current.release_assurance.gates = [{ gate_id: "gate-test", label: "Passed gate", loop_id: "loop-036-release-readiness-loop",
      control_ids: [], required_evidence: [], status: "passed", blocker: "" }];
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify([current]), { status: 200 }));
    await expect(listReleaseInitiatives("token", "workspace-test", "tenant-test")).resolves.toHaveLength(1);
    Object.assign(current.release_assurance.gates[0], { blocker: null });
    fetcher.mockResolvedValueOnce(new Response(JSON.stringify([current]), { status: 200 }));
    await expect(listReleaseInitiatives("token", "workspace-test", "tenant-test")).rejects.toThrow("invalid release");
  });

  it("does not transmit an approval for blocked evidence or a self-review", async () => {
    const current = record();
    const fetcher = vi.spyOn(globalThis, "fetch");
    current.review_context!.reviewable = false;
    await expect(reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "reviewer")).rejects.toThrow("missing or blocked");
    current.review_context!.reviewable = true;
    await expect(reviewReleaseInitiative("token", current, "approve", "Evidence reviewed", "tenant-test", "producer")).rejects.toThrow("separate reviewer");
    expect(fetcher).not.toHaveBeenCalled();
  });
});
