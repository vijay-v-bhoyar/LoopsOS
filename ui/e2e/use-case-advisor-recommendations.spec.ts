import { expect, test, type Page } from "@playwright/test";

const brief = [
  "# Agentic claims triage",
  "Workflow: Use AI agents with delegated tools and memory to triage incoming insurance claims.",
  "Environment: production",
  "AI scope: Agentic AI",
  "Data sensitivity: regulated",
  "Business outcome: Reduce claim cycle time while preserving review quality.",
  "Maturity: pilot",
  "Constraints: Must preserve audit evidence, access controls, guardrails, privacy, and human approval.",
].join("\n");

async function openAdvisor(page: Page) {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
}

test("renders explainable, source-backed advisor recommendations without hidden confidence claims", async ({ page }, testInfo) => {
  await openAdvisor(page);

  await expect(page.getByRole("heading", { name: "Use Case Advisor" })).toBeVisible();
  await page.getByLabel("Describe the use case").fill(brief);
  await page.getByRole("button", { name: "Analyze and review" }).click();
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  const result = page.getByRole("region", { name: "Loop recommendations" });
  await expect(result).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recommendation Result" })).toBeVisible();
  await expect(page.getByText(/loops matched by metadata, archetypes, playbooks, and risk controls\./)).toBeVisible();
  await expect(page.getByText(/Use-case readiness:/)).toBeVisible();
  await expect(page.getByText(/Corpus validation:/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Primary loops" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Governance loops" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validation loops" })).toBeVisible();
  await expect(page.getByText("Why this loop").first()).toBeVisible();
  await expect(result.getByText(/Matched .* in Typed use case\./).first()).toBeVisible();
  await expect(result.getByText(/claims triage|delegated tools and memory|human approval/i).first()).toBeVisible();

  const sourceId = await page.evaluate(() => {
    const stored = JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}");
    return stored.workspaces?.[0]?.input_sources?.[0]?.source_id ?? "";
  });
  expect(sourceId).toBeTruthy();
  await expect(result.getByText(`Source record: ${sourceId}`).first()).toBeVisible();

  await expect(result).not.toContainText(/confidence/i);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("use-case-advisor-recommendations.png"), fullPage: true });
});
