import { expect, test, type Page } from "@playwright/test";

async function openWorkspace(page: Page, role: "Operator" | "Approver" | "Executive" | "Auditor") {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByLabel("Simulation role").selectOption(role);
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
}

test("executes a loop through durable evidence, probes, output, and streamed audit events", async ({ page }, testInfo) => {
  await openWorkspace(page, "Operator");
  await page.getByRole("button", { name: "Run loop" }).click();

  await expect(page.getByText("EFFECTIVENESS_PROVEN").first()).toBeVisible();
  await expect(page.getByText("Verified output")).toBeVisible();
  await expect(page.getByText("RUN_CREATED").first()).toBeVisible();
  await expect(page.getByText("RUN_OUTPUT_RECORDED").first()).toBeVisible();
  await expect(page.getByText(/ACTION_APPLIED is never equivalent to EFFECTIVENESS_PROVEN/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("governed-run-complete.png"), fullPage: true });
});

test("holds an R3 loop for exact-payload approval before execution", async ({ page }, testInfo) => {
  await openWorkspace(page, "Approver");
  await page.getByLabel("Loop to execute").selectOption("loop-069-tool-execution-validation-loop");
  await page.getByRole("button", { name: "Run loop" }).click();

  await expect(page.getByText("Payload-bound approval required")).toBeVisible();
  await expect(page.getByText("PLANNED").first()).toBeVisible();
  await page.getByRole("button", { name: "Approve exact payload and continue" }).click();
  await expect(page.getByText("EFFECTIVENESS_PROVEN").first()).toBeVisible();
  await expect(page.getByText("APPROVAL_CONSUMED").first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("governed-run-approved.png"), fullPage: true });
});

test("rejects an exact payload and verifies the append-only audit chain", async ({ page }, testInfo) => {
  await openWorkspace(page, "Executive");
  await page.getByLabel("Loop to execute").selectOption("loop-069-tool-execution-validation-loop");
  await page.getByRole("button", { name: "Run loop" }).click();

  await expect(page.getByText("Payload-bound approval required")).toBeVisible();
  await page.getByLabel("Decision reason").fill("Required control evidence and authority binding are incomplete.");
  await page.getByRole("button", { name: "Reject and block" }).click();
  await expect(page.getByText("BLOCKED").first()).toBeVisible();
  await expect(page.getByText("APPROVAL_REJECTED").first()).toBeVisible();

  await page.getByRole("button", { name: "Verify audit chain" }).click();
  await expect(page.getByText(/Audit chain verified across \d+ tenant events/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("governed-run-rejected-audit-verified.png"), fullPage: true });
});

test("keeps auditor execution controls read-only", async ({ page }) => {
  await openWorkspace(page, "Auditor");
  await expect(page.getByText("Auditor sessions are read-only.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run loop" })).toBeDisabled();
});
