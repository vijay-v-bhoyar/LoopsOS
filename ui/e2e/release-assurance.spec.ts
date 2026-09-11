import { expect, test } from "@playwright/test";

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
