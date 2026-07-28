import { expect, test } from "@playwright/test";

const brief = [
  "# Claims intake pilot",
  "Workflow: Use AI assistants to triage claims with human review before payout.",
  "Environment: production",
  "AI scope: GenAI use case",
  "Data sensitivity: regulated",
  "Business outcome: Reduce intake time while preserving audit evidence.",
  "Maturity: pilot",
  "Constraints: Must preserve human approval, privacy, and access controls.",
].join("\n");

test("calls enterprise field enhancement only on explicit action and never changes saved loop selection directly", async ({ page }, testInfo) => {
  let requestCount = 0;

  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-field-enhancement" };
  });

  await page.route("**/api/mock-field-enhancement", async (route) => {
    requestCount += 1;
    const body = route.request().postDataJSON() as { task?: string; source?: { source_id?: string }; currentUseCase?: { title?: string } };
    expect(body.task).toBe("loopos_use_case_structuring");
    expect(body.source?.source_id).toBeTruthy();
    expect(body.currentUseCase?.title).toBe("Prepare enterprise for agentic AI");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        proposal: {
          title: "Enterprise claims copilot",
          environment: "production",
          aiScope: "Agentic AI",
          businessOutcome: "Cut claims intake time by 25 percent with accountable review.",
          constraints: "Must preserve human approval, privacy, access controls, and audit evidence.",
        },
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByLabel("Describe the use case").fill(brief);
  await page.getByRole("button", { name: "Analyze and review" }).click();

  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  expect(requestCount).toBe(0);
  await expect(page.getByText(/^deterministic:/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Enhance with enterprise AI" })).toBeVisible();

  await page.getByRole("button", { name: "Enhance with enterprise AI" }).click();
  await expect.poll(() => requestCount).toBe(1);
  await expect(page.locator("p", { hasText: "Enterprise AI suggestions are ready for review." })).toBeVisible();
  await expect(page.locator('input[value="Enterprise claims copilot"]')).toBeVisible();
  await expect(page.locator('input[value="Agentic AI"]')).toBeVisible();
  await expect(page.getByText(/^enterprise LLM:/).first()).toBeVisible();

  const beforeApply = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(beforeApply.workspaces[0].selected_loop_ids).toEqual([]);

  await page.getByRole("button", { name: "Apply selected fields" }).click();
  await expect(page.getByRole("region", { name: "Loop recommendations" })).toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].use_case).toMatchObject({
    title: "Enterprise claims copilot",
    aiScope: "Agentic AI",
    businessOutcome: "Cut claims intake time by 25 percent with accountable review.",
  });
  expect(stored.workspaces[0].input_sources[0]).toMatchObject({ label: "Typed use case", status: "accepted" });
  expect(stored.workspaces[0].selected_loop_ids).toEqual([]);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("structured-field-enhancement.png"), fullPage: true });
});
