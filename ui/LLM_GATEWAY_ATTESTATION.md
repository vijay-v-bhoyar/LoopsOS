# Optional LLM gateway provenance contract

Status: implemented client verification; live gateway, approved model pins, prompt digests and organization-controlled signing custody must be supplied by the deploying organization. No model/provider is selected or approved by this change. Legacy unsigned responses safely use deterministic questions/field proposals. Consent and the existing low/internal data restriction still apply.

## Deployment configuration

Set `VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS` to a JSON array of explicit contracts. Each entry contains `endpoint`, `task`, `provider`, `model`, `model_revision`, `prompt_version`, `prompt_sha256`, `key_id`, `public_key_spki`, `capability_profile_sha256`, `evaluation_receipt_sha256`, `capability_evaluated_at`, `capability_expires_at`, and `lifecycle_status: "approved"`.

- `endpoint` is the exact configured request endpoint, including path. Existing HTTPS, egress allowlist and redirect restrictions apply separately. Unknown endpoints have no trusted route.
- `task` is `loopos_use_case_questions` or `loopos_use_case_structuring` and `prompt_version` is the corresponding task plus `_v1`.
- `provider` and `model` are organization-approved identifiers. `model_revision` must be `sha256:` followed by 64 lowercase hex characters identifying the approved immutable revision artifact. A mutable alias or a version label without immutable evidence is insufficient. Closed providers without such evidence cannot satisfy this contract until the organization's adapter supplies an independently reviewed immutable revision record; never hash the string `latest` and call that immutability.
- `prompt_sha256` is the approved actual prompt artifact digest; changing model or prompt pins requires review and affected evaluation reruns.
- `capability_profile_sha256` and `evaluation_receipt_sha256` identify the dated capability and evaluation evidence for this exact model revision. `capability_evaluated_at` must not be materially in the future, `capability_expires_at` must be future-dated, and deprecated entries are rejected before egress. Updating a model revision requires a new capability profile, receipt, expiry and regression decision; the client never silently adopts a newer alias.
- `public_key_spki` is base64 DER SubjectPublicKeyInfo for an organization-controlled ECDSA P-256 public key. `key_id` identifies its approved custody/rotation record. Keep the private signing key exclusively on the trusted gateway. Neither a model response nor `window.__LOOPOS_RUNTIME_CONFIG__` can supply a trust root.
- Missing, malformed or ambiguous contracts deny the call before egress. Key rotation is a reviewed deployment change. Do not use keys in `src/test/llmAttestationKeys.json`: they are public synthetic fixtures and provide no deployment security.

Configuration is public compiled build input, not a secrets store. Do not put API credentials or private keys in any `VITE_` variable. Deployments must protect the build/configuration supply chain and signing service.

`VITE_LOOPOS_LLM_TIMEOUT_MS` is optional compiled timeout configuration: the default is 15 seconds and the maximum is 30 seconds. Enterprise mode ignores window timeout overrides. Evaluation overrides have the same upper bound.

The client also identifies the published synthetic signing key by SHA-256 of its normalized uncompressed public EC point. Renaming the key or removing `fixture_only` cannot make that key valid outside the exact development + evaluation + loopback + approved mock-route boundary. The application imports only its public fingerprint, never the fixture private key. Unknown keys still require organizational custody review: a fingerprint denylist cannot prove that another configured key is uncompromised.

There is no live client key-revocation channel. Rotation or revocation requires rebuilding configuration and replacing/reloading clients; already-open or cached clients may retain their previous pin. The gateway must enforce emergency revocation and access denial independently. A compromised gateway key is not remedied by the five-minute claim lifetime because an attacker can sign fresh claims. Production acceptance requires an exercised revocation procedure, cache/session handling and organization-controlled historical-key verification.

## Request and response protocol

The request retains the task-specific fields and adds `provenance_request` containing schema version `loopos-llm-attestation/v1`, a fresh UUID nonce, provider, model, model revision, prompt version and prompt digest. The gateway hashes the exact raw UTF-8 request bytes with SHA-256; do not reserialize before hashing.

The gateway must select its route from protected configuration, independently check the adapter's actual provider/model/revision and actual rendered prompt artifact, and refuse any mismatch. Requested identity is an expectation, never evidence. The gateway must not let model-generated content populate identity, key, expiry or attestation fields. If an actual identity or immutable revision cannot be established, return an error and let the UI use deterministic fallback. Fallback to a different model requires its own approved contract and fresh evaluation; do not reuse the original attestation.

Return a JSON object containing `key_id`, `signed_payload` and `signature`. `signed_payload` is a literal JSON string with these fields:

```text
schema_version, nonce, request_sha256, task, provider, model, model_revision,
prompt_version, prompt_sha256, capability_profile_sha256,
evaluation_receipt_sha256, capability_evaluated_at, capability_expires_at,
lifecycle_status, issued_at, expires_at, result
```

`result` contains the existing `{ questions: [...] }` or `{ proposal: {...} }` contract. Sign the exact UTF-8 `signed_payload` bytes, using ECDSA P-256/SHA-256 with IEEE-P1363 signature encoding (64 bytes, r concatenated with s), then base64 encode the signature. Timestamps require a timezone. Lifetime is at most five minutes, expiry must be future, issue time no more than 30 seconds in the future and no more than five minutes old. The client verifies the signature before parsing the claim, binds the nonce and exact request hash, matches every pin and checks time, then validates the task-specific result. Extra unsigned result fields are ignored.

Minimal Node signing integration after all independent adapter/policy checks:

```js
import { createHash, sign } from "node:crypto";
function signGatewayResult(rawRequestBytes, checkedClaim, privateKey, keyId) {
  // checkedClaim comes from the trusted adapter and protected policy, never from model output.
  const signed_payload = JSON.stringify({
    ...checkedClaim,
    request_sha256: createHash("sha256").update(rawRequestBytes).digest("hex"),
  });
  return {
    key_id: keyId,
    signed_payload,
    signature: sign("sha256", Buffer.from(signed_payload, "utf8"), {
      key: privateKey, dsaEncoding: "ieee-p1363",
    }).toString("base64"),
  };
}
```

This is a signing integration reference, not a deployed gateway or provider adapter. The gateway also needs server-side authentication, authorization, protected policy, egress/data controls, request limits, replay handling, key custody, audit, and verified provider execution. Do not expose this signer as a service that blindly signs arbitrary caller claims.

## Evidence and limits

Accepted output records actual configured provider/model, signed generation time, prompt version, immutable revision, prompt digest, capability profile and evaluation receipt digests, capability evidence dates/status, attestor key ID, request hash, signed payload, signature and local verification time in `AIProvenance.gateway_attestation`. Mixed field drafts preserve deterministic provenance for unchanged fields. Deterministic fallback has no gateway attestation. A capability record is still a configured gateway statement; it does not independently prove vendor execution or safety. Expired or deprecated evidence fails closed and callers use their deterministic fallback.

The verification label is `configured-gateway-signature`: it proves what the configured gateway signed and binds that statement to this request/output. It does not independently prove proprietary vendor internals, output truth, authorization to deploy, or lifetime integrity after a user edits/imports saved workspace data. Consumers must reverify preserved signatures against the approved historical key/policy before treating stored provenance as audit evidence. Existing imported records without an attestation remain historical unverified records.

Signed payloads contain the suggestion text. Apply the same access and retention policy as the original workspace; signatures provide integrity, not encryption or permission to retain data. Data classified above internal never enters this optional route even with user consent.

Field enhancement checks both the saved classification and the source-derived proposed classification before egress. Each must explicitly be low or internal. Unclassified or more restricted saved data cannot become eligible merely because supplied source text claims a lower classification. This is a classification-boundary control, not automatic discovery of sensitive content mislabeled by a user.

## Local browser fixtures

For the evaluation browser gate set `LOOPOS_E2E_LLM_ATTESTATION_FIXTURE=1` and `VITE_LOOPOS_DEPLOYMENT_MODE=evaluation`, then run `npm run test:e2e`. The test runner injects synthetic public contracts only for `/api/mock-llm-questions` and `/api/mock-field-enhancement`; Playwright intercepts both endpoints and signs fixture results. It refuses enterprise mode and will not overwrite real configured trust. Runtime validation also rejects marked fixture contracts outside a development build on loopback in evaluation mode or for non-mock endpoints. Leave this flag unset for the enterprise readiness gate. Do not deploy test signing keys or treat fixture signatures as enterprise evidence.
