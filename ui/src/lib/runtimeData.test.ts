import { describe, expect, it, vi } from "vitest";
import { looposData } from "./loopos";
import { loadLooposData } from "./runtimeData";

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

describe("loadLooposData", () => {
  it("loads a valid catalog from the emitted static asset", async () => {
    const fetcher = vi.fn(async () => response(looposData));

    await expect(loadLooposData(fetcher)).resolves.toMatchObject({ stats: looposData.stats });
    expect(fetcher).toHaveBeenCalledWith(expect.any(String), { headers: { accept: "application/json" } });
  });

  it("fails closed when the catalog request is not successful", async () => {
    await expect(loadLooposData(async () => response({}, 503))).rejects.toThrow("HTTP 503");
  });

  it("fails closed when the catalog payload is malformed", async () => {
    await expect(loadLooposData(async () => response({ loops: [] }))).rejects.toThrow("catalog response is invalid");
  });
});
