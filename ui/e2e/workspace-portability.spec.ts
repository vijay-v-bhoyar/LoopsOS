import { expect, test } from "@playwright/test";

test("exports a bounded workspace handoff artifact", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Simulation role").selectOption("Operator");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByRole("button", { name: "Load Example" }).click();
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
  await expect(page.getByText("Authority connected")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export data" }).click();
  const download = await downloadPromise;

  expect(await download.failure()).toBeNull();
  expect(download.suggestedFilename()).toMatch(/\.loopos\.json$/);
});
