import { describe, expect, it, vi } from "vitest";
import { assertAllowedEndpoint, secureJsonRequest } from "./secureRequest";

describe("secureRequest", () => {
  it("rejects insecure remote and non-allowlisted endpoints", () => {
    expect(() => assertAllowedEndpoint("http://ai.example.com/infer", ["ai.example.com"], "https://loopos.example.com")).toThrow(/HTTPS/);
    expect(() => assertAllowedEndpoint("https://unknown.example.com/infer", ["ai.example.com"], "https://loopos.example.com")).toThrow(/allowlist/);
    expect(assertAllowedEndpoint("https://ai.example.com/infer", ["ai.example.com"], "https://loopos.example.com").hostname).toBe("ai.example.com");
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
