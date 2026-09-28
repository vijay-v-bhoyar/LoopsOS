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

async function allowOutboundQuestionRequest(page: Page) {
  await page.getByLabel("Allow this request to send workspace details to enterprise AI").check();
}

test("rejects insecure remote LLM endpoints and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "http://ai.example.com/infer" };
  });
  await openWorkspace(page);

  await expect(page.getByText(/Provider state: LLM endpoint configured\./)).toBeVisible();
  await allowOutboundQuestionRequest(page);
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
  await allowOutboundQuestionRequest(page);
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-unapproved-host.png"), fullPage: true });
});

test("rejects query-bearing configured endpoints before sending a request", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-query-llm?token=secret" };
  });
  let unsafeRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("mock-query-llm")) unsafeRequests += 1;
  });
  await page.route("**/api/mock-query-llm?token=secret", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ questions: [{ question: "unsafe response", why_it_matters: "must not be used", target_field: "constraints" }] }),
    });
  });

  await openWorkspace(page);
  await allowOutboundQuestionRequest(page);
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);
  expect(unsafeRequests).toBe(0);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-query-endpoint.png"), fullPage: true });
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

  await allowOutboundQuestionRequest(page);
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

  await allowOutboundQuestionRequest(page);
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-oversized.png"), fullPage: true });
});

test("rejects chunked oversized endpoint responses and falls back deterministically", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-chunked-large-llm" };
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes("/api/mock-chunked-large-llm")) {
        return Promise.resolve(new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(new Uint8Array(1_000_001));
              controller.close();
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ));
      }
      return originalFetch(input, init);
    };
  });

  await openWorkspace(page);

  await allowOutboundQuestionRequest(page);
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-chunked-oversized.png"), fullPage: true });
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

  await allowOutboundQuestionRequest(page);
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-timeout.png"), fullPage: true });
});

test("aborts configured endpoints that stall after returning response headers", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmEndpoint: "/api/mock-stalled-llm", llmTimeoutMs: 20 };
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes("/api/mock-stalled-llm")) {
        return Promise.resolve(new Response(
          new ReadableStream({
            pull() {
              return new Promise<void>(() => undefined);
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ));
      }
      return originalFetch(input, init);
    };
  });

  await openWorkspace(page);

  await allowOutboundQuestionRequest(page);
  await page.getByRole("button", { name: "Generate Questions" }).click();
  await expectDeterministicFallback(page);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("service-boundary-stalled-body.png"), fullPage: true });
});
