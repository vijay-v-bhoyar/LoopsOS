import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DeploymentPosture } from "../lib/deployment";
import { AuthGate } from "./AuthGate";

const ENTERPRISE_READY: DeploymentPosture = {
  mode: "enterprise",
  status: "enterprise_ready",
  enterpriseReady: true,
  environmentName: "Production",
  apiBaseUrl: "/api",
  authorityAllowedHosts: [],
  allowedEndpointHosts: ["api.example.com"],
  outboundPolicyMode: "allowlist",
  retentionPolicyUrl: "https://policy.example.com/retention",
  supportContact: "loopos-ops@example.com",
  backupRestoreEvidenceUrl: "https://evidence.example.com/restore-test",
  bindings: [],
  blockers: [],
  reviews: [],
};

const ENTERPRISE_RUNTIME_FAILURE: DeploymentPosture = {
  ...ENTERPRISE_READY,
  status: "verification_required",
  enterpriseReady: false,
  bindings: [{
    id: "identity",
    label: "Enterprise identity",
    status: "review",
    detail: "The authority did not verify the current identity session.",
  }],
  reviews: ["identity"],
};

describe("AuthGate", () => {
  it("never offers browser-selected identity or roles in enterprise mode", () => {
    const retry = vi.fn();

    render(
      <AuthGate
        user={null}
        onSignIn={vi.fn()}
        enterpriseSession={{ status: "idle" }}
        onEnterpriseSignIn={retry}
        posture={ENTERPRISE_READY}
      >
        <div>Authenticated application</div>
      </AuthGate>,
    );

    expect(screen.getByRole("heading", { name: "Enterprise Sign-In Required" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Simulation role")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Verify Enterprise Identity" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("fails closed and gives a bounded retry after identity verification errors", () => {
    const retry = vi.fn();

    render(
      <AuthGate
        user={null}
        onSignIn={vi.fn()}
        enterpriseSession={{ status: "error", error: "Identity assertion verification failed." }}
        onEnterpriseSignIn={retry}
        posture={ENTERPRISE_READY}
      >
        <div>Authenticated application</div>
      </AuthGate>,
    );

    expect(screen.queryByText("Authenticated application")).not.toBeInTheDocument();
    expect(screen.getByText("Identity assertion verification failed.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry Enterprise Sign-In" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("keeps transient authority failures recoverable when runtime posture is not ready", () => {
    const retry = vi.fn();

    render(
      <AuthGate
        user={null}
        onSignIn={vi.fn()}
        enterpriseSession={{ status: "error", error: "Authority returned 503.", retryable: true }}
        onEnterpriseSignIn={retry}
        posture={ENTERPRISE_RUNTIME_FAILURE}
      >
        <div>Authenticated application</div>
      </AuthGate>,
    );

    expect(screen.getByRole("heading", { name: "Enterprise Sign-In Failed" })).toBeInTheDocument();
    expect(screen.getByText("Authority returned 503.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry Enterprise Sign-In" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("names the operational bindings that block enterprise activation", () => {
    render(
      <AuthGate
        user={null}
        onSignIn={vi.fn()}
        posture={{
          ...ENTERPRISE_READY,
          status: "activation_blocked",
          enterpriseReady: false,
          bindings: [
            { id: "rate_limit", label: "Request rate limiting", status: "blocked", detail: "Configure request limits." },
            { id: "worker", label: "Worker dispatch", status: "blocked", detail: "Configure external dispatch." },
            { id: "backup_restore", label: "Restore evidence", status: "blocked", detail: "Provide recent restore evidence." },
          ],
        }}
      >
        <div>Authenticated application</div>
      </AuthGate>,
    );

    expect(screen.getByText(/including identity, persistence, audit, rate limiting, worker dispatch, restore evidence, and endpoint policy/)).toBeInTheDocument();
    expect(screen.getByText("Request rate limiting:")).toBeInTheDocument();
    expect(screen.getByText("Worker dispatch:")).toBeInTheDocument();
    expect(screen.getByText("Restore evidence:")).toBeInTheDocument();
  });
});
