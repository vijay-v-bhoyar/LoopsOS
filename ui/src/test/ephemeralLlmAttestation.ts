// Ephemeral unit-test signer. No deployment key is stored or loaded.
import { createHash, sign, webcrypto, generateKeyPairSync } from "node:crypto";
const pair = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
const keys = { privateKey: pair.privateKey, publicKeySpki: pair.publicKey.export({ type: "spki", format: "der" }).toString("base64") };

export const testCrypto = webcrypto;
export function testPin(endpoint: string, task = "loopos_use_case_structuring") {
  return { endpoint, task, provider: "fixture-provider", model: "fixture-model", model_revision: `sha256:${"a".repeat(64)}`,
    prompt_version: `${task}_v1`, prompt_sha256: "b".repeat(64), key_id: "fixture-gateway-only", public_key_spki: keys.publicKeySpki,
    capability_profile_sha256: "c".repeat(64), evaluation_receipt_sha256: "d".repeat(64),
    capability_evaluated_at: new Date(Date.now() - 60_000).toISOString(), capability_expires_at: new Date(Date.now() + 86_400_000).toISOString(),
    lifecycle_status: "approved" as const };
}

export function signedResponse(body: string, result: unknown, mutations: Record<string, unknown> = {}) {
  const request = JSON.parse(body);
  const identity = request.provenance_request;
  const payload = { ...identity, task: request.task, request_sha256: createHash("sha256").update(body).digest("hex"),
    issued_at: new Date().toISOString(), expires_at: new Date(Date.now() + 60_000).toISOString(), result, ...mutations };
  const signed_payload = JSON.stringify(payload);
  return { key_id: "fixture-gateway-only", signed_payload,
    signature: sign("sha256", Buffer.from(signed_payload), { key: keys.privateKey, dsaEncoding: "ieee-p1363" }).toString("base64") };
}
