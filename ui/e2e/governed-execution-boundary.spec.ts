import { expect, test } from "@playwright/test";

test("shows an authority error when refreshing governed runs fails", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();

  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }

  await expect(page.getByRole("button", { name: "Refresh governed runs" })).toBeVisible();
  for (const pattern of ["**/api/v1/runs?workspace_id=**", "**/v1/runs?workspace_id=**"]) {
    await page.route(pattern, async (route) => {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Authority returned 503." }) });
    });
  }
  await page.getByRole("button", { name: "Refresh governed runs" }).click();

  await expect(page.getByText("Authority returned 503.")).toBeVisible();
});

test("reconnects after the initial governed-run read is temporarily unavailable", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  let runReads = 0;
  let allowRecovery = false;
  await page.route("**/api/v1/runs?workspace_id=**", async (route) => {
    runReads += 1;
    if (!allowRecovery) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Authority returned 503." }) });
      return;
    }
    await route.fallback();
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();

  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }

  await expect(page.getByText("Authority unavailable.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reconnect authority" })).toBeVisible();
  allowRecovery = true;
  await page.getByRole("button", { name: "Reconnect authority" }).click();
  await expect(page.getByText("Authority connected")).toBeVisible();
  expect(runReads).toBeGreaterThanOrEqual(2);
});

test("keeps a late governed read from a previous workspace out of the active workspace", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  let firstWorkspaceId = "";
  let releaseFirstRead: (() => void) | undefined;
  const firstRead = new Promise<void>((resolve) => { releaseFirstRead = resolve; });
  const staleRun = {
    run_id: "stale-workspace-run",
    tenant_id: "local-evaluation",
    workspace_id: "stale-workspace",
    loop_id: "loop-069-tool-execution-validation-loop",
    title: "Stale workspace run",
    trigger: "Race regression",
    state: "TRIGGERED",
    runner_status: "queued",
    risk_tier: "R1",
    requires_approval: false,
    payload_hash: "a".repeat(64),
    plan: { action: { tool: "record_action" }, validation_probes: [], effectiveness_probes: [] },
    attempt: 1,
    created_by: "operator-1",
    created_at: "2026-09-04T00:00:00Z",
    updated_at: "2026-09-04T00:00:00Z",
    last_error: null,
    output: null,
  };
  await page.route("**/v1/runs?workspace_id=**", async (route) => {
    const workspaceId = new URL(route.request().url()).searchParams.get("workspace_id") ?? "";
    if (!firstWorkspaceId) firstWorkspaceId = workspaceId;
    if (workspaceId !== firstWorkspaceId) {
      await route.fallback();
      return;
    }
    await firstRead;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([staleRun]) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }

  const activeWorkspace = page.getByLabel("Active workspace");
  await expect(activeWorkspace).toBeVisible();
  await expect.poll(() => firstWorkspaceId).not.toBe("");
  await page.getByLabel("Create workspace").fill("Second live workspace");
  await page.getByRole("button", { name: "Add" }).click();
  await activeWorkspace.selectOption({ label: "Second live workspace" });
  await expect(page.getByText("Authority connected")).toBeVisible();

  releaseFirstRead?.();
  await expect(page.getByText("Stale workspace run")).not.toBeVisible();
});
