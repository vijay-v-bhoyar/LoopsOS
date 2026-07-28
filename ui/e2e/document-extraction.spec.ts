import { expect, test, type Page } from "@playwright/test";

async function openDocumentIntake(page: Page) {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByRole("tab", { name: "Document" }).click();
}

test("extracts local documents within limits, retains truncation warnings, and surfaces actionable failures", async ({ page }, testInfo) => {
  await openDocumentIntake(page);

  const chooser = page.getByLabel("Choose documents");
  await chooser.setInputFiles({
    name: "enterprise-agentic-readiness.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Agentic readiness\n" + "x".repeat(50_200)),
  });

  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  const result = page.getByRole("region", { name: "Loop recommendations" });
  await expect(result).toBeVisible();
  if ((page.viewportSize()?.width ?? 1_440) < 1_280) {
    await page.getByRole("button", { name: "Edit use case" }).click();
  }

  await expect(page.getByRole("button", { name: "Remove enterprise-agentic-readiness.md" })).toBeVisible();
  await expect(page.getByText("Text was limited to 50,000 characters.")).toBeVisible();
  await expect(page.getByText(/document \/ browser text reader \/ 50,000 characters/)).toBeVisible();

  await chooser.setInputFiles({
    name: "spoofed.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("not actually a pdf"),
  });
  await expect(page.locator("p", { hasText: "The file contents do not match the .pdf format." })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).not.toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].input_sources).toHaveLength(1);
  expect(stored.workspaces[0].input_sources[0]).toMatchObject({
    kind: "document",
    label: "enterprise-agentic-readiness.md",
    status: "accepted",
    extraction_method: "browser text reader",
    truncated: true,
  });
  expect(stored.workspaces[0].input_sources[0].warnings).toEqual(
    expect.arrayContaining([expect.objectContaining({ code: "truncated" })]),
  );

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("document-extraction.png"), fullPage: true });
});
