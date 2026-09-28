# LoopsOS 13-owner assurance report — help and recovery slice addendum

**Assessment date: September 22, 2026 (America/New_York). Decision remains NO-GO for Fortune 500 or other enterprise production reliance.** This addendum records one local help/recovery workflow slice after the full 13-owner baseline in [the September 21 report](LOOPSOS_13_OWNER_TEST_REPORT_FRESH_2026-09-21.md). Read that report for the complete owner threat cases, source review, and external closure requirements. This delta does not certify the product, close organizational risks, or authorize a pilot or release.

## Governing identity and decision

- Conductor: `product-lifecycle-loop`; selected delivery engine: `codex-product-build-loop`. The 13-owner method is supplied by `enterprise-ai-assurance-loop`; it is not an additional delivery engine.
- Authoritative registry: [skill-fleet/registry.json](../skill-fleet/registry.json), SHA-256 `2e203517ca2c6009ff60bebc2d3af54d5a6cc6b5bac8cafef54e1fa4e7052027`. Embedded lifecycle policy: v1.1.0, SHA-256 `436576de960e56410d114ecccbb654215b22146080dcff2e84936baaf55d43cf`.
- Current lifecycle run: [LOOPSOS-ENTERPRISE-REPAIR-20260920](../.loop/runs/LOOPSOS-ENTERPRISE-REPAIR-20260920.json), still `PARTIAL`, release `NO_GO`, deployment authorization `false`, parent acceptance incomplete. Existing external help items remain needed/requested; this feature does not satisfy them.
- The prior risk register remains bound to subject `870a404c709e886ccbf25cf34a071d68dacbd18bb6cd0b3b9b7dcade7e8ee38e`, with 26 records (15 partial-local, 6 open external/organizational, 5 local pass). It was not rebound to the new UI slice. The earlier 338-file subject manifest is historical evidence, not a hash claim over this addendum’s code.
- No provider credentials, billing, network egress for product behavior, external writes, production deployment, or live release action was used.

## What changed

The Workspace Console now exposes a help-request ledger for blocked goals. A request records the blocked acceptance criterion, requested owner/team, action, risk while waiting, deadline, wake condition, and evidence references. The state path is `draft → waiting` or `delivery_failed → response_recorded → revalidation_needed → closure_review_requested` (a failed revalidation returns to `response_recorded`).

The workflow records delivery attempts by reference only; it does not send a message. It caps delivery attempts at three and revalidation plans at ten, requires a different user ID to plan a retest and a third user ID to record the result, and prevents event time from moving backward. A passing retest requests external closure review; the UI cannot close the parent assurance gate. Workspace import validation checks event shape, bounded counts and lengths, evidence references, status replay, timestamps, and the distinct-user-ID constraints. Legacy workspaces normalize to an empty help ledger. A Markdown handoff can be downloaded and explicitly states that LoopOS did not send the request and does not independently verify user-entered records.

These are local workflow safeguards, not authorization or identity proof. Workspace JSON and event entries remain user-editable; distinct profile IDs can be fabricated. No signed append-only event store, server-side authorization, automatic scheduler, alert delivery, staffed escalation, dead-letter queue, provider reconciliation, or automatic retry was added. Deadlines can be viewed as overdue when the UI is opened; there is no timer service to wake or page someone.

## 13-owner impact matrix

The owner threat cases and original blue-team evidence remain in the baseline report. The status column below states what this specific delta changes; it does not claim a fresh full adversarial campaign for every owner.

| # / owner | Delta evidence and red-team interpretation | Current disposition |
|---|---|---|
| 0 — `enterprise-ai-discovery` | The help workflow is visible in the Workspace Console and Graphify map. It does not inventory deployed products, shadow AI, legal entities, subprocessors, or production routes. | No closure. Deployed-system inventory and accountable-owner confirmation remain open. |
| 1 — `enterprise-ai-quality` | Added deterministic form/state validation and regression tests. No business loss function, independently collected outcome, cohort denominator, subgroup metric, or review-miss rate was established. | No closure. Enterprise thresholds and outcome data remain unapproved/unmeasured. |
| 2 — `enterprise-llm-assurance` | This slice has no LLM call, model route, prompt, retrieval, or provider data path. | No closure. Real-provider, data-egress, update, retention, poisoning, and fallback tests remain open. |
| 3 — `enterprise-agentic-assurance` | Help handoff attempts are bounded and auditable as local entries. Since delivery is manual and unverified, the ledger cannot reconcile an external effect, lost response, duplicate send, or provider restart. | No closure. Hosted locking/RLS and real provider commit/replay/cancellation tests remain open. |
| 4 — `enterprise-frontier-assurance` | No frontier model, new capability, model promotion, or model evidence was exercised. | No closure. Version-pinned evaluation with sealed holdouts and candidate-vs-baseline evidence remains open. |
| 5 — `enterprise-ai-threat-modeling` | Import validation now rejects malformed/replayed help histories and enforces structural role separation. A malicious workspace editor can still forge the records, references, identities, and timestamps; this does not resolve the scanner and production network/identity gaps in the baseline. | Partial local hardening only. Independent security scans and production threat exercises remain open. |
| 6 — `enterprise-quantum-safe-assurance` | No cryptographic algorithm, key custody, signing root, HSM, or post-quantum migration behavior changed or was exercised. | No closure. Inventory, custody, rotation/revocation, recovery, and migration plan remain open. |
| 7 — `enterprise-advanced-capability-assurance` | Bounded help/revalidation counters and explicit closure-review state make local incomplete-work handling clearer. No long-horizon, multi-agent, collusion, or frontier-capability campaign was run. | No closure. Advanced capability and full outcome-reconciliation exercises remain open. |
| 8 — `enterprise-ai-regulatory-assurance` | The ledger records a deadline and wake condition but does not establish jurisdiction, classification, legal basis, retention, appeal, notice, or counsel review. | No closure. Organization-selected obligations and legal review remain open. |
| 9 — `enterprise-ai-data-lifecycle` | Workspace persistence now includes help history; handoff Markdown exports only references, not referenced evidence contents. No new retention, legal-hold, deletion, backup/restore, provider-copy, or model-training exclusion control was proved. | No closure. Hosted deletion/resurrection and data-lineage exercises remain open. |
| 10 — `enterprise-ai-independent-challenge` | Requester, retest planner, and retest recorder must have distinct user IDs in the local data model. The system does not authenticate those identities or establish separate custody, independent administration, blinding, or veto authority. | Partial local structural guard only. Independent second-line challenge and closure remain open. |
| 11 — `enterprise-ai-vendor-assurance` | No vendor route, model alias, vendor contract, App installation, SBOM, or vendor recovery path was changed or verified. | No closure. Actual vendor configuration, terms, change notices, fallback independence, and exit drill remain open. |
| 12 — `enterprise-human-ai-operations` | This is the primary beneficiary: a blocked goal can retain owner, request, risk, deadline, wake condition, delivery/response/retest references, and bounded retry history. It helps preserve a recovery trail, but creates no staffed coverage, automatic notice, measured SLA, workload capacity, dead-letter handling, in-flight drain, customer remediation, or hosted restore evidence. | Partial local improvement. Owner 12 remains open; run a staffed recovery drill with measured stop-to-containment and stop-to-customer-recovery times. |

## Verification performed for this slice

- Full UI test suite rerun on September 22: **33 test files, 331 tests passed**.
- Targeted help workflow, ledger component, and workspace migration checks after hardening: **31 tests passed across 3 files**.
- Production UI build: **PASS**; fresh production build completed with a 503.97 kB JavaScript chunk (148.84 kB gzip), a 2.38 MB PDF worker, and a 3.52 MB dataset (203.81 kB gzip); Vite emitted its >500 kB chunk warning. Existing large-chunk/performance concern remains.
- Design-token check: **PASS**.
- Local browser journey for bounded workspace export: **2 passed**, desktop Chromium and mobile Chromium, against an isolated temporary SQLite database. This exercises workspace render/export and portability; the help ledger’s direct actions are covered by component tests, not this browser scenario. An initial harness invocation could not locate Python 3.12; rerun with the documented Python 3.12.14 runtime and `LOOPOS_PYTHON` passed.
- Fleet registry validation: **PASS** for the governing registry and inventory. This checks policy/metadata integrity, not runtime security.
- Graphify was refreshed after the source changes in code-only mode: **11,826 nodes, 19,159 links, 756 communities**; `graphify-out/graph.json` SHA-256 `c6e9b883f937d675cdb98234da45c14fc4551436e57d2368b6feac61ce65643f` and `graphify-out/GRAPH_REPORT.md` SHA-256 `57e0ba71bdd0dd5a221de90166d4101d0df8affcb807c57548f5416bf5ce968e`. no unverified or dangling graph elements were reported. One self-loop remains on `supabase_migrations_20260720010000_loopos_authority_runs`, extracted from `supabase/migrations/20260720010000_loopos_authority.sql` at line 1; treat it as a graph warning to investigate, not proof of a runtime defect. The installed Claude-facing Graphify skill is 0.9.41 while the detected package is 0.9.53. Saved labels number 754 for 756 communities; semantic label refresh was not run.
- The full baseline remains relevant: 13 owner fixtures **39/39 passed**, shared assurance **51 passed**, authority tests **422 passed / 1 hosted-Postgres test skipped**, and the earlier broader browser evaluation **100 passed / 10 enterprise-only skipped**. These predate this help-ledger delta and therefore do not establish that the feature closes any enterprise blocker.

## Source hashes and evidence boundary

These are SHA-256 hashes of the current working-tree files, not a signed release artifact or a deployment digest:

| File | SHA-256 |
|---|---|
| `ui/src/lib/helpRequestWorkflow.ts` | `5f357585c475a25fedcc52f53d9995000eea1d8126191df2f7f3acdf79f4c1e4` |
| `ui/src/lib/helpRequestWorkflow.test.ts` | `c26135a9c15e79be230d3ca70c33433172110d49efb2f33b1161d8158b18520f` |
| `ui/src/components/HelpRequestLedger.tsx` | `e6e12422adc14c5d50bab4abacf739c15511ab9ac2f5fb1e0aaccf862deb97dc` |
| `ui/src/components/HelpRequestLedger.test.tsx` | `34b080df4c434d1e5805b9b24b14af994af264824abc5aaac1235b681489fdfe` |
| `ui/src/lib/workspaceDocument.ts` | `fca32185736786e24b2f24ef525d011fc72543cb0534bac0a4035534ddcd5e71` |
| `ui/src/lib/workspaceStore.ts` | `5a25adb91bb3bbc2e89b8aac4f125f87e9c30939a96d42b6b42e46ba85ff732f` |
| `ui/src/screens/WorkspaceConsole.tsx` | `98b0e9795f91fceb766ae19ff41b4d4e06fcfbe026e9347e03d66151aecbb174` |
| `ui/src/types.ts` | `c5e0a877a85d5acfb5e9fccbb60eaac4efb504976ec866a8756c0aeb587e1fdb` |

This review did not exercise hosted PostgreSQL, tenant RLS, production identity, live provider behavior, enterprise alert delivery, restoration, or an independently controlled challenge. Existing uncommitted workspace changes were preserved; this report does not attribute unrelated working-tree changes to the help/recovery slice.

## Required next evidence before reconsidering GO

1. Move help-request events behind authenticated, tenant-scoped authority with role-bound identities and tamper-evident event history; test forgery, import/export, replay, cross-tenant references, and concurrent updates.
2. Add and exercise a real scheduler/notification path with delivery receipts, retry backoff, dead-letter ownership, wake-condition checks, escalation and deduplication; record outage and reconciliation behavior.
3. Run a staffed human-operations simulation with measured reviewer load, SLA misses, kill-switch plus in-flight drain, provider-effect reconciliation, customer notification/remediation, and restore objectives.
4. Commission independent assurance with separate identities, tools, data custody, sealed negative controls, and authority to veto. Reconcile every finding through reproduction, repair, retest, and independent closure.
5. Refresh all 13 owner dispositions against one new immutable source/build subject and obtain current organization-owned hosted evidence. Update the risk register only through its governed binding path.
6. Keep deployment fail-closed until the parent goal has current acceptance evidence and the authorized release process approves a concrete deployable artifact.

**Release disposition: NO-GO. Parent goal: incomplete. Deployment: not authorized.**