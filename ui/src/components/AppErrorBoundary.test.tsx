import { createRef } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppErrorBoundary } from "./AppErrorBoundary";

describe("AppErrorBoundary", () => {
  it("fails closed without displaying internal error detail and can recover", () => {
    const boundary = createRef<AppErrorBoundary>();
    window.history.replaceState(null, "", "#advisor");
    render(<AppErrorBoundary ref={boundary}><div>Healthy screen</div></AppErrorBoundary>);
    act(() => boundary.current?.setState(AppErrorBoundary.getDerivedStateFromError()));

    expect(screen.getByRole("heading", { name: "LoopOS could not complete this screen" })).toBeInTheDocument();
    expect(screen.queryByText(/internal detail/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Return to dashboard" }));
    expect(window.location.hash).toBe("#dashboard");
    expect(screen.getByText("Healthy screen")).toBeInTheDocument();
  });
});
