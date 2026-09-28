import { expect, test } from "@playwright/test";
import { createHmac, randomUUID } from "node:crypto";
import type { WorkspaceState } from "../src/types";

const releaseBrief = [
  "# Release v2.4.0 deployment decision",
  "Workflow: Prepare a governed production release with GitHub pull-request evidence, Jira release scope, rollback checks, and post-deploy validation.",
  "Environment: production",
  "AI scope: Release/compliance governance",
  "Data sensitivity: internal",
  "Business outcome: Ship the release with visible gates, explicit exceptions, and a proof-pack-ready evidence trail.",
  "Maturity: pilot",
  "Constraints: Keep deployment approval, secure SDLC evidence, change validation, and rollback readiness visible before launch.",
].join("\n");

async function setupReleaseDraft(page: import("@playwright/test").Page) {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();

  await page.getByLabel("Describe the use case").fill(releaseBrief);
  await page.getByRole("button", { name: "Analyze and review" }).click();
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  await expect(page.getByText("Primary loops")).toBeVisible();
  await page.getByRole("button", { name: "Back to previous screen" }).click();
  await expect(page.getByRole("heading", { name: "LoopOS Enterprise Console" })).toBeVisible();
  await page.getByRole("button", { name: "Create SDLC Initiative" }).click();
  await expect(page.getByText("Evaluation loop runbook")).toBeVisible();
}

async function openWorkspaces(page: import("@playwright/test").Page) {
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
}

test("creates a release assurance workspace from the dashboard and preserves shadow connector posture", async ({ page }, testInfo) => {
  await setupReleaseDraft(page);

  const releasePanel = page.getByRole("heading", { name: "Release Assurance Evaluation Draft" });
  await expect(releasePanel).toBeVisible();
  await expect(page.getByText("shadow_release")).toBeVisible();
  await expect(page.getByText("Connector posture")).toBeVisible();
  await expect(page.getByText("Jira Cloud release evidence")).toBeVisible();
  await expect(page.getByText("GitHub App change evidence")).toBeVisible();
  await expect(page.getByText("Manual attestation fallback")).toBeVisible();
  await expect(page.getByText("Evidence graph seeds")).toBeVisible();
  await expect(page.getByText("Risk exceptions")).toBeVisible();
  await expect(page.getByText("ROI planning basis")).toBeVisible();
  await expect(page.getByText("Estimated hours saved").first()).toBeVisible();
  await expect(page.getByText(/Shadow gate passes|Gate gaps|Review gates|Exceptions active|Release blockers/).first()).toBeVisible();

  await page.getByRole("button", { name: "Complete step" }).click();
  await expect(page.getByText(/1\/14 steps/)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Evaluation Pack" }).click();
  const evaluationPack = await downloadPromise;
  expect(evaluationPack.suggestedFilename()).toMatch(/evaluation-pack\.md$/);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("release-assurance-dashboard.png"), fullPage: true });
});

test("binds a workspace release draft to a tenant authority record and downloads its proof pack", async ({ page }) => {
  await setupReleaseDraft(page);
  await openWorkspaces(page);

  await expect(page.getByRole("heading", { name: "Saved Workspace Console" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Governed Execution Authority" })).toBeVisible();
  await expect(page.getByText("Authority connected")).toBeVisible();

  await page.getByRole("button", { name: "Record release initiative" }).click();
  await expect(page.getByText(/Latest durable record:/)).toBeVisible();
  await expect(page.getByText(/release NO_GO|release REVIEW_REQUIRED/)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Authority proof pack" }).click();
  const proofPack = await downloadPromise;
  expect(proofPack.suggestedFilename()).toMatch(/authority-proof-pack\.md$/);
});

test("reviews exact signed fixture evidence through the real authority and preserves a rejection", async ({ page }, testInfo) => {
  const tenantId = testInfo.project.name === "mobile-chromium" ? "loopos-e2e-mobile" : "loopos-e2e-desktop";
  await page.route("**/api/v1/dev/sessions", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    await route.continue({ postData: JSON.stringify({ ...body, tenant_id: tenantId }) });
  });
  await setupReleaseDraft(page);
  await openWorkspaces(page);
  await expect(page.getByText("Authority connected")).toBeVisible();
  const state = await page.evaluate(() => JSON.parse(localStorage.getItem("loopos.v2.workspace-state") ?? "null")) as WorkspaceState;
  const workspace = state.workspaces.find((item) => item.workspace_id === state.active_workspace_id)!;
  expect(workspace).toBeTruthy();
  const nonce = randomUUID();
  const session = await page.request.post("/api/v1/dev/sessions", { data: {
    tenant_id: tenantId, user_id: `fixture-producer-${nonce}`, name: "Signed fixture producer", role: "Operator",
  } });
  expect(session.ok()).toBe(true);
  const headers = { authorization: `Bearer ${(await session.json()).access_token}` };
  const put = await page.request.put(`/api/v1/workspaces/${workspace.workspace_id}`, { headers: { ...headers, "if-none-match": "*" }, data: { document: workspace } });
  expect([201, 409, 412]).toContain(put.status());
  const policyResponse = await page.request.get("/api/v1/release-policy", { headers });
  expect(policyResponse.ok()).toBe(true);
  const policy = await policyResponse.json();
  const appId = policy.github_release_attestor_app_id;
  const workflowId = (policy.github_release_workflow_ids as number[] | undefined)?.[0];
  expect(Number.isSafeInteger(appId), "The local evaluation authority must pin a synthetic release App ID").toBe(true);
  expect(Number.isSafeInteger(workflowId), "The local evaluation authority must pin a synthetic release workflow ID").toBe(true);
  const secrets = JSON.parse(process.env.LOOPOS_WEBHOOK_SECRETS_JSON ?? "{}");
  const secret = secrets[`${tenantId}:github`];
  expect(typeof secret, "The evaluation E2E launcher must supply a synthetic webhook key").toBe("string");
  const now = new Date().toISOString();
  const gates = [], decisions = [], artifacts = [], refs = [], eventIds = [];
  for (const [index, requirement] of policy.requirements.entries()) {
    const checkSuiteId = 900_000 + index;
    const check = { repository: { full_name: "local-fixture/release" }, check_run: {
      id: `${nonce}-${requirement.loop_id}`, name: requirement.check_name, status: "completed", conclusion: "success",
      head_sha: "d".repeat(40), completed_at: now, html_url: `https://github.example/local-fixture/release/checks/${nonce}-${requirement.loop_id}`,
      app: { id: appId }, check_suite: { id: checkSuiteId },
    } };
    const body = JSON.stringify(check);
    const eventResponse = await page.request.post(`/api/v1/webhooks/${tenantId}/github?workspace_id=${encodeURIComponent(workspace.workspace_id)}`, {
      headers: { "content-type": "application/json", "x-github-event": "check_run", "x-github-delivery": `${nonce}-${requirement.loop_id}`,
        "x-hub-signature-256": `sha256=${createHmac("sha256", secret).update(body).digest("hex")}` }, data: body,
    });
    expect(eventResponse.ok(), await eventResponse.text()).toBe(true);
    const event = await eventResponse.json();
    const id = event.connector_event_id, gateId = `gate-${requirement.loop_id}`;
    const workflow = { repository: { full_name: "local-fixture/release" }, workflow: { id: workflowId, name: "Protected Release Workflow" },
      workflow_run: { id: checkSuiteId + 10_000, workflow_id: workflowId, check_suite_id: checkSuiteId, run_attempt: 1,
        head_sha: "d".repeat(40), status: "completed", conclusion: "success", created_at: now, updated_at: now,
        html_url: `https://github.example/local-fixture/release/actions/runs/${checkSuiteId + 10_000}` } };
    const workflowBody = JSON.stringify(workflow);
    const workflowResponse = await page.request.post(`/api/v1/webhooks/${tenantId}/github?workspace_id=${encodeURIComponent(workspace.workspace_id)}`, {
      headers: { "content-type": "application/json", "x-github-event": "workflow_run", "x-github-delivery": `${nonce}-${requirement.loop_id}-workflow`,
        "x-hub-signature-256": `sha256=${createHmac("sha256", secret).update(workflowBody).digest("hex")}` }, data: workflowBody,
    });
    expect(workflowResponse.ok(), await workflowResponse.text()).toBe(true);
    const workflowEvent = await workflowResponse.json();
    const decision = { decision_id: `claim-${requirement.loop_id}`, gate_id: gateId, status: "passed", decided_by: "fixture-producer-claim",
      decided_at: now, basis: "Synthetic signed check completed successfully.", source_ref_ids: [id] };
    decisions.push(decision);
    gates.push({ gate_id: gateId, label: requirement.check_name, loop_id: requirement.loop_id, control_ids: [requirement.loop_id],
      required_evidence: [requirement.check_name], status: "passed", blocker: "", last_decision: decision });
    refs.push({ ref_id: id, system: "github", object_type: "check", label: requirement.check_name, observed_at: event.observed_at, evidence_hash: event.payload_hash });
    artifacts.push({ artifact_id: `artifact-${requirement.loop_id}`, gate_id: gateId, loop_id: requirement.loop_id, source_ref: id,
      label: requirement.check_name, freshness: "fresh", required: true, observed_at: event.observed_at });
    eventIds.push(id, workflowEvent.connector_event_id);
  }
  const createdResponse = await page.request.post("/api/v1/release-initiatives", { headers: { ...headers, "idempotency-key": `browser-release-${nonce}` }, data: {
    workspace_id: workspace.workspace_id, title: "Signed fixture release", description: "Local end-to-end review boundary test", workflow_type: "release",
    business_outcome: "Verify authenticated readiness review", maturity: "pilot", risk_tier: "R2", status: "planned", release_name: "Signed fixture release",
    loop_bundle_ids: policy.requirements.map((item: { loop_id: string }) => item.loop_id), source_event_ids: eventIds,
    release_assurance: { profile_id: `profile-${nonce}`, initiative_id: `claim-${nonce}`, release_name: "Signed fixture release", operating_mode: "shadow_release",
      connectors: [], external_refs: refs, gates, evidence_artifacts: artifacts, decisions, exceptions: [], metric_observations: [], proof_pack_scope: ["Local synthetic review"],
      policy_id: policy.policy_id, policy_version: policy.version, policy_digest: policy.policy_digest,
      release_subject: { repository: "local-fixture/release", commit_sha: "d".repeat(40) } },
  } });
  expect(createdResponse.status(), await createdResponse.text()).toBe(201);
  const created = await createdResponse.json();
  expect(created.readiness_verdict.verdict).toBe("REVIEW_REQUIRED");
  expect(created.review_context.reviewable).toBe(true);
  await page.getByRole("button", { name: "Refresh governed runs" }).click();
  await expect(page.getByText("An Approver or Executive must review this record.")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByLabel("Simulation role").selectOption("Approver");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  const panel = page.getByRole("region", { name: "Authenticated release review" });
  await expect(panel).toBeVisible();
  await panel.getByText("Inspect gates and evidence", { exact: true }).click();
  await expect(panel.getByText(`Required policy: ${created.review_context.policy_digest}`)).toBeVisible();
  await panel.getByLabel("Review rationale").fill("Reviewed all six signed local fixture checks for the exact commit.");
  await panel.getByRole("checkbox").check();
  const approval = page.waitForResponse((response) => response.url().endsWith(`/release-initiatives/${created.initiative_id}/reviews`) && response.request().method() === "POST");
  await panel.getByRole("button", { name: "Approve release readiness" }).click();
  const approved = await approval;
  expect(approved.status(), await approved.text()).toBe(200);
  expect(approved.request().postDataJSON().subject_digest).toBe(created.review_context.subject_digest);
  await expect(page.getByText("release GO", { exact: true })).toBeVisible();

  // A malformed event with a valid, different repository identity is irrelevant to this release.
  const unrelatedBody = JSON.stringify({ repository: { full_name: "other-org/unrelated-repository" } });
  const unrelatedEvent = await page.request.post(`/api/v1/webhooks/${tenantId}/github?workspace_id=${encodeURIComponent(workspace.workspace_id)}`, {
    headers: { "content-type": "application/json", "x-github-event": "check_run", "x-github-delivery": `${nonce}-malformed-other-repository`,
      "x-hub-signature-256": `sha256=${createHmac("sha256", secret).update(unrelatedBody).digest("hex")}` }, data: unrelatedBody,
  });
  expect(unrelatedEvent.ok(), await unrelatedEvent.text()).toBe(true);
  await page.getByRole("button", { name: "Refresh governed runs" }).click();
  await expect(page.getByText("release GO", { exact: true })).toBeVisible();

  // A signed but incomplete check event must invalidate the prior GO, including in the refreshed UI.
  const malformedBody = JSON.stringify({ repository: { full_name: "local-fixture/release" } });
  const malformedEvent = await page.request.post(`/api/v1/webhooks/${tenantId}/github?workspace_id=${encodeURIComponent(workspace.workspace_id)}`, {
    headers: { "content-type": "application/json", "x-github-event": "check_run", "x-github-delivery": `${nonce}-malformed-unlinked-check`,
      "x-hub-signature-256": `sha256=${createHmac("sha256", secret).update(malformedBody).digest("hex")}` }, data: malformedBody,
  });
  expect(malformedEvent.ok(), await malformedEvent.text()).toBe(true);
  const malformedEventRecord = await malformedEvent.json();
  await page.getByRole("button", { name: "Refresh governed runs" }).click();
  await expect(page.getByText("release NO_GO", { exact: true })).toBeVisible();
  await expect(panel.getByText(/observed check/i)).toBeVisible();
  const recoveryGuidance = panel.getByRole("status", { name: "Provider check recovery guidance" });
  await expect(recoveryGuidance).toContainText(malformedEventRecord.connector_event_id);
  await expect(recoveryGuidance).toContainText("no complete provider-inventory reconciliation path yet");

  await panel.getByLabel("Review rationale").fill("Reject after independent concern; retain veto in the release record.");
  await panel.getByRole("checkbox").check();
  await panel.getByRole("button", { name: "Reject release readiness" }).click();
  await expect(page.getByText("release NO_GO", { exact: true })).toBeVisible();
  await expect(panel.getByText(/Latest authenticated review: reject/)).toBeVisible();
  await testInfo.attach("overflow-diagnostics", { body: JSON.stringify(await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, elements: Array.from(document.querySelectorAll("body *")).map((element) => ({ tag: element.tagName, classes: element.className, width: element.getBoundingClientRect().width, right: element.getBoundingClientRect().right, text: element.textContent?.slice(0, 120) })).filter((element) => element.right > document.documentElement.clientWidth) })), null, 2), contentType: "application/json" });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("release-review-rejection.png"), fullPage: true });
});
