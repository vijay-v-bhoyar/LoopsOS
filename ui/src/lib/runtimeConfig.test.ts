import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const posture = vi.hoisted(() => ({ mode: "enterprise" }));
vi.mock("./deployment", () => ({ deploymentPosture: posture }));
import { isLocalLlmFixtureEndpoint, llmTimeoutMs } from "./runtimeConfig";
describe("LLM request containment configuration", () => {
  beforeEach(() => { posture.mode = "enterprise"; });
  afterEach(() => { delete window.__LOOPOS_RUNTIME_CONFIG__; vi.unstubAllEnvs(); });
  it("ignores enterprise window timeout overrides and clamps compiled timeout", () => {
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmTimeoutMs: 2_000_000_000 };
    vi.stubEnv("VITE_LOOPOS_LLM_TIMEOUT_MS", "5000");
    expect(llmTimeoutMs()).toBe(5000);
    vi.stubEnv("VITE_LOOPOS_LLM_TIMEOUT_MS", "2000000000");
    expect(llmTimeoutMs()).toBe(30_000);
  });
  it.each(["", "invalid", "Infinity", "0", "-1"])("uses a bounded default for invalid compiled value %s", (value) => {
    vi.stubEnv("VITE_LOOPOS_LLM_TIMEOUT_MS", value);
    expect(llmTimeoutMs()).toBe(15_000);
  });
  it("bounds evaluation overrides while preserving short local timeout tests", () => {
    posture.mode = "evaluation";
    window.__LOOPOS_RUNTIME_CONFIG__ = { llmTimeoutMs: 20 };
    expect(llmTimeoutMs()).toBe(20);
    window.__LOOPOS_RUNTIME_CONFIG__.llmTimeoutMs = 2_000_000_000;
    expect(llmTimeoutMs()).toBe(30_000);
  });
  it("never admits fixture routes in enterprise mode even in development", () => {
    vi.stubEnv("DEV", true);
    expect(isLocalLlmFixtureEndpoint("/api/mock-field-enhancement")).toBe(false);
  });
});
