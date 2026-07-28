import { expect, test } from "@playwright/test";

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

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
});

test("reviews typed input, preserves focus, and renders a source-backed loop bundle", async ({ page }, testInfo) => {
  await expect(page.getByText("Multimodal intake")).toBeVisible();
  const describeTab = page.getByRole("tab", { name: "Describe" });
  await describeTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Document" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Describe" }).click();

  await page.getByLabel("Describe the use case").fill(brief);
  const analyze = page.getByRole("button", { name: "Analyze and review" });
  await analyze.click();
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(analyze).toBeFocused();

  await analyze.click();
  await page.getByRole("button", { name: "Apply selected fields" }).click();
  const result = page.getByRole("region", { name: "Loop recommendations" });
  await expect(result).toBeInViewport();
  await expect(page.getByText("Primary loops")).toBeVisible();
  await expect(page.getByText(/in Typed use case/).first()).toBeVisible();

  await page.getByRole("button", { name: /primary R\d/ }).first().click();
  await expect(page.getByRole("heading", { name: "Loop Explorer" })).toBeVisible();
  await page.getByRole("button", { name: "Back to previous screen" }).click();
  await expect(result).toBeInViewport();

  const isNarrow = (page.viewportSize()?.width ?? 1_440) < 1_280;
  if (isNarrow) {
    await expect(page.getByRole("button", { name: /Show recommendations/i })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Edit use case" }).click();
  }
  await expect(page.getByRole("button", { name: "Remove Typed use case" })).toBeVisible();
  if (isNarrow) {
    await page.getByRole("button", { name: /Show recommendations/i }).click();
    await expect(result).toBeInViewport();
  }

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].input_sources[0]).toMatchObject({ kind: "text", status: "accepted", label: "Typed use case" });
  expect(JSON.stringify(stored)).not.toContain("blob:");

  const themeToggle = page.getByRole("button", { name: /Switch to Night Ember theme|Switch to Daylight Blue theme/ });
  await themeToggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ reducedMotion: "reduce" });
  const transitionMs = await themeToggle.evaluate((element) => {
    const duration = getComputedStyle(element).transitionDuration;
    const value = Number.parseFloat(duration);
    return duration.endsWith("ms") ? value : value * 1_000;
  });
  expect(transitionMs).toBeLessThanOrEqual(0.01);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("multimodal-advisor.png"), fullPage: true });
});

test("handles a long local document name without layout overflow", async ({ page }, testInfo) => {
  const longName = "enterprise-agentic-ai-operating-model-and-governance-readiness-assessment-2026.md";
  await page.getByRole("tab", { name: "Document" }).click();
  await page.getByLabel("Choose documents").setInputFiles({
    name: longName,
    mimeType: "text/markdown",
    buffer: Buffer.from(brief),
  });
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await page.getByRole("button", { name: "Apply selected fields" }).click();
  if ((page.viewportSize()?.width ?? 1_440) < 1_280) {
    await page.getByRole("button", { name: "Edit use case" }).click();
  }
  await expect(page.getByRole("button", { name: `Remove ${longName}` })).toBeVisible();

  await page.getByRole("tab", { name: "Voice" }).click();
  await expect(page.getByText(/Voice input is unavailable|Start dictation|Record for enterprise transcription/)).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("long-source-name.png"), fullPage: true });
});
