import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page) {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
}

test("shows corpus validation separately from enterprise activation readiness on the dashboard", async ({ page }, testInfo) => {
  await signIn(page);

  await expect(page.getByRole("heading", { name: "LoopOS Enterprise Console" })).toBeVisible();
  await expect(page.getByText("Corpus validated")).toBeVisible();
  await expect(page.getByRole("main").getByText("Evaluation only").first()).toBeVisible();
  await expect(page.getByText("1577 activation actions")).toBeVisible();

  await expect(page.getByText("Validation Reality")).toBeVisible();
  await expect(page.getByText("Corpus validator")).toBeVisible();
  await expect(page.getByRole("main").getByText("PASS").first()).toBeVisible();
  await expect(page.getByText("Line audit blockers")).toBeVisible();
  await expect(page.getByRole("main").getByText("0").first()).toBeVisible();
  await expect(page.getByText("Known activation gaps")).toBeVisible();
  await expect(page.getByRole("main").getByText("5").first()).toBeVisible();
  await expect(page.getByText("DRAFT gaps are not hidden: owners, evidence stores, metric targets, executable probes, and real golden-task fixtures must be bound before ACTIVE enterprise use.")).toBeVisible();

  await page.getByRole("button", { name: "Validate Readiness" }).click();
  await expect(page.getByRole("heading", { name: "Validation Studio" })).toBeVisible();
  await expect(page.getByText("Separate corpus validity from this use case's enterprise readiness.")).toBeVisible();
  await expect(page.getByText(/Framework-level DRAFT gaps/)).toBeVisible();

  await page.getByRole("button", { name: "Back to previous screen" }).click();
  await expect(page.getByRole("heading", { name: "LoopOS Enterprise Console" })).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("dashboard-validation-summary.png"), fullPage: true });
});
