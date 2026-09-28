# Product verification guide

Read this reference when selecting or executing checks for a changed or test-only product surface.

## Choose evidence by changed boundary

| Surface | Minimum useful evidence |
|---|---|
| Pure function, component, or local domain logic | Focused positive, negative, and boundary tests; type or lint checks when configured |
| API, service, database, queue, file, model, or provider integration | Contract or integration tests; auth, timeout, retry, malformed input, and failure behavior; migration checks when state changes |
| User-facing UI or route | Current served-app browser journey; visible outcome; navigation; keyboard/accessibility where relevant; mobile/responsive layout; console and page errors |
| Auth, tenant, privacy, or sensitive data | Server-side allow and deny tests; cross-tenant isolation; redacted fixtures; audit event verification; data lifecycle controls |
| Agent tool or consequential action | Input/result schema validation; operation allowlist; approval boundary; idempotency/replay; timeout; compensation; kill switch; adversarial cases |
| Build or release artifact | Production build/package; generated-artifact freshness; configuration validation; supply-chain checks when configured; smoke and rollback evidence |

Use a specialized security, migration, accessibility, performance, browser, or release skill when the task enters that domain and one is available.

## Verification order

1. Run the narrow regression, unit test, or deterministic probe.
2. Run related contract or integration checks.
3. Run configured typecheck, lint, compile, or production build.
4. Exercise affected critical journeys in a real served runtime when behavior crosses the browser or process boundary.
5. Run security, migration, accessibility, performance, supply-chain, or release checks required by the changed risk.
6. Run the broader regression gate after the changed-surface behavior is understood.

Scale depth with risk. A low-risk local function does not need release ceremony; a data, auth, tenant, agent-action, or production-facing change needs negative and failure-boundary evidence.

## Browser and runtime integrity

- Rebuild or regenerate the artifact when source changes require it.
- Start or restart the intended server and verify application identity, URL, port, environment, and build version before assertions.
- Detect stale or occupied ports and wrong-app responses before changing product code.
- Check browser console errors, page errors, failed requests, and visible completion state.
- For responsive work, test the relevant narrow viewport and confirm there is no hidden content or horizontal overflow.
- A mocked browser path proves the mock contract only. Keep it distinct from real integration and authenticated-live proof.

## Failure handling

Classify failures as change-caused, baseline, test defect/flakiness, stale runtime, missing dependency, configuration, permission, sandbox, or external-service failure.

Retry only after changing a relevant condition or when the tool defines retry behavior. Preserve the original failure and any retry result. Do not weaken assertions, skip meaningful checks, or replace real behavior with a mock to manufacture a pass.

Use these result labels:

- `PASS`: the named check passed for the intended target.
- `FAIL`: the check executed and violated its oracle or threshold.
- `SKIPPED`: the check did not execute.
- `DEGRADED`: the check ran with a known limitation, flakiness, fallback, or incomplete dependency.
- `BLOCKED`: a required input, authority, environment, or dependency prevented execution.

Only `PASS` is green proof for the named check.
