import { expect, test } from "@playwright/test";

const brief = [
  "# Claims governance pilot",
  "Workflow: Evaluate an enterprise pilot for AI-assisted claims triage with human approval, audit evidence, and governed rollout.",
  "Environment: production",
  "AI scope: Agentic AI",
  "Data sensitivity: regulated",
  "Business outcome: Reduce claims handling time while preserving approval controls and auditability.",
  "Maturity: pilot",
  "Constraints: Must keep approval, evidence, validation, and handoff requirements visible before production expansion.",
].join("\n");

test("builds an enterprise action plan, persists it to the workspace, and exports markdown", async ({ page, context }, testInfo) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();

  await page.getByLabel("Describe the use case").fill(brief);
  await page.getByRole("button", { name: "Analyze and review" }).click();
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  await expect(page.getByText("Primary loops")).toBeVisible();
  if ((page.viewportSize()?.width ?? 1_440) < 1_280) {
    await page.getByRole("button", { name: "Edit use case" }).click();
  }
  await page.getByRole("button", { name: "Send To Action Plan" }).click();

  await expect(page.getByRole("heading", { name: "Enterprise Action Plan" })).toBeVisible();
  await expect(page.getByText("Markdown Preview")).toBeVisible();
  await expect(page.getByText(/LoopOS Enterprise Action Plan:/)).toBeVisible();
  await expect(page.getByText("Trust Note")).toBeVisible();

  await page.getByRole("button", { name: "Copy Markdown" }).click();
  await expect.poll(async () => page.evaluate(() => navigator.clipboard.readText())).toContain("# LoopOS Enterprise Action Plan:");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.md$/);

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].action_plan_markdown).toContain("# LoopOS Enterprise Action Plan:");
  expect(stored.workspaces[0].selected_loop_ids.length).toBeGreaterThan(0);

  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
  await expect(page.getByText("Saved Workspace Console")).toBeVisible();
  await expect(page.getByText("Saved loops")).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("action-plan.png"), fullPage: true });
});
