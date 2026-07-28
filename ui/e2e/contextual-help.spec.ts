import { expect, test } from "@playwright/test";

async function openNavDestination(page: import("@playwright/test").Page, name: string) {
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name }).click();
  } else {
    await page.getByRole("button", { name }).first().click();
  }
}

async function expectHelp(page: import("@playwright/test").Page, buttonName: string, heading: string, body: RegExp) {
  await page.getByRole("button", { name: buttonName }).first().click();
  await expect(page.getByText(heading, { exact: true }).last()).toBeVisible();
  await expect(page.getByText(body)).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
}

test("shows contextual help for why, risk, readiness, evidence, and export without hiding critical guidance", async ({ page }, testInfo) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();

  await expectHelp(
    page,
    "Help: Why this loop?",
    "Why this loop?",
    /Recommendations show recorded match factors from loop metadata, playbooks, risk, and controls\./,
  );
  await expectHelp(
    page,
    "Help: Multimodal intake",
    "Multimodal intake",
    /Typed text, extracted document text, and reviewed transcripts can propose use-case fields\./,
  );

  await openNavDestination(page, "Loop Explorer");
  await expect(page.getByRole("heading", { name: "Loop Explorer" })).toBeVisible();
  await expectHelp(
    page,
    "Help: Risk tier",
    "Risk tier",
    /LoopOS risk tiers control proof depth and handoff expectations\./,
  );

  await openNavDestination(page, "Validation Studio");
  await expect(page.getByRole("heading", { name: "Validation Studio" })).toBeVisible();
  await expectHelp(
    page,
    "Help: Readiness",
    "Readiness",
    /Use-case readiness is separate from corpus validation\./,
  );
  await expect(page.getByText(/The framework is valid, but enterprise activation still requires named owners/)).toBeVisible();

  await openNavDestination(page, "Workspaces");
  await expect(page.getByRole("heading", { name: "Saved Workspace Console" })).toBeVisible();
  await expectHelp(
    page,
    "Help: Evidence",
    "Evidence",
    /Evidence gaps mean an enterprise must bind the loop to real systems such as source control, CI, observability, GRC, data catalogs, or model evaluation stores\./,
  );
  await expect(page.getByText(/These browser-local drafts cannot authorize tools or change an authority run\./)).toBeVisible();

  await openNavDestination(page, "Action Plan");
  await expect(page.getByRole("heading", { name: "Enterprise Action Plan" })).toBeVisible();
  await expectHelp(
    page,
    "Help: Export",
    "Export",
    /Exports are read-only action plans\. They do not approve changes, promote loops, or mutate LoopOS governance state\./,
  );

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("contextual-help.png"), fullPage: true });
});
