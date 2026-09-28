import { describe, expect, it } from "vitest";
import { requireConnectorUrl } from "./endpointValidation";

describe("requireConnectorUrl", () => {
  it("accepts HTTPS connectors and local development HTTP connectors", () => {
    expect(requireConnectorUrl(" https://enterprise.example/actions ", "Action endpoint")).toBe("https://enterprise.example/actions");
    expect(requireConnectorUrl("http://localhost:8787/actions", "Action endpoint")).toBe("http://localhost:8787/actions");
    expect(requireConnectorUrl("http://127.0.0.1:8787/actions", "Action endpoint")).toBe("http://127.0.0.1:8787/actions");
  });

  it.each([
    ["https://enterprise.example/actions?token=secret", "query strings or fragments"],
    ["https://enterprise.example/actions#fragment", "query strings or fragments"],
    ["https://enterprise.example\\actions", "backslashes"],
    ["https://user:password@enterprise.example/actions", "embedded credentials"],
    ["http://connector.example/actions", "use HTTPS"],
  ])("rejects unsafe connector URL %s", (value, message) => {
    expect(() => requireConnectorUrl(value, "Action endpoint")).toThrow(message);
  });
});
