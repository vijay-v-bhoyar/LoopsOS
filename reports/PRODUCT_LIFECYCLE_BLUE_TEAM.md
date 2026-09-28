# Lifecycle red/blue assessment and repair

Date: 2026-09-12. Target: the reusable `product-lifecycle-loop` skill package in
LoopsOS, under `codex/production-hardening`. Scope: skill orchestration, local
progress/help/recovery, selected legacy release boundaries, and individual-owner
enhancement plans. This is not a release assessment of the LoopsOS application.

## 1. Decision

The conductor now has an implemented local progress ledger and a full-goal repair
contract. It can preserve required work, identify the next eligible task, retain
failure history, request precise help, and revalidate before resuming. Codex must
still perform the actual work and final verification. The helper does not execute
workers, contact recipients, run continuously, authenticate evidence, or enforce
provider authority and spend.

Use it for bounded local product work after the validation recorded below. Do not
wire its exit code or `READY_FOR_GOAL_REVIEW` to deployment. Unattended external
execution remains unproven and the legacy release helpers remain compatibility-
blocked. No exceptions or new production authority were granted by this review.

## 2. Six assessment lenses

| Lens | Evidence-qualified decision |
|---|---|
| Beta readiness | Insufficient evidence for an external product beta; this assessment covers a local skill/helper |
| Architecture and operations | Local state implementation tested; scheduler, authenticated admission, distributed leases, incident service and provider enforcement remain outside the implementation |
| Adversarial failure | Baseline source review plus executed local negative probes; initial helper defects were sent back for repair and independent retest |
| Acquisition/value diligence | Valuation not assessable; no customer, revenue, ownership or transaction diligence performed |
| Category strategy/moat | Not assessed; reliable completion is a proposed value driver, not measured differentiation |
| Future resilience/autonomy | Evidence limited to tested local restart/help/invalidation cases; real host/provider changes and continuous operations need separate drills |

## 3. Scope and evidence

The prior inventory read metadata and hashes from 690 skill entrypoints; that is
not 690 deep audits. The individual-loop plan inspected 76 local source paths and
covers seven coordinating loops plus phase specialists and relevant alternatives.
Its owner-specific acceptance cases are proposed, not executed. The original
ten-file package and selected legacy code were red-reviewed; the enhanced package
adds a progress helper, its tests, and three operating references.

Evidence sources:

- [Baseline red findings](PRODUCT_LIFECYCLE_RED_TEAM.md), PLC-RT-001 through 010.
- [Legacy release compatibility](PRODUCT_LIFECYCLE_RELEASE_COMPATIBILITY.md), PLC-REL-001 through 011.
- [Individual owner plan](INDIVIDUAL_LOOP_STRENGTHENING_PLAN.md), exact variants, changes, dependencies and positive/negative acceptance cases.
- [Independent helper challenge](PRODUCT_LIFECYCLE_PROGRESS_REDCHECK.md), reproduced paths and final retest scope.
- [Local workflow artifacts](../output/product-lifecycle-goal-workflow/), actual fixture outputs, help response, checkpoint, receipts and final assertions.

No live deployment, charge, message, credential change, production migration or
scheduled controller was executed. Four isolated legacy governor function calls
were executed in this review; the legacy CLI and effectful workflows were not.
The original compatibility report's earlier source-only scope remains historical.

## 4. Twenty-layer coverage

| Layer | Applicability, evidence and remaining work |
|---|---|
| L01 Product/workflow | Applicable: required goal criteria, task coverage, dependencies and final review added; PLC-RT-001/003 |
| L02 UX/adoption | Applicable to handoff language/help: contract and fixture; product UI and accessibility not assessed |
| L03 Frontend | Not applicable to this CLI/skill change; no frontend changed |
| L04 API | Local CLI JSON boundaries tested; network API/authentication not implemented here |
| L05 Backend services | Local state/replay/revision/lock transitions tested; distributed execution absent |
| L06 Data | Local hashes, atomic persistence and invalidation tested; backup, retention and hostile-writer protection not established |
| L07 Identity | Producer/owner strings are claims; authenticated host identity remains required before external automation |
| L08 Authorization | Skill preserves authority boundaries; local receipts grant none; actual provider admission remains required |
| L09 Tenant isolation | Not applicable to the single-workspace helper; cross-tenant hosted use would need its own design/tests |
| L10 Agent orchestration | Goal, dependency, attempt, blocker/help and resume logic added; real scheduler/cancellation/fleet remain unproven |
| L11 Prompt/policy | Frozen plan/control/engine fingerprints and unchanged-oracle instructions added; arbitrary writer can rewrite all records |
| L12 Tool execution | Operation journal and reconciliation transitions tested locally; provider truth/idempotency not demonstrated |
| L13 Retrieval | No RAG change; retrieved help remains untrusted data; provider-specific retrieval tests not run |
| L14 File ingestion | Strict local JSON, size, path and hash checks tested; hostile concurrent filesystem replacement excluded |
| L15 Security | Scoped local boundary tests and legacy blockers; no broad dependency/egress/host security certification |
| L16 Observability | Durable attempts, failure fingerprints and current-attempt context; actual cost/latency/alert delivery not implemented |
| L17 Audit/compliance | Traceable local history and stable findings; no regulated audit or legally sufficient immutable store claimed |
| L18 Testing/evaluation | Unit, independent adversarial and executed fixture checks; written behavioral scenarios separately identified |
| L19 CI/CD/release | Source/global parity checked on installation; PLC-REL blockers remain before automatic legacy releases |
| L20 Operations/support | Help/recovery contract and local resume exercised; on-call, notifications, restore and continuous controller need real drills |

## 5. Findings and blue-team disposition

| Stable finding | Change / disposition | Residual proof needed |
|---|---|---|
| PLC-RT-001 | Full-goal criteria, coverage, frozen plan and separate final review added | Actual product outcomes still require the accepted oracle |
| PLC-RT-002 | Typed blockers, response pointers, revalidation and durable help/resume guidance added | Real message delivery, recipient availability and scheduler wake are not provided by the helper |
| PLC-RT-003 | Unknown dependencies/cycles/uncovered criteria rejected; only required eligible tasks proposed | Product decomposition correctness remains a reviewed judgment |
| PLC-RT-004 | Persistent aggregate/per-task attempts and failure-signature ceilings added | Host/provider cost, elapsed-time and child budgets need real enforcement |
| PLC-RT-005 | External intent/key, uncertain outcome and reconciliation transitions added | Actual provider readback, idempotency and compensation drills remain required |
| PLC-RT-006 | Plan/control/helper identity checks and reply-as-data rules added | No protection from an actor able to rewrite all state, artifacts and controls; no producer authentication |
| PLC-RT-007/008/009/010 | Legacy classification, evidence identity, empty-gate API and ledger weaknesses retained as open | Repair legacy implementation and prove its true entrypoints fail closed before removing compatibility block |
| PLC-PR-001 through 007 | Seven reproduced local helper defects corrected and independently retested | Closure applies to the recorded local transitions, not provider or host guarantees |

These are scoped mitigations, not blanket closure of the original operational
risks. An instruction or test at one boundary cannot establish another boundary.

## 6. Repair packages and individual loops

The complete per-owner packages are in the individual strengthening plan. The
shared minimum is: verified entry, accepted output, typed failure, precise help,
current-state resume, and original-goal closure. The new
[specialist contract](../skill-packages/product-lifecycle-loop/references/specialist-contract.md)
turns these into a common handoff and challenge set. Installations and source
variants were not indiscriminately rewritten.

| Coordinator | Next enhancement |
|---|---|
| product-lifecycle-loop | Connect tested local state to a real host adapter, help dispatcher and reviewed state migration when needed |
| codex-product-build-loop | Return failures to bounded diagnosis/repair and parent acceptance; retain repeated-failure state across slices |
| product-loop | Repair actual runner admission, resource accounting, parked-item behavior and release integration before unattended use |
| agentic-product-loop | Reconcile wrapper/runner policy, canonical artifact identity and fail-closed guard behavior |
| agentic-assurance-loop | Tie findings to exact reproductions, repairs and independent closure; maintain unknown evidence across runs |
| product-vision | Convert unknown assumptions into owned experiments/decisions, preserving unaffected design progress |
| loop-fleet | Prove leases/fencing, aggregate budgets, crash/STOP handling, semantic conflict detection and integrated acceptance |

Release P0 packages retain their PLC-REL IDs. Required sequence: strict evidence
schemas and current identity; complete classification; authority and budget
admission; provider operation/readback; mandatory smoke; truthful rollback/
compensation; independent negative and actual-environment tests. A dry run must
never mint executed recovery proof. A failed rollback must stay failed/unknown.

## 7. Dependency order

1. Complete and validate local goal/help/recovery state and its independent tests.
2. Integrate the selected delivery owner and domain adapters against this contract.
3. Implement exact host identity/authority, aggregate resource limits, cancellation,
   leases and a requested scheduler before continuous external execution.
4. Repair compatibility-blocked legacy release paths or use a separately reviewed,
   authorized provider workflow with explicit evidence.
5. Exercise real authenticated journeys, provider ambiguity, migration/restore,
   alert delivery and help/incident response in the intended environment.
6. Prove billing, rights and acquisition outcomes when the product goal includes
   business activation. Introduce fleet throughput after solo reliability.

These are dependency buckets, not promised dates or staffed assignments. Domain
skills are proposed owners; a real operator/support recipient must be identified
by the product using the loop.

## 8. Executed verification

Final helper SHA256:
`99fd31d8ed03d9db5bd6ecc1a171921bf57d047fa4707748982384bf39a63aa3`.

| Test | Control / action | Actual result and evidence | Verifier / scope |
|---|---|---|---|
| PLC-V01 | Complete inventory and progress unit suites | **52/52 PASS**, exit 0; [execution log](../output/product-lifecycle-recovery-unit-tests.log) | Integration owner; bundled Python, Windows local fixtures |
| PLC-V02 | Independent malformed-state and adversarial transitions, PLC-PR-001 through 007 plus liveness controls | **10/10 PASS**, exit 0; [red-check report](PRODUCT_LIFECYCLE_PROGRESS_REDCHECK.md) and executable harness | Separate red-team agent; isolated local files/receipts, no provider |
| PLC-V03 | Full local goal: inventory, missing preference, checkpoint/reload, later reply, revalidation, handoff and final integrated assertion | **PASS**, both phase processes exit 0, final revision 12, five starts; [process evidence](../output/product-lifecycle-goal-workflow/final-frozen-repeat/process-result.json) | Fresh-context workflow agent; fictional local documentation goal, simulated owner reply; integration owner reread actual final artifacts |
| PLC-V04 | Official Codex skill-creator structural validator | **PASS** for source and installed package | Installed validator; structure only |
| PLC-V05 | Internal references, JSON/YAML and unique scenario IDs | **PASS**, 15 files, no broken package references; [validation record](../output/product-lifecycle-recovery-validation.json) | Integration owner; actual package bytes |
| PLC-V06 | Installed baseline drift check, backup, scoped update and SHA256 parity | **PASS**, all 15 installed files match source; [manifest](../output/product-lifecycle-installation.json) | Integration owner; old ten-file installation preserved in workspace backup |
| PLC-V07 | Scoped Graphify refresh and source-integrity checks | **PASS**, 15 files, 252 nodes, 648 exported directed edges, no source drift or dangling endpoints; [graph report](../output/product-lifecycle-graph/GRAPH_REPORT.md) | Graph worker and semantic extraction; four Python AST files and eleven semantic artifacts, repository root graph unchanged |

Graph scope is source structure and documented contracts, not operational proof.
One parallel unittest import relation collapses in the directed export and remains
in raw extraction. The report retains the exact-AST explanation for import-cycle
projection artifacts; no code cycle is inferred from those source relationships.

The workflow preserved its initial missing input and later fixture reply as
separate artifacts. A previously completed experiment used five starts; an
intermediate experiment was deliberately superseded after two starts when the
helper changed. Both histories remain intact. The final five-start experiment is
a separate regression run, not a migration or budget reset of an unfinished goal.

The package contains 15 behavioral scenarios and eight trigger cases. Written
cases without a separate execution record remain not run. Earlier five written
walkthroughs concern the baseline and do not prove this new executable helper.

## 9. Release, exceptions and recovery

There is no product-production GO from this work. Local review readiness cannot
authorize deployment. Compatibility blocks, wrong/stale identity, absent mandatory
proof, revoked authority and unknown external effects remain stop conditions for
dependent actions. Continue useful authorized independent work, then checkpoint a
precise waiting state if an actual dependency remains.

The helper cannot reset its frozen budget or migrate its own plan. Preserve the
old ledger for any reviewed successor; no silent reset or invented budget grant.
A stranded lock or corrupt record requires inspection. The host must handle real
process termination, credentials, billing caps and operational recovery reserves.

## 10. Value and future resilience

Measure completion against the original goal, including failures, support effort
and real costs. Useful next comparison: this conductor versus the same authorized
tools with a simple checklist on equivalent tasks and unchanged acceptance. No
valuation, market superiority or guaranteed eventual completion is asserted.

## 11. Change since baseline

The former package supplied routing and inventory. This update adds executable
local progress, bounded recovery, explicit help/revalidation, dependency checks,
current evidence checks and final-goal review semantics. The red team challenged
the new implementation before activation and routed reproduced defects back to
the blue team. Legacy scripts, product application files and personal memory
were not modified by this update.

## 12. Continuation

This skill-enhancement task delivers the central repair and the individual-loop
plan. Remaining runtime/provider work has explicit dependencies above; it is not
silently declared complete. A product adopting the loop supplies its actual goal,
workspace, accepted criteria, existing authority and available environment. The
conductor then pursues required work, repairs within scope, asks for only missing
help, revalidates the response, and continues until the accepted outcome is
verified or an actionable dependency requires another actor.
