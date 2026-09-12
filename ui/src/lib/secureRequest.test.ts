import { describe, expect, it, vi } from "vitest";
import { assertAllowedEndpoint, secureJsonRequest } from "./secureRequest";

describe("secureRequest", () => {
  it("rejects insecure remote and non-allowlisted endpoints", () => {
    expect(() => assertAllowedEndpoint("http://ai.example.com/infer", ["ai.example.com"], "https://loopos.example.com")).toThrow(/HTTPS/);
    expect(() => assertAllowedEndpoint("https://unknown.example.com/infer", ["ai.example.com"], "https://loopos.example.com")).toThrow(/allowlist/);
    expect(assertAllowedEndpoint("https://ai.example.com/infer", ["ai.example.com"], "https://loopos.example.com").hostname).toBe("ai.example.com");
  });

  it("rejects non-global HTTPS endpoint hosts even when explicitly allowlisted", () => {
    for (const endpoint of [
      "https://localhost/infer",
      "https://127.0.0.1/infer",
      "https://100.64.0.1/infer",
      "https://192.0.2.1/infer",
      "https://[::1]/infer",
      "https://[::ffff:127.0.0.1]/infer",
    ]) {
      const host = new URL(endpoint).hostname;
      expect(() => assertAllowedEndpoint(endpoint, [host], "https://loopos.example.com")).toThrow(/global, non-local/);
    }
  });

  it("preserves local HTTP evaluation endpoints", () => {
    expect(assertAllowedEndpoint("http://127.0.0.1:8787/infer", ["127.0.0.1:8787"], "http://localhost:4273").hostname).toBe("127.0.0.1");
  });

  it.each([
    "https://ai.example.com/infer?token=secret",
    "https://ai.example.com/infer#fragment",
    "https://ai.example.com\\infer",
  ])("rejects ambiguous configured endpoint %s", (endpoint) => {
    expect(() => assertAllowedEndpoint(endpoint, ["ai.example.com"], "https://loopos.example.com")).toThrow(/query strings, fragments, or backslashes/);
  });

  it("does not let browser runtime configuration widen the enterprise allowlist", async () => {
    vi.stubEnv("VITE_LOOPOS_DEPLOYMENT_MODE", "enterprise");
    vi.stubEnv("VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS", "ai.example.com");
    vi.resetModules();

    const { allowedHostsForConfiguredEndpoint, assertAllowedEndpoint: assertEnterpriseEndpoint } = await import("./secureRequest");
    const { allowedEndpointHosts, llmEndpoint } = await import("./runtimeConfig");
    window.__LOOPOS_RUNTIME_CONFIG__ = {
      llmEndpoint: "https://evil.example.com/infer",
      allowedEndpointHosts: ["evil.example.com"],
    };

    expect(llmEndpoint()).toBeUndefined();
    expect(allowedEndpointHosts()).toBeUndefined();
    expect(allowedHostsForConfiguredEndpoint("https://evil.example.com/infer")).toEqual(["ai.example.com"]);
    expect(() => assertEnterpriseEndpoint(
      "https://evil.example.com/infer",
      allowedHostsForConfiguredEndpoint("https://evil.example.com/infer"),
      "https://loopos.example.com",
    )).toThrow(/allowlist/);

    delete window.__LOOPOS_RUNTIME_CONFIG__;
    vi.unstubAllEnvs();
  });

  it("applies enterprise-safe fetch defaults", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-length": "15" }),
      text: async () => JSON.stringify({ status: "ok" }),
    });

    const result = await secureJsonRequest<{ status: string }>("https://ai.example.com/infer", {
      allowedHosts: ["ai.example.com"],
      fetchImpl: fetchImpl as never,
      init: { method: "POST", body: "{}" },
    });

    expect(result.status).toBe("ok");
    expect(fetchImpl).toHaveBeenCalledWith("https://ai.example.com/infer", expect.objectContaining({
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
    }));
  });

  it("rejects oversized responses before parsing", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-length": "2000" }),
      text: async () => "{}",
    });
    await expect(secureJsonRequest("https://ai.example.com/infer", {
      allowedHosts: ["ai.example.com"],
      fetchImpl: fetchImpl as never,
      maxResponseBytes: 100,
    })).rejects.toThrow(/response limit/);
  });

  it("enforces the response limit while reading chunked bodies", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array(101));
          controller.close();
        },
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));

    await expect(secureJsonRequest("https://ai.example.com/infer", {
      allowedHosts: ["ai.example.com"],
      fetchImpl: fetchImpl as never,
      maxResponseBytes: 100,
    })).rejects.toThrow(/response limit/);
  });

  it("aborts a response that stalls while reading its body", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        pull() {
          return new Promise<void>(() => undefined);
        },
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));

    await expect(secureJsonRequest("https://ai.example.com/infer", {
      allowedHosts: ["ai.example.com"],
      fetchImpl: fetchImpl as never,
      timeoutMs: 5,
    })).rejects.toThrow(/timed out/);
  });

  it("rejects a parsed response that fails the caller's runtime contract", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers(),
      text: async () => JSON.stringify({ status: 42 }),
    });

    await expect(secureJsonRequest<{ status: string }>("https://ai.example.com/infer", {
      allowedHosts: ["ai.example.com"],
      fetchImpl: fetchImpl as never,
      validate: (value): value is { status: string } => Boolean(value && typeof value === "object" && (value as { status?: unknown }).status === "ok"),
    })).rejects.toThrow(/invalid JSON response/);
  });

  it("aborts requests that exceed their deadline", async () => {
    const fetchImpl = vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    await expect(secureJsonRequest("https://ai.example.com/infer", {
      allowedHosts: ["ai.example.com"],
      fetchImpl: fetchImpl as never,
      timeoutMs: 5,
    })).rejects.toThrow(/timed out/);
  });
});
