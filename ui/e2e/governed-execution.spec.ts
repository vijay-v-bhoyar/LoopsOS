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

async function switchEvaluationRole(page: Page, role: "Approver" | "Executive") {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "LoopOS Evaluation Workspace" })).toBeVisible();
  await page.getByLabel("Simulation role").selectOption(role);
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
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
  await openWorkspace(page, "Operator");
  await page.getByLabel("Loop to execute").selectOption("loop-069-tool-execution-validation-loop");
  await page.getByRole("button", { name: "Run loop" }).click();

  await expect(page.getByText("Payload-bound approval required")).toBeVisible();
  await expect(page.getByText("PLANNED").first()).toBeVisible();
  await switchEvaluationRole(page, "Approver");
  await expect(page.getByText("Payload-bound approval required")).toBeVisible();
  await page.getByRole("button", { name: "Approve exact payload and continue" }).click();
  await expect(page.getByText("EFFECTIVENESS_PROVEN").first()).toBeVisible();
  await expect(page.getByText("APPROVAL_CONSUMED").first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("governed-run-approved.png"), fullPage: true });
});

test("rejects an exact payload and verifies the append-only audit chain", async ({ page }, testInfo) => {
  await openWorkspace(page, "Operator");
  await page.getByLabel("Loop to execute").selectOption("loop-069-tool-execution-validation-loop");
  await page.getByRole("button", { name: "Run loop" }).click();

  await expect(page.getByText("Payload-bound approval required")).toBeVisible();
  await switchEvaluationRole(page, "Executive");
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

test("returns to the sign-in gate when an authority session expires", async ({ page }) => {
  await openWorkspace(page, "Operator");
  for (const pattern of ["**/api/v1/runs?workspace_id=**", "**/v1/runs?workspace_id=**"]) {
    await page.route(pattern, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Session expired." }),
      });
    });
  }

  await page.getByRole("button", { name: "Refresh governed runs" }).click();

  await expect(page.getByRole("heading", { name: "LoopOS Evaluation Workspace" })).toBeVisible();
});

test("keeps an unallowlisted external connector in a failed authority state", async ({ page }, testInfo) => {
  await openWorkspace(page, "Operator");
  await page.getByLabel("Execution target").selectOption("http");
  await page.getByLabel("Action endpoint").fill("https://unknown.example.com/actions");
  await page.getByLabel("Compensation endpoint").fill("https://unknown.example.com/compensate");
  await page.getByLabel("Verification endpoint").fill("https://unknown.example.com/status");
  await page.getByRole("button", { name: "Run loop" }).click();

  await expect(page.getByText("Payload-bound approval required")).toBeVisible();
  await switchEvaluationRole(page, "Approver");
  await page.getByRole("button", { name: "Approve exact payload and continue" }).click();
  await expect(page.getByText("VALIDATION_FAILED").first()).toBeVisible();
  await expect(page.getByText("Connector host unknown.example.com is not allowlisted.").first()).toBeVisible();
  await expect(page.getByText("Action output, not effectiveness-proven")).toBeVisible();
  await expect(page.getByText("Verified output")).not.toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("governed-external-connector-fail-closed.png"), fullPage: true });
});

test("lets a user stop following a stalled audit stream without claiming remote cancellation", async ({ page }) => {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes("/v1/runs/") && url.includes("/events?")) {
        return Promise.resolve(new Response(
          new ReadableStream({
            pull() {
              return new Promise<void>(() => undefined);
            },
          }),
          { status: 200, headers: { "content-type": "text/event-stream" } },
        ));
      }
      return originalFetch(input, init);
    };
  });
  await openWorkspace(page, "Operator");

  await page.getByRole("button", { name: "Run loop" }).click();
  await expect(page.getByRole("button", { name: "Stop following events" })).toBeVisible();
  await page.getByRole("button", { name: "Stop following events" }).click();
  await expect(page.getByRole("button", { name: "Run loop" })).toBeVisible();
  await expect(page.getByText(/Stopping observation does not cancel a remote request/)).toBeVisible();
});
