import { expect, test, type Page } from "@playwright/test";

async function openWorkspace(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByRole("button", { name: "Load Example" }).click();
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
}

test("falls back to deterministic questions and can apply a saved prompt back into the use case", async ({ page }, testInfo) => {
  await page.addInitScript(() => window.localStorage.clear());
  await openWorkspace(page);

  await expect(page.getByRole("heading", { name: "Saved Workspace Console" })).toBeVisible();
  await expect(page.getByText(/Provider state: deterministic fallback active\./)).toBeVisible();
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expect(page.getByText("deterministic fallback", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Governance loops should produce explicit approvals, not meeting-memory.")).toBeVisible();
  await expect(page.getByText("LoopOS separates action applied from effectiveness proven.")).toBeVisible();

  const addButton = page.getByRole("button", { name: "Add To Use Case" }).first();
  const questionText = await addButton.locator("xpath=ancestor::div[contains(@class,'rounded-panel')]").locator("div.font-semibold").textContent();
  await addButton.click();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].question_suggestions.length).toBeGreaterThan(0);
  expect(stored.workspaces[0].question_suggestions.every((question: { source: string }) => question.source === "deterministic fallback")).toBe(true);
  expect(`${stored.workspaces[0].use_case.businessOutcome} ${stored.workspaces[0].use_case.constraints}`).toContain(questionText ?? "");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("llm-questioning-fallback.png"), fullPage: true });
});

test("uses a configured LLM endpoint when present and saves returned questions into the workspace", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-llm-questions" };
  });
  await page.route("**/api/mock-llm-questions", async (route) => {
    const body = route.request().postDataJSON() as { task?: string; recommendations?: unknown[] };
    expect(body.task).toBe("loopos_use_case_questions");
    expect(Array.isArray(body.recommendations)).toBe(true);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        questions: [
          {
            question: "Which evidence store will hold approval and execution records for this pilot?",
            why_it_matters: "The configured provider should still return explicit evidence-bound questions.",
            target_field: "ownerEvidence",
          },
          {
            question: "What rollback trigger will stop the pilot before unsafe drift expands?",
            why_it_matters: "A provider-backed question should still preserve stop conditions.",
            target_field: "constraints",
          },
        ],
      }),
    });
  });

  await openWorkspace(page);

  await expect(page.getByText(/Provider state: LLM endpoint configured\./)).toBeVisible();
  await expect(page.getByLabel("Allow this request to send workspace details to enterprise AI")).toBeChecked({ checked: false });
  await expect(page.getByRole("button", { name: "Generate Questions" })).toBeDisabled();
  await page.getByLabel("Allow this request to send workspace details to enterprise AI").check();
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expect(page.getByText("LLM endpoint").first()).toBeVisible();
  await expect(page.getByText("Which evidence store will hold approval and execution records for this pilot?")).toBeVisible();
  await expect(page.getByText("What rollback trigger will stop the pilot before unsafe drift expands?")).toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].question_suggestions).toHaveLength(2);
  expect(stored.workspaces[0].question_suggestions.every((question: { source: string }) => question.source === "LLM endpoint")).toBe(true);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("llm-questioning-configured.png"), fullPage: true });
});
