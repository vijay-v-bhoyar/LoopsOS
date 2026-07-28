import { expect, test } from "@playwright/test";

async function openWorkspace(page: import("@playwright/test").Page, role: "Operator" | "Approver" = "Approver") {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByLabel("Simulation role").selectOption(role);
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();

  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
}

test("persists workspace edits, exports portable JSON, and requires confirmation before deletion", async ({ page }, testInfo) => {
  await openWorkspace(page, "Approver");

  await expect(page.getByRole("heading", { name: "Saved Workspace Console" })).toBeVisible();
  await expect(page.getByText(/Saved locally|Save pending|Save failed/)).toBeVisible();

  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expect(page.getByText(/Provider state: deterministic fallback active\./)).toBeVisible();

  await page.getByRole("button", { name: "Save Owner/Evidence Edit" }).click();
  await expect(page.getByText(/GRC \/ evidence store URL/)).toBeVisible();

  await page.getByRole("button", { name: "Save Approval Draft" }).click();
  await expect(page.getByText("Pending")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export data" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.loopos\.json$/);

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].question_suggestions.length).toBeGreaterThan(0);
  expect(stored.workspaces[0].owner_evidence_edits.length).toBeGreaterThan(0);
  expect(stored.workspaces[0].approvals[0].status).toBe("Approved");

  await page.getByRole("button", { name: "Delete workspace" }).click();
  await expect(page.getByRole("dialog", { name: "Delete workspace?" })).toBeVisible();
  await page.getByRole("button", { name: "Delete permanently" }).click();
  await expect(page.getByText("Saved Workspaces")).toBeVisible();

  const afterDelete = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(afterDelete.workspaces).toEqual([]);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("workspace-console.png"), fullPage: true });
});
