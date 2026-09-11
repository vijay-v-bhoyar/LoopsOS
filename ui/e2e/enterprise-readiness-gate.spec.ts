import { expect, test } from "@playwright/test";

test.skip(process.env.LOOPOS_E2E_ENTERPRISE_GATE !== "1", "Requires the enterprise-configured Vite preview.");

test("does not issue an enterprise session when authority readiness is unavailable", async ({ page }) => {
  let sessionCalls = 0;
  await page.addInitScript(() => window.localStorage.clear());
  await page.route("**/api/health/ready", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Authority readiness is unavailable." }),
    });
  });
  await page.route("**/api/v1/sessions", async (route) => {
    sessionCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Enterprise Sign-In Failed" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry Enterprise Sign-In" })).toBeVisible();
  await page.waitForTimeout(500);

  expect(sessionCalls).toBe(0);
});

test("blocks enterprise session bootstrap when authority bindings do not match the UI build", async ({ page }) => {
  let sessionCalls = 0;
  await page.addInitScript(() => window.localStorage.clear());
  await page.route("**/api/health/ready", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ready",
        development_auth: false,
        storage_backend: "postgres",
        production_identity: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 0,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: {},
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://wrong.example/retention",
          support_contact: "loopos-operations@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/loopos/restore.json",
        },
        backup_restore_evidence: {
          url: "https://evidence.example.com/loopos/restore.json",
          sha256: "a".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
        },
        operational_evidence: {
          url: "https://evidence.example.com/loopos/operational.json",
          sha256: "b".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
          binding_fingerprint: "c".repeat(64),
        },
      }),
    });
  });
  await page.route("**/api/v1/sessions", async (route) => {
    sessionCalls += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Enterprise Activation Blocked" })).toBeVisible();
  await expect(page.getByText("The compiled UI bindings do not match the authority configuration contract.")).toBeVisible();

  expect(sessionCalls).toBe(0);
});

test("blocks enterprise session bootstrap when authority adds an unbound endpoint host", async ({ page }) => {
  let sessionCalls = 0;
  await page.addInitScript(() => window.localStorage.clear());
  await page.route("**/api/health/ready", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ready",
        development_auth: false,
        storage_backend: "postgres",
        production_identity: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 0,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: {},
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com", "voice.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://policy.example.com/retention",
          support_contact: "loopos-ops@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/restore-test",
        },
        backup_restore_evidence: {
          url: "https://evidence.example.com/restore-test",
          sha256: "a".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
        },
        operational_evidence: {
          url: "https://evidence.example.com/operational.json",
          sha256: "b".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
          binding_fingerprint: "c".repeat(64),
        },
      }),
    });
  });
  await page.route("**/api/v1/sessions", async (route) => {
    sessionCalls += 1;
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "session should not be requested" }) });
  });

  await page.goto("/");
  await expect(page.getByText("The compiled UI bindings do not match the authority configuration contract.")).toBeVisible();
  expect(sessionCalls).toBe(0);
});

test("blocks enterprise session bootstrap when a ready response still has queued jobs", async ({ page }) => {
  let sessionCalls = 0;
  await page.addInitScript(() => window.localStorage.clear());
  await page.route("**/api/health/ready", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ready",
        development_auth: false,
        storage_backend: "postgres",
        production_identity: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 1,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: {},
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://policy.example.com/retention",
          support_contact: "loopos-ops@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/restore-test",
        },
        backup_restore_evidence: {
          url: "https://evidence.example.com/restore-test",
          sha256: "a".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
        },
        operational_evidence: {
          url: "https://evidence.example.com/operational.json",
          sha256: "b".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
          binding_fingerprint: "c".repeat(64),
        },
      }),
    });
  });
  await page.route("**/api/v1/sessions", async (route) => {
    sessionCalls += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Enterprise Verification Required" })).toBeVisible();
  expect(sessionCalls).toBe(0);
});

test("offers a retry when an authoritative workspace save is temporarily unavailable", async ({ page }) => {
  let saveAttempts = 0;
  await page.addInitScript(() => window.localStorage.clear());
  await page.route("**/api/health/ready", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ready",
        development_auth: false,
        storage_backend: "postgres",
        production_identity: true,
        audit_anchor_configured: true,
        audit_anchor_backlog: 0,
        audit_anchor_delivery_verified: true,
        audit_anchor_delivery_fresh: true,
        audit_anchor_last_delivered_at: "2026-07-30T12:00:00+00:00",
        execution_job_backlog: 0,
        execution_worker_dispatch: {
          verified: true,
          source: "external",
          observed_at: "2026-07-30T12:00:00+00:00",
          age_seconds: 5,
          detail: {},
        },
        operational_bindings: {
          retention_verified: true,
          support_verified: true,
          outbound_policy_verified: true,
          backup_restore_verified: true,
          worker_dispatch_verified: true,
        },
        configuration_contract: {
          allowed_http_hosts: ["api.example.com"],
          outbound_policy_mode: "allowlist",
          retention_policy_url: "https://policy.example.com/retention",
          support_contact: "loopos-ops@example.com",
          backup_restore_evidence_url: "https://evidence.example.com/restore-test",
        },
        backup_restore_evidence: {
          url: "https://evidence.example.com/restore-test",
          sha256: "a".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
        },
        operational_evidence: {
          url: "https://evidence.example.com/operational.json",
          sha256: "b".repeat(64),
          verified_at: "2026-07-30T12:00:00+00:00",
          binding_fingerprint: "c".repeat(64),
        },
      }),
    });
  });
  await page.route("**/api/v1/sessions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "enterprise-token",
        token_type: "bearer",
        expires_in: 900,
        actor: {
          tenant_id: "tenant-enterprise",
          user_id: "oidc-user-42",
          name: "Enterprise Operator",
          email: "operator@example.com",
          role: "Operator",
        },
      }),
    });
  });
  await page.route("**/api/v1/workspaces", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/runs**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/release-initiatives**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/connector-events**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/controls/kill-switch", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tenant_id: "tenant-enterprise",
        scope: "tenant",
        active: false,
        activation_id: null,
        reason: null,
        actor_id: null,
        activated_at: null,
        deactivated_at: null,
        deactivated_by: null,
        deactivation_reason: null,
        semantics: "pre_dispatch_block_and_in_flight_interrupt",
      }),
    });
  });
  await page.route("**/api/v1/workspaces/*", async (route) => {
    if (route.request().method() !== "PUT") return route.fallback();
    saveAttempts += 1;
    if (saveAttempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Authority temporarily unavailable." }),
      });
      return;
    }
    const requestBody = route.request().postDataJSON() as { document: Record<string, unknown> };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: requestBody.document.workspace_id,
        tenant_id: "tenant-enterprise",
        revision: 1,
        document: requestBody.document,
        document_hash: "d".repeat(64),
        created_by: "oidc-user-42",
        updated_by: "oidc-user-42",
        created_at: requestBody.document.created_at,
        updated_at: requestBody.document.updated_at,
      }),
    });
  });

  await page.goto("/");
  if ((page.viewportSize()?.width ?? 1_440) < 1_024) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("dialog", { name: "Navigation" }).getByRole("button", { name: "Workspaces" }).click();
  } else {
    await page.getByRole("button", { name: "Workspaces" }).first().click();
  }
  await expect(page.getByRole("heading", { name: "Saved Workspaces" })).toBeVisible();
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("status").getByText("Save failed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry save" })).toBeVisible();

  await page.getByRole("button", { name: "Retry save" }).click();
  await expect(page.getByRole("status").getByText("Saved to authority")).toBeVisible();
  expect(saveAttempts).toBe(2);
});
