import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requestAttestedLlm } from "./llmProvenance";
import { signedResponse, testCrypto, testPin } from "../test/ephemeralLlmAttestation";
import { signedResponse as publishedResponse, testPin as publishedPin } from "../test/llmAttestation";

const endpoint = "https://enterprise.example/intake";
const task = "loopos_use_case_structuring";
const prompt = `${task}_v1`;
const result = { proposal: { title: "Attested suggestion" } };
function responder(mutations: Record<string, unknown> = {}) {
  return vi.fn(async (_url, options) => new Response(JSON.stringify(signedResponse(options.body, result, mutations)), { status: 200 }));
}
describe("gateway attestation", () => {
  beforeEach(() => {
    vi.stubGlobal("crypto", testCrypto);
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([testPin(endpoint)]));
  });
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("binds a signed result to pinned provider, immutable revision, prompt and exact request", async () => {
    const fetchImpl = responder();
    const value = await requestAttestedLlm(endpoint, task, prompt, { source: "fixture" }, fetchImpl);
    expect(value.result).toEqual(result);
    expect(value.provenance).toMatchObject({ provider: "fixture-provider", model: "fixture-model", gateway_attestation: {
      verification: "configured-gateway-signature", model_revision: `sha256:${"a".repeat(64)}`, key_id: "fixture-gateway-only",
      capability_profile_sha256: "c".repeat(64), evaluation_receipt_sha256: "d".repeat(64), lifecycle_status: "approved",
    } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
  it.each([
    ["provider mismatch", { provider: "impostor" }], ["model mismatch", { model: "other-model" }],
    ["floating revision", { model_revision: "latest" }], ["missing revision", { model_revision: undefined }],
    ["wrong prompt", { prompt_version: "other-prompt" }], ["changed prompt", { prompt_sha256: "c".repeat(64) }],
    ["changed capability profile", { capability_profile_sha256: "e".repeat(64) }],
    ["changed evaluation receipt", { evaluation_receipt_sha256: "e".repeat(64) }],
    ["changed capability expiry", { capability_expires_at: new Date(Date.now() + 172_800_000).toISOString() }],
    ["replayed nonce", { nonce: "old-nonce" }], ["wrong request", { request_sha256: "c".repeat(64) }],
    ["expired", { issued_at: new Date(0).toISOString(), expires_at: new Date(1000).toISOString() }],
    ["future issue", { issued_at: new Date(Date.now() + 120_000).toISOString() }],
  ])("rejects %s even with a valid signature", async (_name, mutation) => {
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, responder(mutation))).rejects.toThrow();
  });
  it("rejects unsigned legacy content and model-supplied verification keys", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ ...result, provider: "fixture-provider", verified: true,
      public_key_spki: testPin(endpoint).public_key_spki }), { status: 200 }));
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow("self-report");
  });
  it("rejects output tampering", async () => {
    const fetchImpl = vi.fn(async (_url, options) => {
      const envelope = signedResponse(options.body, result);
      envelope.signed_payload = envelope.signed_payload.replace("Attested suggestion", "Tampered suggestion");
      return new Response(JSON.stringify(envelope));
    });
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow("signature");
  });
  it.each([[], [testPin(endpoint), testPin(endpoint)], [{ ...testPin(endpoint), model_revision: "latest" }],
    [{ ...testPin(endpoint), public_key_spki: "bad-key" }], [{ ...testPin(endpoint), endpoint: "https://different.example/intake" }]])(
    "refuses invalid or ambiguous deployment trust before egress: %j", async (...pins) => {
      vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify(pins));
      const fetchImpl = responder();
      await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow();
      expect(fetchImpl).not.toHaveBeenCalled();
    },
  );
  it.each([
    ["missing capability profile", { capability_profile_sha256: undefined }],
    ["expired capability evidence", { capability_expires_at: new Date(Date.now() - 1_000).toISOString() }],
    ["future evaluation evidence", { capability_evaluated_at: new Date(Date.now() + 120_000).toISOString() }],
    ["deprecated model", { lifecycle_status: "deprecated" }],
  ])("rejects %s before egress", async (_name, mutation) => {
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([{ ...testPin(endpoint), ...mutation }]));
    const fetchImpl = responder();
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow();
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it("ignores window-supplied attestation trust", async () => {
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", "[]");
    Object.assign(window, { __LOOPOS_RUNTIME_CONFIG__: { llmAttestationContracts: [testPin(endpoint)] } });
    const fetchImpl = responder();
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow();
    expect(fetchImpl).not.toHaveBeenCalled();
    delete window.__LOOPOS_RUNTIME_CONFIG__;
  });
  it("rejects marked fixture pins in a production build before egress", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([{ ...testPin(endpoint), fixture_only: true }]));
    const fetchImpl = responder();
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow();
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it("rejects marked fixture pins for a real endpoint even in local development", async () => {
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([{ ...testPin(endpoint), fixture_only: true }]));
    const fetchImpl = responder();
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow();
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it.each([true, false])("rejects the public fixture key with marker removed and renamed identity, DEV=%s", async (development) => {
    vi.stubEnv("DEV", development);
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([{ ...publishedPin(endpoint), key_id: "production-looking-key", provider: "claimed-provider" }]));
    const fetchImpl = responder();
    await expect(requestAttestedLlm(endpoint, task, prompt, {}, fetchImpl)).rejects.toThrow("Published fixture signing key");
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it("allows the published key only on the exact local evaluation mock route", async () => {
    vi.stubEnv("DEV", true);
    const localEndpoint = "/api/mock-field-enhancement";
    vi.stubGlobal("window", { location: { hostname: "localhost", origin: "http://localhost" }, setTimeout, clearTimeout });
    vi.stubEnv("VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS", JSON.stringify([{ ...publishedPin(localEndpoint), fixture_only: true }]));
    const fetchImpl = vi.fn(async (_url, options) => new Response(JSON.stringify(publishedResponse(options.body, result))));
    expect((await requestAttestedLlm(localEndpoint, task, prompt, {}, fetchImpl)).result).toEqual(result);
  });
});
