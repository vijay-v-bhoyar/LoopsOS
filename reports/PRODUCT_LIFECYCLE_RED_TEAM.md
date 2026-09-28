# Product lifecycle adversarial review

Date: 2026-09-12. Scope: the original ten-file lifecycle package, selected installed loop owners, and inspected legacy release code. This is a baseline report for blue-team remediation in the current task. Later package edits can supersede the baseline locators below; they do not automatically close these findings.

**Verdict:** the baseline is a useful instruction conductor with honest release boundaries, but it does not establish autonomous progress to a whole-product goal. Its executable component inventories skills; it does not enforce completion, recovery, help resolution, or sustained operation. “No gaps” and guaranteed eventual completion cannot be established from a finite review. Missing user authority, unavailable providers, and impossible acceptance criteria can remain real terminal dependencies.

Evidence labels: **Observed execution** means the exact local function was called; **source-confirmed** means current source was inspected; **hypothesis** means the described operational trajectory has not been executed. Severity is impact if integrated into the intended unattended workflow, not evidence of an actual incident.

## Baseline identity and review method

Graph navigation used `output/product-lifecycle-graph/GRAPH_REPORT.md`, then current source checks. Its semantic edges are documentation relationships, not enforcement proof. The existing compatibility report was used as a lead; selected legacy locators were reread in current source. No personal memory files were used for this independent review.

Baseline SHA256:

- `skill-packages/product-lifecycle-loop/SKILL.md`: `ed0efeaa4baa91c95145fc6ee64bd5eb06c2e733c738877640d43cda808e7e3d`
- `references/run-contract.md`: `bb486afc78d28275401f5cae7b62682d257f12bf2ecce8e78fdc6325dff4f6ac`
- `references/skill-resolution.md`: `b38761ee96297c8389ba544f22699795285c979c9ddf9b2f8603e9a107bfff52`
- Installed `.agents/skills/release-governor/scripts/governor.py`: `31ebf3a43da36bc6be4c78c26e2f0e489be40561394be88e2ab0a5a9b36c25f3`
- Installed `.agents/skills/release-governor/scripts/evidence_adapters.py`: `304befdc9230a767be27fd63d5bbb9ce07d5d92dd2e436086b1738550cb27a0e`

## PLC-RT-001 — A completed slice can be mistaken for the completed goal

P1. Source-confirmed missing operational contract; premature termination is a hypothesis.

Evidence: baseline `SKILL.md:28-30` correctly says a cycle boundary does not shrink scope. `references/run-contract.md:13` records acceptance criteria, but `:86-88` defines PASS over “stated work scope” without a separately persisted goal predicate. The baseline has no explicit criterion IDs, required-set validation, or aggregation of child results into the original goal.

Trajectory: an agent narrows a subscription-launch request to “implement checkout,” receives a child PASS, and ends while cancellation, entitlements, provider reconciliation, and launch acceptance remain incomplete. Documentation tells it not to do this, but supplies no operational check to detect it.

Blue repair: preserve the original outcome with stable required criteria; record work-item results separately; require each applicable criterion's current evidence plus a final integration review. The mechanical state should mean “ready for goal review,” not independent proof of user satisfaction.

Oracle: one of three required criteria is verified; goal completion must reject. Removing/renaming the other criteria or redefining the goal inside a child result must not silently obtain completion. A legitimate user scope change must preserve a traceable prior version.

## PLC-RT-002 — Parking and asking for help have no complete lifecycle

P1. Source-confirmed contract gap; indefinite parking is a hypothesis.

Evidence: `references/run-contract.md:71` parks dependencies; `references/skill-resolution.md:28-39` resolves missing names and continues independent work. Neither baseline reference specifies a blocker owner, scoped help request, delivery state, response acceptance, wake condition, or expiry. The delivery owner's `.codex/skills/codex-product-build-loop/SKILL.md:136` allows one correction or stopping at a blocker.

Trajectory: an owner is unavailable; the task parks it and completes incidental work. Another run repeats “blocked” without investigating an equivalent capability, requesting the exact missing input, or detecting that the input arrived. A support request in draft form may also be mistaken for one actually sent.

Blue repair: classify the blocker; attempt local diagnosis and a relevant alternate capability within scope; create a bounded help packet with evidence, exact request, recipient/authority, response state, resume predicate and next check. Treat drafting, sending, answering and independently verifying the answer as different states. External messages still require explicit authorization.

Oracle: supplying the missing input wakes only the affected work; an irrelevant answer leaves it blocked; an unsent request cannot be “awaiting recipient”; a help response cannot grant extra side effects or turn its own success claim into proof.

## PLC-RT-003 — Dependency deadlock and goal-irrelevant churn are undetected

P1. Source-confirmed contract gap; trajectories are hypotheses.

Evidence: `references/run-contract.md:14,35-38,67-71` names selected work and dependencies, but has no dependency graph validation or “all required paths blocked” transition. The baseline cycle prioritizes work without a criterion-linked measure of remaining goal work.

Trajectory: billing waits for entitlement design while entitlement design waits for billing, or every required outcome waits for a decision and the agent keeps polishing unrelated documentation. Activity can continue indefinitely without advancing the requested result.

Blue repair: use a validated acyclic dependency model or identify strongly connected dependencies for explicit redesign; select runnable required work; stop discretionary churn when no required path can advance. Preserve genuine missing decisions rather than deleting dependencies to make work runnable.

Oracle: reject A→B→A and references to nonexistent work; surface all blocked critical paths; verify that completing unrelated optional work cannot satisfy a required criterion.

## PLC-RT-004 — Retry limits can reset across restarts and delegates

P1. Source-confirmed persistence gap; repeated spending is a hypothesis.

Evidence: `references/run-contract.md:22,80-82` asks for resource limits and a retry limit, but provides no durable aggregate attempt counter or failure identity. Legacy `product-loop/SKILL.md:549-550` retries parked environment/tooling items once every review, allowing a repeated unchanged blocker across many reviews despite a locally bounded retry.

Trajectory: each task or replacement specialist starts with “attempt one.” A persistent permission denial, bad migration, or unavailable provider consumes new time and tool calls on every run; child cost disappears from the parent's accounting.

Blue repair: persist attempts by work and stable failure signature; distinguish observation from effect retries; record a changed diagnostic hypothesis before another attempt; enforce cumulative run and goal limits with a reserved shutdown/recovery allowance. Unknown measured spend must not be represented as zero or unlimited. Runtime ceilings require actual host/provider enforcement.

Oracle: restart after two failed attempts and verify the third does not reset the counter; another worker cannot create a fresh item solely to evade the same limit; hitting a bound checkpoints and requests a scoped next decision rather than falsely completing the goal.

## PLC-RT-005 — Crash reconciliation is specified but not made executable

P1. Source-confirmed runtime gap; duplicate effects are a hypothesis.

Evidence: `references/run-contract.md:73-78` already correctly requires reconciliation and the same idempotency key; `references/release-and-operations.md:90-103` correctly distinguishes uncertain recovery. The baseline lacks an operation journal recording intent before an effect, operation identity, reconciliation evidence, and a gate preventing replay while outcome remains unknown.

Trajectory: the provider accepts an operation and the task crashes before recording success. The next run knows no operation ID because it was only going to store the response, and may create another logical operation or stop forever.

Blue repair: record scoped intent and stable logical operation key before dispatch; preserve unknown/in-flight states; reconcile actual provider state and verify result before unblocking dependent work. A local ledger can require this record but cannot prove the external provider or transaction was idempotent.

Oracle: simulate a lost response after an accepted effect; restart must select reconciliation and never dispatch a second effect. “Provider ready” for a different artifact or target must not settle the original operation.

## PLC-RT-006 — Help or self-repair can change the contract that judges the work

P1. Source-confirmed partial coverage; bypass trajectory is a hypothesis.

Evidence: `references/skill-resolution.md:34-38` prohibits picking fewer gates, and release reference `:45-48` requires independent proof to remove a compatibility block. Baseline run records capture owner hashes at `references/run-contract.md:16-17`; they do not define mandatory revalidation when the selected skill, completion oracle, or helper changes during work.

Trajectory: a specialist “fixes” the failing completion check or swaps an owner, reruns it, and reports green under changed criteria. A renamed or updated helper appears repaired without exercising the original adversarial case.

Blue repair: preserve acceptance/gate and selected-owner fingerprints for the active work; treat contract changes as separately reviewed work with authorization appropriate to scope; invalidate dependent evidence; rerun original failing and negative cases under an independent reviewer. A writable local hash is change detection, not tamper-resistant enforcement.

Oracle: modify a gate/skill during a run and verify the prior receipt is rejected; an updated compatibility-blocked helper remains blocked until explicit repair evidence is recorded; a helper answer cannot itself remove the block.

## PLC-RT-007 — Legacy classification can understate sensitive work

P1. Observed local pure-function execution; no release CLI or provider action executed. Corroborates the prior compatibility review.

Evidence: [governor.py](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:203) immediately returns an allowed declared class. At line 210 a single matching path is enough to choose a class even when another path is unmatched.

Executed cases:

| Fixture | Observed | Required oracle |
|---|---|---|
| `classify(['auth/permissions.py'], {'class_globs': {'L3': ['auth/**']}}, 'L0')` | `L0` | Derive L3 or reject the lower declaration |
| `classify(['README.md','auth/permissions.py'], {'class_globs': {'L0': ['**/*.md']}}, None)` | `L0` | Unclassified/high-risk handling for the unmatched path |

Trajectory: README changes conceal an unclassified security change, or a caller forces low risk. Blue repair: classify every changed path, preserve unmatched paths, and prevent declarations from lowering derived risk. Test exact mixed-path and downgrade cases through the eventual integration adapter as well as the pure function.

## PLC-RT-008 — Legacy evidence conversion and weak identity can promote stale evidence

P1. Prefix behavior observed in a pure function; conversion defects source-confirmed only. Corroborates the prior compatibility review.

Evidence: [governor.py](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:85) accepts a seven-character prefix without resolving it to a canonical full revision. Executed `_hash_matches({'hash':'abcdef0'}, 'abcdef01234567890123456789012345678901234')` returned `True`. This proves prefix acceptance, not a demonstrated pair of colliding repository commits.

Further current-source evidence: [evidence_adapters.py](C:/Users/vijay/.agents/skills/release-governor/scripts/evidence_adapters.py:98) falls back to another metrics row; line 130 stamps security counts with the caller hash without validating source identity; line 149 defaults a missing rollback result to success when executed is true. These file-writing adapters were not run.

Blue repair: strict source schema, full immutable subject identity, target, producer, expiry and explicit result; missing or mismatched fields reject. Preserve original evidence provenance. Oracle: records for A cannot become receipts for B; missing result cannot pass; a short unresolvable identity cannot satisfy an exact-artifact gate.

## PLC-RT-009 — Legacy decision API accepts no gates

P2. Observed pure-function defect; reachability limitation explicitly retained.

Evidence: [governor.py](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:241) computes `all(...)` on the supplied sequence without validating mandatory gate names. Executed `decide([], 'L0', {})` returned `GO`.

The inspected CLI beginning at line 305 always constructs the gate list, so this is **not a demonstrated current CLI bypass**. It is a latent defect if a replacement adapter reuses `decide` with a missing/filtered gate set, precisely the likely integration work required here.

Blue repair: require the exact applicable gate set, reject duplicates/unknowns/missing gates and empty scope before decision. Oracle: no gates, one omitted mandatory gate, and duplicate pass names all reject. Keep the current compatibility block until the actual integrated path has these negative tests.

## PLC-RT-010 — Corrupt release history can erase budget/cooldown evidence

P1. Source-confirmed; not executed.

Evidence: [evidence_adapters.py](C:/Users/vijay/.agents/skills/release-governor/scripts/evidence_adapters.py:208) skips corrupt ledger rows and then computes counts from remaining records. The comment says corruption must not silently zero the count, but the control flow does not enforce that. At line 225 unreadable prior freeze state returns false. [governor.py](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:187) also treats empty oversight objects as healthy.

Trajectory: a partial write, malformed timestamp, or overwritten freeze snapshot removes the evidence needed to enforce a release cap or incident stop, allowing later work to appear admissible.

Blue repair: malformed ledger/freeze/oversight input means unknown or blocked; retain last verified state; repair from independently verifiable events before resuming. Oracle: truncated ledger entry, corrupt freeze JSON, empty oversight object, and stale observation must never yield healthy/under-budget claims.

## Reproduction boundary

Four function calls above were executed by the bundled Python at `C:/Users/vijay/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` with `-B`. The inspected governor module was imported through `importlib.util.spec_from_file_location`; its CLI was not invoked. Inputs were in-memory fixtures. The module's top level imports standard-library modules and defines constants/classes/functions; no provider or subprocess effects occur at import. No installed skill files or bytecode were written. No network/provider call, deployment, rollback, migration, outgoing message, purchase, or automation was executed. Initial `python` and `py -3` attempts failed because those runtimes were unavailable; the bundled interpreter succeeded.

No full unattended run, kill/restart experiment against an external provider, concurrency stress, billing journey, sustained monitoring window, or production security boundary was tested. Baseline PLC-RT-001 through PLC-RT-006 require implementation plus adversarial integration verification; source prose alone cannot close them. The existing legacy compatibility block remains the correct integration boundary pending repairs and independent tests.
