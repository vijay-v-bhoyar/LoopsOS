import type {
  EnterpriseUser,
  HelpRequest,
  HelpRequestEvent,
  HelpRevalidationResult,
} from "../types";

export const MAX_HELP_DELIVERY_ATTEMPTS = 3;
export const MAX_HELP_EVIDENCE_REFS = 30;
export const MAX_HELP_REVALIDATION_ATTEMPTS = 10;

export interface NewHelpRequestInput {
  blocked_goal: string;
  destination: string;
  requested_action: string;
  evidence_refs: string[];
  risk_while_waiting: string;
  deadline: string;
  wake_condition: string;
}

function boundedText(label: string, value: string, maxLength: number): string {
  const normalized = value.trim();
  if (!normalized) throw new Error(`${label} is required.`);
  if (normalized.length > maxLength) throw new Error(`${label} must be ${maxLength} characters or fewer.`);
  return normalized;
}

function requireEvidenceRef(value: string): string {
  return boundedText("Evidence reference", value, 512);
}

function id(): string {
  if (!globalThis.crypto?.randomUUID) throw new Error("Secure random IDs are unavailable in this browser.");
  return globalThis.crypto.randomUUID();
}

function appendEvent(
  request: HelpRequest,
  actor: EnterpriseUser,
  type: HelpRequestEvent["type"],
  note: string,
  at: string,
  evidenceRef?: string,
  result?: HelpRevalidationResult,
): HelpRequest {
  const normalizedEvidenceRef = evidenceRef === undefined ? undefined : requireEvidenceRef(evidenceRef);
  const normalizedNote = boundedText("Event note", note, 2_000);
  const eventTime = Date.parse(at);
  const priorTime = Date.parse(request.updated_at);
  if (!Number.isFinite(eventTime) || !Number.isFinite(priorTime) || eventTime < priorTime) {
    throw new Error("Event time must be valid and cannot move backward.");
  }
  const event: HelpRequestEvent = {
    event_id: id(),
    type,
    actor_id: actor.user_id,
    actor_name: actor.name,
    at,
    note: normalizedNote,
    ...(normalizedEvidenceRef ? { evidence_ref: normalizedEvidenceRef } : {}),
    ...(result ? { result } : {}),
  };
  return { ...request, updated_at: at, events: [...request.events, event] };
}

export function createHelpRequestDraft(
  input: NewHelpRequestInput,
  actor: EnterpriseUser,
  at = new Date().toISOString(),
): HelpRequest {
  const deadline = new Date(input.deadline);
  const now = new Date(at);
  if (!Number.isFinite(deadline.getTime()) || !Number.isFinite(now.getTime()) || deadline.getTime() <= now.getTime()) {
    throw new Error("Choose a valid future deadline.");
  }
  const evidenceRefs = input.evidence_refs.map((reference) => requireEvidenceRef(reference));
  if (evidenceRefs.length === 0 || evidenceRefs.length > MAX_HELP_EVIDENCE_REFS) {
    throw new Error(`Provide between 1 and ${MAX_HELP_EVIDENCE_REFS} evidence references.`);
  }
  if (new Set(evidenceRefs).size !== evidenceRefs.length) throw new Error("Evidence references must be unique.");
  const request: HelpRequest = {
    help_request_id: id(),
    blocked_goal: boundedText("Blocked goal or acceptance criterion", input.blocked_goal, 500),
    destination: boundedText("Requested owner or team", input.destination, 240),
    requested_action: boundedText("Requested action", input.requested_action, 2_000),
    evidence_refs: evidenceRefs,
    risk_while_waiting: boundedText("Risk while waiting", input.risk_while_waiting, 2_000),
    deadline: deadline.toISOString(),
    wake_condition: boundedText("Wake condition", input.wake_condition, 1_000),
    requested_by_id: actor.user_id,
    requested_by: actor.name,
    status: "draft",
    attempts: 0,
    created_at: at,
    updated_at: at,
    events: [],
  };
  return appendEvent(request, actor, "draft_created", "Help request draft created; no message was sent.", at);
}

export function recordHelpDelivery(
  request: HelpRequest,
  actor: EnterpriseUser,
  delivered: boolean,
  evidenceRef: string,
  note: string,
  at = new Date().toISOString(),
): HelpRequest {
  if (request.status !== "draft" && request.status !== "delivery_failed") throw new Error("Delivery can only be recorded for a draft or a failed attempt.");
  if (request.attempts >= MAX_HELP_DELIVERY_ATTEMPTS) throw new Error("The three-attempt limit has been reached; escalate through the product lifecycle owner.");
  const updated = appendEvent(
    request,
    actor,
    delivered ? "delivery_recorded" : "delivery_failed",
    note,
    at,
    evidenceRef,
  );
  return { ...updated, status: delivered ? "waiting" : "delivery_failed", attempts: request.attempts + 1 };
}

export function recordHelpResponse(
  request: HelpRequest,
  actor: EnterpriseUser,
  evidenceRef: string,
  note: string,
  at = new Date().toISOString(),
): HelpRequest {
  if (request.status !== "waiting") throw new Error("A response can only be recorded while waiting for help.");
  const updated = appendEvent(request, actor, "response_recorded", note, at, evidenceRef);
  return { ...updated, status: "response_recorded" };
}

export function planHelpRevalidation(
  request: HelpRequest,
  actor: EnterpriseUser,
  evidenceRef: string,
  note: string,
  at = new Date().toISOString(),
): HelpRequest {
  if (request.status !== "response_recorded") throw new Error("Revalidation can only be planned after a response is recorded.");
  if (request.events.filter((event) => event.type === "revalidation_planned").length >= MAX_HELP_REVALIDATION_ATTEMPTS) {
    throw new Error(`The ${MAX_HELP_REVALIDATION_ATTEMPTS}-attempt revalidation limit has been reached; escalate through the product lifecycle owner.`);
  }
  if (actor.user_id === request.requested_by_id) throw new Error("A different reviewer must plan revalidation.");
  const updated = appendEvent(request, actor, "revalidation_planned", note, at, evidenceRef);
  return { ...updated, status: "revalidation_needed" };
}

export function recordHelpRevalidation(
  request: HelpRequest,
  actor: EnterpriseUser,
  result: HelpRevalidationResult,
  evidenceRef: string,
  note: string,
  at = new Date().toISOString(),
): HelpRequest {
  if (request.status !== "revalidation_needed") throw new Error("Revalidation must be planned before recording its result.");
  const planner = [...request.events].reverse().find((event) => event.type === "revalidation_planned");
  if (!planner) throw new Error("The revalidation plan is missing from the event history.");
  if (actor.user_id === request.requested_by_id || actor.user_id === planner.actor_id) {
    throw new Error("A third person, separate from the requester and revalidation planner, must record the result.");
  }
  const updated = appendEvent(request, actor, "revalidation_result", note, at, evidenceRef, result);
  return { ...updated, status: result === "pass" ? "closure_review_requested" : "response_recorded" };
}

export function helpRequestMarkdown(request: HelpRequest): string {
  return [
    `# Help request ${request.help_request_id}`,
    "",
    "> Draft only. LoopOS did not send this request. Delivery, response, and test entries are user-recorded and are not independently verified here.",
    "",
    `- Status: ${request.status}`,
    `- Requested by: ${request.requested_by}`,
    `- Destination: ${request.destination}`,
    `- Deadline: ${request.deadline}`,
    `- Blocked goal: ${request.blocked_goal}`,
    `- Risk while waiting: ${request.risk_while_waiting}`,
    `- Wake condition: ${request.wake_condition}`,
    "",
    "## Requested action",
    request.requested_action,
    "",
    "## Evidence references (IDs only; do not paste evidence contents or secrets)",
    ...request.evidence_refs.map((reference) => `- ${reference}`),
    "",
  ].join("\n");
}