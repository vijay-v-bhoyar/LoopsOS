import { expect, test } from "@playwright/test";

test("fails closed with an incident reference and recovers back to the dashboard", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { crashAuthenticatedView: "workspace" };
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();

  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }

  await expect(page.getByRole("heading", { name: "LoopOS could not complete this screen" })).toBeVisible();
  await expect(page.getByText("No readiness or approval result was recorded. Return to the dashboard and retry the operation.")).toBeVisible();
  await expect(page.getByText(/Incident reference:\s*ui-/)).toBeVisible();
  await expect(page.getByText(/LoopOS test crash|internal detail|componentStack|Error:/)).not.toBeVisible();

  await page.getByRole("button", { name: "Return to dashboard" }).click();
  await expect(page.getByRole("heading", { name: "LoopOS Enterprise Console" })).toBeVisible();
  await expect(page).toHaveURL(/#dashboard$/);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("client-failure-boundary.png"), fullPage: true });
});
