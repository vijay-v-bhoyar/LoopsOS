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
  allowedEndpointHosts: ["api.example.com"],
  bindings: [],
  blockers: [],
  reviews: [],
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
});
