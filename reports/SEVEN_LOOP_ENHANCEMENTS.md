# Seven loop enhancements: implementation and verification

Updated 2026-09-13. All seven requested coordinating loops now have implemented local controls, updated skill instructions, and executed tests. Their installed copies match the tested source. This report supersedes the provisional status of these seven loops in the individual strengthening plan; that plan's wider specialist recommendations remain separate work.

Words are Spells: passing local controls establish the behavior described below. They do not establish a product's production readiness or guarantee completion when required authority, credentials, resources, or decisions are unavailable.

## What changed in each loop

| Loop | Implemented strengthening | Package tests |
| --- | --- | ---: |
| product-lifecycle-loop | SQLite scheduling with real subprocess dispatch, cumulative dispatch/time reservations, pinned configuration, cancellation, local help delivery and response receipts, exact parent-goal completion checks, and reviewed limits-only state migration. | 72 |
| codex-product-build-loop | Persistent failure IDs, hypotheses, bounded repair history, original failure and regression evidence, typed help, and explicit unmet parent criteria. A finished repair returns for parent review. | 16 |
| product-loop | Portable Python admission/runner, exact repository and configuration identity, real Windows process-family cancellation, retained crash reservations, parked-work fingerprints, and explicit release blocking for the legacy compatibility lane. | 25 |
| agentic-product-loop | Wrapper and runner share the same admission implementation and pinned adapter hash. Legacy discovery cannot claim execution readiness. Canonical reference identity is preserved. | 5 |
| agentic-assurance-loop | Stable findings bound to reproduction, repair, original/regression proof, subject and expiry; separate named verifier where required; assessment-only mode cannot claim a repair. Closure remains an explicit review result. | 16 |
| product-vision | Durable assumptions with owners, experiments, decision owners, revisit triggers, and affected acceptance criteria. New experiments invalidate prior decisions; unresolved criteria remain visible. | 16 |
| loop-fleet | Transactional concurrency and resource claims, aggregate reservations, lease fencing, real cancellation/timeouts, changed-file ownership checks, and serial integration verification. Unsafe legacy launch and automatic merge/cleanup routes are disabled. | 23 |
| **Total** | **Unit and real process tests on the final source** | **173** |

Executable entrypoints and their operational contracts are in:

- [Lifecycle runtime](../skill-packages/product-lifecycle-loop/references/local-runtime.md), including `local_scheduler.py` and `migrate_state.py`.
- [Build repair ledger](../skill-packages/codex-product-build-loop/scripts/repair_ledger.py).
- [Portable cycle contract](../skill-packages/product-loop/references/local-cycle-contract.md).
- [Agentic wrapper guard](../skill-packages/agentic-product-loop/scripts/loop_guard.py).
- [Assurance finding ledger](../skill-packages/agentic-assurance-loop/scripts/finding_ledger.py).
- [Vision ledger](../skill-packages/product-vision/scripts/vision_ledger.py).
- [Fleet runtime](../skill-packages/loop-fleet/scripts/fleet_runtime.py).

## How progress, repair and help work

The conductor keeps the parent's criteria and pending dependencies. A due local job reserves resources before dispatching a pinned cycle. Each child records its result and supporting artifacts, then returns to the parent. Finishing a child does not finish the goal.

Failures preserve their identity and diagnosis history. Changed evidence can justify another bounded attempt; repeating an already reconsidered parked-work fingerprint cannot create an unlimited retry route. Independent required work can continue while another dependency waits. Unknown process or external-effect state stays unresolved until reconciled.

Help requests can be delivered atomically to a local inbox with deduplicated receipts. A matching response is recorded as data and requires revalidation; its text is not executable authority. Delivery is distinct from recipient acknowledgment. The loop must keep the blocked criterion visible until the response actually resolves it.

The scheduler's completion path requires the exact goal, parent criteria, repository revision and configuration subject, a ready progress review, and current adapter admission. Changed product identity or an easier criterion cannot complete the original goal. These checks validate the supplied review structure and binding; they do not authenticate a reviewer or determine whether arbitrary evidence is semantically truthful.

## Red-team findings repaired

Independent runtime review reproduced two defects and confirmed their repairs:

1. Goal completion could accept the same goal ID with easier criteria or a different subject. Completion now binds both the parent criteria and exact subject, with positive and negative cases.
2. Fleet integration rounded positive fractional remaining time down to zero. The runtime now preserves finite positive duration and rejects invalid numeric values; an actual short integration run verifies it.

Final runner validation also found a STOP race after reservation but before dispatch. That path now returns cancellation, retains charged accounting, closes the waiting pipe, and does not dispatch. Windows cancellation waits for the Job's active process count to reach zero; uncertain cleanup keeps the run active instead of admitting a duplicate. A real descendant delayed-write test verifies termination behavior.

Independent results on the final source:

- [Runtime red check](SEVEN_LOOP_RUNTIME_REDCHECK.md): **18/18 cases passed**, covering real subprocesses, concurrency, cancellation, crash reservations, completion, help delivery, migration and guard parity.
- [Owner-ledger red check](SEVEN_LOOP_OWNER_REDCHECK.md): **8/8 cases passed**, using 62 ledger CLI subprocesses and actual fail/pass probes across build, assurance and vision.

These are scoped adversarial checks, not a proof that no defects remain.

## Installation and evidence

The seven packages contain **82 authored files**. **137 files** were copied to **12 existing installation roots**: all seven personal Codex skills, the workspace build and assurance skills, and the existing agent copies of product-loop, product-vision and loop-fleet. Previous files were backed up; unrelated files were preserved.

- [Final test results](../output/seven-loop-final-unit-results.json): 173 passing tests.
- [Package validation](../output/seven-loop-final-validation.json): all seven source skills pass the official skill-creator validator; no broken internal references.
- [Installation manifest and backup paths](../output/seven-loop-installation.json).
- [Post-install validation](../output/seven-loop-post-install-validation.json): all 137 installed hashes, all 82 graph source hashes, and all 12 installed skill validators pass.
- [Graphify report](../output/seven-loop-graph/GRAPH_REPORT.md): 608 nodes and 1,642 directed edges; 24 Python AST files and seven bounded semantic reference extractions. The other 51 files have provenance/link coverage. The report records 28 unresolved references, one symbol-ID collision, and 100 collapsed parallel edges; this is not complete semantic coverage.

Earlier lifecycle and individual author reports remain historical evidence. Their earlier counts and fingerprints are superseded by the final-source and installation records linked here. The repository's unrelated application changes were not part of this package work.

## Remaining operational boundaries

| Boundary | What is still required for a particular product |
| --- | --- |
| Always-on execution | The local scheduler actually dispatches due work while running and has a finite foreground service mode. No OS service, hosted daemon or recurring Codex automation was activated. Choose and validate the host lifecycle for the actual product. |
| Help beyond the workspace | Local inbox delivery is implemented. External recipient delivery, authenticated acknowledgment and escalation ownership need a configured transport and authorization. |
| Provider spending | Dispatch counts, elapsed-time ceilings and reservations are enforced locally. Provider dollar/token accounting and cross-host aggregate budgets need actual provider metering and reconciliation. |
| State migration | Reviewed same-engine, limits-only migration is implemented with a durable before/after journal and crash reconciliation. Arbitrary schema or engine migration is not supported. |
| Unknown workers | Uncertain cleanup/crash states retain reservations and block duplicate work. Recovery requires verified reconciliation; there is no automatic takeover based only on age or PID. |
| Authority and evidence | Artifact hashes and named actors bind records, but are not authenticated identities or a security boundary against someone who controls the local store. Product-specific verification and permission checks remain necessary. |
| Release and deployment | The portable legacy cycle lane reports release blocked. No automatic release compatibility, provider provisioning, payment flow or deployed smoke/rollback proof is claimed. A product needs its exact authorized release adapter and current live evidence. |
| Business outcome | The conductor can coordinate business work. Customer demand, acquisition, payment correctness and approved legal material require their own product evidence. |

## Use the updated skills

Use `$product-lifecycle-loop` as the reusable entrypoint with the actual product outcome and repository context. It selects the relevant owners; the individual loops can also be invoked within their documented scope. The preferred build owner remains `codex-product-build-loop`; the two legacy cycle owners are alternatives.

Installation was verified on disk. A task's loaded skill catalog may need a fresh task or an explicit installed `SKILL.md` reference to pick up the update. No product goal, recurring schedule, deployment or external message was started by this enhancement work.
