import { describe, expect, it } from "vitest";
import { isSavedWorkspaceDocument } from "./workspaceDocument";
import { createWorkspace } from "./workspaceStore";
import {
  createHelpRequestDraft,
  helpRequestMarkdown,
  MAX_HELP_REVALIDATION_ATTEMPTS,
  planHelpRevalidation,
  recordHelpDelivery,
  recordHelpRevalidation,
  recordHelpResponse,
} from "./helpRequestWorkflow";
import type { EnterpriseUser } from "../types";

const requester: EnterpriseUser = { user_id: "user-requester", name: "Requester", email: "requester@example.test", role: "Operator", signed_in_at: "2026-09-22T10:00:00.000Z" };
const planner: EnterpriseUser = { user_id: "user-planner", name: "Planner", email: "planner@example.test", role: "Auditor", signed_in_at: "2026-09-22T10:00:00.000Z" };
const verifier: EnterpriseUser = { user_id: "user-verifier", name: "Verifier", email: "verifier@example.test", role: "Executive", signed_in_at: "2026-09-22T10:00:00.000Z" };
const t0 = "2026-09-22T10:00:00.000Z";
const t1 = "2026-09-22T10:05:00.000Z";
const t2 = "2026-09-22T10:10:00.000Z";
const t3 = "2026-09-22T10:15:00.000Z";
const t4 = "2026-09-22T10:20:00.000Z";
const input = {
  blocked_goal: "Obtain deployment-bound route evidence",
  destination: "Platform operations owner",
  requested_action: "Provide authenticated evidence for the canonical deployment",
  evidence_refs: ["risk:F-06", "run:LOOPSOS-ENTERPRISE-REPAIR"],
  risk_while_waiting: "Release remains NO-GO and deployment is not authorized",
  deadline: "2026-09-23T10:00:00.000Z",
  wake_condition: "The canonical project and deployment IDs plus route evidence are recorded",
};

function draft() {
  return createHelpRequestDraft(input, requester, t0);
}

describe("durable help request workflow", () => {
  it("requires bounded, unique evidence references and a future deadline", () => {
    expect(() => createHelpRequestDraft({ ...input, evidence_refs: [] }, requester, t0)).toThrow("Provide between");
    expect(() => createHelpRequestDraft({ ...input, evidence_refs: ["same", "same"] }, requester, t0)).toThrow("unique");
    expect(() => createHelpRequestDraft({ ...input, deadline: t0 }, requester, t0)).toThrow("future deadline");
  });

  it("caps delivery attempts and preserves the blocked state without sending anything", () => {
    let request = draft();
    request = recordHelpDelivery(request, requester, false, "ticket:attempt-1", "Destination rejected the request", t1);
    request = recordHelpDelivery(request, requester, false, "ticket:attempt-2", "Owner mapping still unresolved", t2);
    request = recordHelpDelivery(request, requester, false, "ticket:attempt-3", "Escalation required", t3);
    expect(request.status).toBe("delivery_failed");
    expect(request.attempts).toBe(3);
    expect(() => recordHelpDelivery(request, requester, true, "ticket:attempt-4", "retry", t4)).toThrow("three-attempt limit");
    expect(helpRequestMarkdown(request)).toContain("LoopOS did not send this request");
  });

  it("records response and independent retest before requesting closure review", () => {
    let request = draft();
    request = recordHelpDelivery(request, requester, true, "ticket:123", "Delivered through the approved channel", t1);
    request = recordHelpResponse(request, requester, "ticket:123#response", "Operations supplied the requested evidence", t2);
    expect(() => planHelpRevalidation(request, requester, "test-plan:1", "Retest route identity", t3)).toThrow("different reviewer");
    request = planHelpRevalidation(request, planner, "test-plan:1", "Retest the same authenticated route on the canonical deployment", t3);
    expect(() => recordHelpRevalidation(request, planner, "pass", "test:receipt:1", "Pass", t4)).toThrow("third person");
    request = recordHelpRevalidation(request, verifier, "pass", "test:receipt:1", "The original blocked probe now passes", "2026-09-22T10:25:00.000Z");
    expect(request.status).toBe("closure_review_requested");
    expect(request.events.map((event) => event.type)).toEqual([
      "draft_created", "delivery_recorded", "response_recorded", "revalidation_planned", "revalidation_result",
    ]);
    expect(helpRequestMarkdown(request)).toContain("not independently verified here");
  });

  it("bounds revalidation cycles and rejects timestamps that move backward", () => {
    let request = draft();
    request = recordHelpDelivery(request, requester, true, "ticket:cycle", "Delivered", t1);
    request = recordHelpResponse(request, requester, "ticket:cycle#response", "Response received", t2);
    let minute = 15;
    for (let attempt = 0; attempt < MAX_HELP_REVALIDATION_ATTEMPTS; attempt += 1) {
      const plannedAt = `2026-09-22T10:${String(minute).padStart(2, "0")}:00.000Z`;
      minute += 1;
      request = planHelpRevalidation(request, planner, `test-plan:${attempt}`, "Retest the blocked criterion", plannedAt);
      const resultAt = `2026-09-22T10:${String(minute).padStart(2, "0")}:00.000Z`;
      minute += 1;
      request = recordHelpRevalidation(request, verifier, "fail", `test-result:${attempt}`, "Still blocked", resultAt);
    }
    expect(() => planHelpRevalidation(request, planner, "test-plan:exhausted", "Retry", "2026-09-22T11:00:00.000Z"))
      .toThrow(`${MAX_HELP_REVALIDATION_ATTEMPTS}-attempt revalidation limit`);
    expect(() => recordHelpDelivery(draft(), requester, true, "ticket:early", "Out of order", "2026-09-22T09:59:00.000Z"))
      .toThrow("cannot move backward");
  });

  it("returns failed or inconclusive revalidation to response review instead of closing", () => {
    let request = draft();
    request = recordHelpDelivery(request, requester, true, "ticket:456", "Delivered", t1);
    request = recordHelpResponse(request, requester, "ticket:456#response", "Response received", t2);
    request = planHelpRevalidation(request, planner, "test-plan:2", "Retest acceptance criteria", t3);
    request = recordHelpRevalidation(request, verifier, "inconclusive", "test:receipt:2", "Provider evidence could not be authenticated", t4);
    expect(request.status).toBe("response_recorded");
  });

  it("migrates old workspace documents and rejects forged or inconsistent help history", () => {
    const workspace = createWorkspace(requester, "Test", {
      title: "Test", description: "Test", environment: "test", aiScope: "test", dataSensitivity: "low",
      businessOutcome: "test", maturity: "discovery", constraints: "test",
    });
    const legacy = { ...workspace } as Record<string, unknown>;
    delete legacy.help_requests;
    expect(isSavedWorkspaceDocument(legacy)).toBe(true);
    expect(isSavedWorkspaceDocument({ ...workspace, help_requests: [draft()] })).toBe(true);
    const invalid = draft();
    invalid.status = "closure_review_requested";
    expect(isSavedWorkspaceDocument({ ...workspace, help_requests: [invalid] })).toBe(false);
    const tampered = draft();
    tampered.events.push({ ...tampered.events[0], event_id: "forged-event", type: "revalidation_result", result: "pass", evidence_ref: "test:forged" });
    expect(isSavedWorkspaceDocument({ ...workspace, help_requests: [tampered] })).toBe(false);

    let completed = recordHelpDelivery(draft(), requester, true, "ticket:identity", "Delivered", t1);
    completed = recordHelpResponse(completed, requester, "ticket:identity#response", "Response received", t2);
    completed = planHelpRevalidation(completed, planner, "test-plan:identity", "Retest", t3);
    completed = recordHelpRevalidation(completed, verifier, "pass", "test-result:identity", "Pass", t4);
    const requesterRetests = {
      ...completed,
      events: completed.events.map((event) => event.type === "revalidation_planned"
        ? { ...event, actor_id: requester.user_id, actor_name: requester.name }
        : event),
    };
    expect(isSavedWorkspaceDocument({ ...workspace, help_requests: [requesterRetests] })).toBe(false);
    const misplacedResult = { ...draft(), events: [{ ...draft().events[0], result: "pass" }] };
    expect(isSavedWorkspaceDocument({ ...workspace, help_requests: [misplacedResult] })).toBe(false);
  });
});