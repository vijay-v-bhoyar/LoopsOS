import { expect, test } from "@playwright/test";

async function openValidation(page: import("@playwright/test").Page) {
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Validation Studio" }).click();
  } else {
    await page.getByRole("button", { name: "Validation Studio" }).first().click();
  }
}

test("keeps validation honest by separating corpus status from incomplete use-case readiness", async ({ page }, testInfo) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();

  await page.getByLabel("Use-case title").fill("AI triage");
  await page.getByLabel("Workflow and problem").fill("Automate reviews.");
  await page.getByLabel("Business outcome").clear();
  await page.getByLabel("Constraints").clear();

  await openValidation(page);

  await expect(page.getByRole("heading", { name: "Validation Studio" })).toBeVisible();
  await expect(page.getByText("Use-case readiness")).toBeVisible();
  await expect(page.getByText("Blocked", { exact: true })).toBeVisible();
  await expect(page.getByText("Corpus validator")).toBeVisible();
  await expect(page.getByText("PASS", { exact: true })).toBeVisible();
  await expect(page.getByText("Activation gaps").first()).toBeVisible();
  await expect(page.getByText(/Framework-level DRAFT gaps still need enterprise binding:/)).toBeVisible();
  await expect(page.getByText("Use-case name", { exact: true })).toBeVisible();
  await expect(page.getByText("Workflow description", { exact: true })).toBeVisible();
  await expect(page.getByText("Business outcome", { exact: true })).toBeVisible();
  await expect(page.getByText("High-risk controls", { exact: true })).toBeVisible();
  await expect(page.getByText("The framework is valid, but enterprise activation still requires named owners")).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("validation-studio.png"), fullPage: true });
});
