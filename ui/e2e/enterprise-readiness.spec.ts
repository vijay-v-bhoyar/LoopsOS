import { expect, test } from "@playwright/test";

test("exposes the deployment boundary and every navigation destination", async ({ page }, testInfo) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "LoopOS Evaluation Workspace" })).toBeVisible();
  await expect(page.getByLabel("Simulation role")).toHaveValue("Operator");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();

  const isMobile = (page.viewportSize()?.width ?? 1_440) < 1_024;
  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    const navigation = page.getByRole("dialog", { name: "Navigation" });
    await expect(navigation.getByText("Evaluation only")).toBeVisible();
    await expect(navigation.getByRole("button", { name: "Workspaces" })).toBeVisible();
    await expect(navigation.getByRole("button", { name: "Action Plan" })).toBeVisible();
    await navigation.getByRole("button", { name: "Readiness" }).click();
  } else {
    await expect(page.getByText("Evaluation only").first()).toBeVisible();
    await page.getByRole("button", { name: "Readiness" }).first().click();
  }

  await expect(page.getByRole("heading", { name: "Enterprise Activation Readiness" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pilot Activation Gate" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "owners unassigned" })).toBeVisible();
  await expect(page.getByText(/Production activation is not authorized/i)).toBeVisible();
  await expect(page.getByText(/Pilot activation remains separately gated by 5 known corpus activation gaps/i)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("enterprise-readiness.png"), fullPage: true });
});
