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

test("creates a release assurance workspace from the dashboard and preserves shadow connector posture", async ({ page }, testInfo) => {
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
  await expect(page.getByText("Actionable loop runbook")).toBeVisible();

  const releasePanel = page.getByRole("heading", { name: "Release Assurance Workspace" });
  await expect(releasePanel).toBeVisible();
  await expect(page.getByText("shadow_release")).toBeVisible();
  await expect(page.getByText("Connector posture")).toBeVisible();
  await expect(page.getByText("Jira Cloud release evidence")).toBeVisible();
  await expect(page.getByText("GitHub App change evidence")).toBeVisible();
  await expect(page.getByText("Manual attestation fallback")).toBeVisible();
  await expect(page.getByText("Evidence graph seeds")).toBeVisible();
  await expect(page.getByText("Risk exceptions")).toBeVisible();
  await expect(page.getByText("Measured ROI basis")).toBeVisible();
  await expect(page.getByText(/Release gates passed|Gate gaps|Review gates|Exceptions active|Release blockers/).first()).toBeVisible();

  await page.getByRole("button", { name: "Complete step" }).click();
  await expect(page.getByText(/1\/14 steps/)).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("release-assurance-dashboard.png"), fullPage: true });
});
