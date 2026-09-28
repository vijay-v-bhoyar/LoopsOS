import type { AIProvenance } from "../types";
import { isLocalLlmFixtureEndpoint, llmAttestationContracts, llmTimeoutMs } from "./runtimeConfig";
import { secureJsonRequest } from "./secureRequest";

interface AttestationPin {
  endpoint: string;
  task: string;
  provider: string;
  model: string;
  model_revision: string;
  prompt_version: string;
  prompt_sha256: string;
  key_id: string;
  public_key_spki: string;
  capability_profile_sha256: string;
  evaluation_receipt_sha256: string;
  capability_evaluated_at: string;
  capability_expires_at: string;
  lifecycle_status: "approved";
}

const digestPattern = /^[a-f0-9]{64}$/;
const revisionPattern = /^sha256:[a-f0-9]{64}$/;
const maxLifetimeMs = 5 * 60_000;
// SHA-256 of the normalized uncompressed public EC point of the published browser fixture.
// Only a fingerprint enters the application; no test private key is imported.
const publishedFixtureKeyFingerprint = "271175e0571b695884515a5d0bc7e92c06dcf48a78fa71a97ca7e874f1ab4caa";
const encoder = new TextEncoder();

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function boundedText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= 2_000;
}

function isPin(value: unknown): value is AttestationPin {
  return record(value)
    && ["endpoint", "task", "provider", "model", "prompt_version", "key_id", "public_key_spki"].every((key) => boundedText(value[key]))
    && typeof value.model_revision === "string" && revisionPattern.test(value.model_revision)
    && typeof value.prompt_sha256 === "string" && digestPattern.test(value.prompt_sha256)
    && typeof value.capability_profile_sha256 === "string" && digestPattern.test(value.capability_profile_sha256)
    && typeof value.evaluation_receipt_sha256 === "string" && digestPattern.test(value.evaluation_receipt_sha256)
    && typeof value.capability_evaluated_at === "string" && typeof value.capability_expires_at === "string"
    && value.lifecycle_status === "approved";
}

async function sha256(value: string): Promise<string> {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)))].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function decodeBase64(value: string): Uint8Array<ArrayBuffer> {
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(value)) throw new Error("Invalid attestation encoding.");
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

function timestamp(value: unknown): number {
  return typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : Number.NaN;
}

function capabilityIsCurrent(pin: AttestationPin, now: number): boolean {
  const evaluated = timestamp(pin.capability_evaluated_at);
  const expires = timestamp(pin.capability_expires_at);
  return Number.isFinite(evaluated) && Number.isFinite(expires)
    && evaluated <= now + 30_000 && expires > now && expires > evaluated;
}

/** Verifies the configured gateway's statement, not independent knowledge of vendor internals. */
export async function requestAttestedLlm(
  endpoint: string,
  task: string,
  promptVersion: string,
  input: Record<string, unknown>,
  fetchImpl?: typeof fetch,
): Promise<{ result: unknown; provenance: AIProvenance }> {
  const contracts = llmAttestationContracts();
  if (!Array.isArray(contracts) || !contracts.every(isPin)) throw new Error("Missing model attestation configuration.");
  const matches = contracts.filter((pin) => pin.endpoint === endpoint && pin.task === task && pin.prompt_version === promptVersion);
  if (matches.length !== 1) throw new Error("No unique approved model pin.");
  const pin = matches[0];
  const now = Date.now();
  if (!capabilityIsCurrent(pin, now)) throw new Error("Model capability evidence is expired or invalid.");
  // Import before egress so malformed trust configuration never causes a model call.
  const publicKey = await crypto.subtle.importKey("spki", decodeBase64(pin.public_key_spki), { name: "ECDSA", namedCurve: "P-256" }, true, ["verify"]);
  const publicPoint = await crypto.subtle.exportKey("raw", publicKey);
  const keyFingerprint = [...new Uint8Array(await crypto.subtle.digest("SHA-256", publicPoint))].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  if (keyFingerprint === publishedFixtureKeyFingerprint && !isLocalLlmFixtureEndpoint(endpoint)) {
    throw new Error("Published fixture signing key is forbidden outside local mock evaluation.");
  }
  const nonce = crypto.randomUUID();
  const requestBody = JSON.stringify({ ...input, task, provenance_request: {
    schema_version: "loopos-llm-attestation/v1", nonce, provider: pin.provider, model: pin.model,
    model_revision: pin.model_revision, prompt_version: promptVersion, prompt_sha256: pin.prompt_sha256,
    capability_profile_sha256: pin.capability_profile_sha256,
    evaluation_receipt_sha256: pin.evaluation_receipt_sha256,
    capability_evaluated_at: pin.capability_evaluated_at,
    capability_expires_at: pin.capability_expires_at,
    lifecycle_status: pin.lifecycle_status,
  } });
  const requestHash = await sha256(requestBody);
  const envelope = await secureJsonRequest<Record<string, unknown>>(endpoint, {
    fetchImpl, timeoutMs: llmTimeoutMs(),
    init: { method: "POST", headers: { "content-type": "application/json" }, body: requestBody },
    validate: record,
  });
  if (envelope.key_id !== pin.key_id || typeof envelope.signed_payload !== "string" || !boundedText(envelope.signature)) {
    throw new Error("Provider self-report is not verified provenance.");
  }
  const verified = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, publicKey, decodeBase64(envelope.signature), encoder.encode(envelope.signed_payload));
  if (!verified) throw new Error("Invalid gateway attestation signature.");
  const claim: unknown = JSON.parse(envelope.signed_payload);
  if (!record(claim) || claim.schema_version !== "loopos-llm-attestation/v1" || claim.nonce !== nonce || claim.request_sha256 !== requestHash
    || claim.task !== task || claim.provider !== pin.provider || claim.model !== pin.model || claim.model_revision !== pin.model_revision
    || claim.prompt_version !== promptVersion || claim.prompt_sha256 !== pin.prompt_sha256
    || claim.capability_profile_sha256 !== pin.capability_profile_sha256
    || claim.evaluation_receipt_sha256 !== pin.evaluation_receipt_sha256
    || claim.capability_evaluated_at !== pin.capability_evaluated_at
    || claim.capability_expires_at !== pin.capability_expires_at
    || claim.lifecycle_status !== pin.lifecycle_status) throw new Error("Gateway identity or request binding mismatch.");
  const issued = timestamp(claim.issued_at);
  const expires = timestamp(claim.expires_at);
  if (!Number.isFinite(issued) || !Number.isFinite(expires) || issued > now + 30_000 || issued < now - maxLifetimeMs
    || expires <= now || expires <= issued || expires - issued > maxLifetimeMs) throw new Error("Gateway attestation expired or invalid.");
  return { result: claim.result, provenance: {
    source: "external", provider: pin.provider, model: pin.model, prompt_version: promptVersion,
    consent_granted: true, generated_at: new Date(issued).toISOString(),
    gateway_attestation: {
      verification: "configured-gateway-signature", model_revision: pin.model_revision, prompt_sha256: pin.prompt_sha256,
      capability_profile_sha256: pin.capability_profile_sha256,
      evaluation_receipt_sha256: pin.evaluation_receipt_sha256,
      capability_evaluated_at: pin.capability_evaluated_at,
      capability_expires_at: pin.capability_expires_at,
      lifecycle_status: pin.lifecycle_status,
      key_id: pin.key_id, request_sha256: requestHash, signed_payload: envelope.signed_payload,
      signature: envelope.signature, verified_at: new Date(now).toISOString(),
    },
  } };
}
