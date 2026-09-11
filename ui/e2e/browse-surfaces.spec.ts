import { expect, test } from "@playwright/test";

async function openNavDestination(page: import("@playwright/test").Page, name: string) {
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name }).click();
  } else {
    await page.getByRole("button", { name }).first().click();
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
});

test("browses loops and use cases with explicit empty states and handoff navigation", async ({ page }, testInfo) => {
  await openNavDestination(page, "Loop Explorer");
  await expect(page.getByRole("heading", { name: "Loop Explorer" })).toBeVisible();

  const loopFilter = page.getByLabel("Filter loops");
  await loopFilter.fill("zzzz-no-match");
  await expect(page.getByRole("status")).toContainText("No loops match the current filters");
  await loopFilter.fill("");

  const categoryFilter = page.getByLabel("Filter by category");
  await categoryFilter.selectOption({ index: 1 });
  await page.locator("main button").filter({ hasText: /^\d+/ }).first().click();
  await expect(page.getByRole("heading", { name: "Production-Grade Run Sequence" })).toBeVisible();

  await openNavDestination(page, "Use Case Library");
  await expect(page.getByRole("heading", { name: "Enterprise Use Case Library" })).toBeVisible();
  const globalSearch = page.getByLabel("Search loops and use cases");
  await globalSearch.fill("zzzz-no-match");
  await expect(page.getByRole("status")).toContainText("No use cases match the current search");
  await globalSearch.fill("");
  await page.locator("main button").first().click();
  await expect(page.getByRole("region", { name: "Loop recommendations" })).toBeVisible();
  await expect(page).toHaveURL(/#advisor$/);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("browse-surfaces.png"), fullPage: true });
});
