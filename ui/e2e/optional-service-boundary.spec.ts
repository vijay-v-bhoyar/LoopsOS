import { expect, test, type Page } from "@playwright/test";

async function openWorkspace(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
}

async function expectDeterministicFallback(page: Page) {
  await expect(page.getByText("deterministic fallback", { exact: true }).first()).toBeVisible();
  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].question_suggestions.length).toBeGreaterThan(0);
  expect(stored.workspaces[0].question_suggestions.every((question: { source: string }) => question.source === "deterministic fallback")).toBe(true);
}

test("rejects insecure remote LLM endpoints and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "http://ai.example.com/infer" };
  });
  await openWorkspace(page);

  await expect(page.getByText(/Provider state: LLM endpoint configured\./)).toBeVisible();
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-insecure-endpoint.png"), fullPage: true });
});

test("rejects non-allowlisted configured hosts and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = {
      llmEndpoint: "https://unknown.example.com/infer",
      allowedEndpointHosts: ["ai.example.com"],
    };
  });
  await openWorkspace(page);

  await expect(page.getByText(/Provider state: LLM endpoint configured\./)).toBeVisible();
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-unapproved-host.png"), fullPage: true });
});

test("rejects redirecting configured endpoints and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-redirect-llm" };
  });
  await page.route("**/api/mock-redirect-llm", async (route) => {
    await route.fulfill({
      status: 302,
      headers: { location: "/api/mock-redirect-target" },
      body: "",
    });
  });

  await openWorkspace(page);

  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-redirect.png"), fullPage: true });
});

test("rejects oversized configured endpoint responses and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-large-llm" };
  });
  await page.route("**/api/mock-large-llm", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "content-length": "1000001" },
      body: "{}",
    });
  });

  await openWorkspace(page);

  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-oversized.png"), fullPage: true });
});

test("aborts slow configured endpoints at the deadline and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-slow-llm", llmTimeoutMs: 20 };
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes("/api/mock-slow-llm")) {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        });
      }
      return originalFetch(input, init);
    };
  });

  await openWorkspace(page);

  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-timeout.png"), fullPage: true });
});
