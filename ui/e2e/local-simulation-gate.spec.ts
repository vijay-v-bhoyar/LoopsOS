import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, role: "Operator" | "Approver") {
  await page.goto("/");
  await page.getByLabel("Simulation role").selectOption(role);
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
}

async function openWorkspace(page: Page) {
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
}

test("enforces the local simulation gate across sign-in, role authority, and sign-out", async ({ page }, testInfo) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "LoopOS Evaluation Workspace" })).toBeVisible();
  await expect(page.getByText("This is not enterprise sign-in. The selected role is a local simulation role and cannot authorize production actions.")).toBeVisible();
  await expect(page.getByLabel("Simulation role")).toHaveValue("Operator");

  await signIn(page, "Operator");
  await openWorkspace(page);
  await expect(page.getByRole("heading", { name: "Saved Workspace Console" })).toBeVisible();
  await page.getByRole("button", { name: "Save Approval Draft" }).click();
  await expect(page.getByText("Your role can request approvals but cannot approve or reject them in this local workspace.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();
  await expect(page.getByText("Pending")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "LoopOS Evaluation Workspace" })).toBeVisible();
  await expect(page.getByLabel("Simulation role")).toHaveValue("Operator");

  await signIn(page, "Approver");
  await openWorkspace(page);
  await expect(page.getByRole("heading", { name: "Saved Workspace Console" })).toBeVisible();
  await page.getByRole("button", { name: "Save Approval Draft" }).click();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.current_user.role).toBe("Approver");
  expect(stored.workspaces[0].approvals.at(-1)?.status ?? stored.workspaces[0].approvals[0]?.status).toBe("Approved");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("local-simulation-gate.png"), fullPage: true });
});
