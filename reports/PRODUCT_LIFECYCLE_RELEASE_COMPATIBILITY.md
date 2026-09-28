# Product lifecycle release compatibility review

Date: 2026-09-12

Decision: **Do not use the inspected legacy release scripts as automatic execution adapters for the new lifecycle conductor.** Keep their output advisory until the findings below are repaired and the relevant behavior tests pass. A lifecycle readiness report must not become a replacement release authority.

This is a source review. No provider command, release, migration, production probe, legacy deployment script, or exploit was executed. Findings marked source-confirmed describe inspected control flow or conflicting instructions; they do not claim a reproduced production incident. Proposed tests below were not run during this review. Global skills were not changed.

## Recommended composition

Use `product-lifecycle-loop` as the one user-facing lifecycle entry point. It owns intake, stage selection, capability routing, dependencies, and consolidated evidence. Select exactly one engineering cycle owner, normally `codex-product-build-loop` for scoped Codex work. Treat `product-loop` and `agentic-product-loop` as alternative legacy engines requiring their own compatible prerequisites, not additional nested cycles.

Specialists own their domain methods. `product-vision` already composes `market-sizing`, `moat-reviewer`, and `idea-reviewer`; the conductor should not invoke the same diligence twice. `agentic-assurance-loop` owns broad assurance and defaults to assessment, so remediation needs the authorization already supplied by the task. `loop-fleet` is a separate legacy execution coordinator; ordinary bounded read-only subagents do not require starting the fleet.

The call graph must have no back edge from a selected child engine to the lifecycle conductor. A child returns a scoped result and evidence references, not a new top-level loop. The conductor must not invent production authority, approve itself, change a release policy to obtain a pass, or infer authorization from tool availability, a local report, a deadline, or a script exit code.

## Findings

### PLC-REL-001 — Contradictory release authority across owners

Priority: P1. State: source-confirmed instruction conflict. Execution verification: not run.

`product-loop` says the cited child skill wins when instructions conflict, then routes GO through unattended merge/tag mechanics. `release-governor` says it replaces the human token. However, `ship-release` explicitly forbids unattended execution, `migration-safety` explicitly forbids it, and `agent-release` requires human approval bound to the GA bundle hash. Combining their names does not resolve the conflicting contracts.

Sources:

- [product-loop child precedence](C:/Users/vijay/.agents/skills/product-loop/SKILL.md:13), and [GO execution routing](C:/Users/vijay/.agents/skills/product-loop/SKILL.md:468).
- [release-governor token replacement](C:/Users/vijay/.agents/skills/release-governor/SKILL.md:8).
- [ship-release unattended prohibition](C:/Users/vijay/.agents/skills/ship-release/SKILL.md:12).
- [migration-safety unattended prohibition](C:/Users/vijay/.agents/skills/migration-safety/SKILL.md:8).
- [agent-release hash-bound GA approval](C:/Users/vijay/.agents/skills/agent-release/SKILL.md:78), and [inherited never-unattended GA rule](C:/Users/vijay/.agents/skills/agent-release/SKILL.md:227).

Treatment: resolve the owner contracts explicitly before integration. Current platform instructions and the user's actual authorization remain controlling. Prepare all authorized local work and a concrete release packet without treating a skill's permission claim as user authorization.

### PLC-REL-002 — Dry runs and forward deployments generate false rollback proof

Priority: P1. State: source-confirmed control-flow defect. Execution verification: not run.

The successful deployment branch calls `emit_rollback_evidence(..., executed=True, result="success")` even for a dry run and even when no rollback ran. The comment explicitly treats a forward promotion as proof of its reversal. The resulting `rollback.json` is intended for a downstream release gate that requires an actually executed reversal. A forward operation cannot establish that the reverse operation restores service or data.

Sources: [deploy.py forward/dry-run success emits executed reversal](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:259), [dry-run smoke is skipped](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:239), [documented forward-flip proof claim](C:/Users/vijay/.agents/skills/deploy-provision/SKILL.md:27), and [governor executed rollback requirement](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:130).

Treatment: dry-run records remain planned/not-executed. Forward deployment records and reversal drill records must have separate types. Emit reversal proof only after performing the named reversal and verifying the restored artifact, target, and required journeys in an authorized rehearsal environment.

### PLC-REL-003 — Missing smoke and failed rollback receive misleading terminal states

Priority: P1. State: source-confirmed control-flow defect. Execution verification: not run.

Smoke defaults to `SKIPPED`; when no smoke script or probes are provided, execution reaches the success branch. On an actual smoke failure, the program records `ROLLED-BACK` and prints that it reverted even when `rollback()` returns `ok=False`. Therefore a successful exit can omit required live health proof, and a rollback status can overstate recovery.

Sources: [optional smoke branch](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:235), [failed rollback still reported as rolled back](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:249), [rollback can return false](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:147), and [missing smoke script is accepted by the caller](C:/Users/vijay/.agents/skills/release-governor/scripts/release_phase.py:168).

Treatment: live execution requires a configured, executed, passing smoke contract. Separate `DEPLOYED_VERIFIED`, `SMOKE_FAILED`, `ROLLBACK_ATTEMPTED`, `ROLLED_BACK_VERIFIED`, and `RECOVERY_FAILED`. A recovery failure must retain the unknown/current live state and the required incident action.

### PLC-REL-004 — Evidence adapters can relabel old or incomplete evidence with the requested hash

Priority: P1. State: source-confirmed evidence provenance defect. Execution verification: not run.

The metrics parser prefers matching rows but falls back to the most recent verdict in the whole file. The emitter then stamps that verdict with the requested release hash. Security and rollback parsers similarly emit the caller's hash without checking that the source record names it. The rollback parser also defaults the result to success if `executed` is true and no result is present. Thus a well-formed normalized record can claim more freshness or success than its source supports.

Sources: [metrics fallback to unrelated rows](C:/Users/vijay/.agents/skills/release-governor/scripts/evidence_adapters.py:79), [eval emitter caller hash](C:/Users/vijay/.agents/skills/release-governor/scripts/evidence_adapters.py:71), [security parser restamps source](C:/Users/vijay/.agents/skills/release-governor/scripts/evidence_adapters.py:116), and [rollback parser restamps/defaults success](C:/Users/vijay/.agents/skills/release-governor/scripts/evidence_adapters.py:146).

Treatment: parse and validate the source identity, environment, producer, exact full artifact revision, outcome, and evidence timestamp; preserve them without substitution. Missing fields remain missing. Evidence for a predecessor is not relabeled as evidence for a successor. Reusable mechanism-level rollback evidence needs an explicit compatibility rule rather than a changed hash.

### PLC-REL-005 — Local approval JSON and elapsed veto bypass fresh gate evaluation

Priority: P1. State: source-confirmed authorization validation gap. Execution verification: not run.

`gate_governor()` accepts `<hash>.approved.json` before checking the ordinary verdict, requiring only matching hash and `authorized=true`. The inspected function does not validate issuer, expiry, policy digest, target, action, revocation, or current gates. `cmd_resume()` creates this approval record after a stored veto deadline passes and directly calls deployment without re-running the governor. A stale or revoked release decision can therefore be accepted by this code path if these files are supplied to it. This is a source-level finding; no claim is made about deployed filesystem access controls.

Sources: [approval JSON takes precedence](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:56), and [deadline creates approval and directly deploys](C:/Users/vijay/.agents/skills/release-governor/scripts/release_phase.py:276).

Treatment: retain authorization as a separately validated, scoped artifact from the approved authority. Recheck all applicable gates, current target, policy revision, STOP/holds, and evidence expiry immediately before an effect. Elapsed time cannot create new user authorization. A prior explicit bounded authorization remains usable only while its scope and conditions still match.

### PLC-REL-006 — Classifier allows caller override and incomplete path coverage

Priority: P1. State: source-confirmed classifier weakness and contract conflict. Execution verification: not run.

`classify()` returns a recognized `declared_class` before evaluating changed paths. Otherwise it selects the highest class matching any path, without requiring every changed path to match a rule. A classified documentation path can therefore coexist with an unmatched sensitive path while the whole change receives the documentation class. The CLI exposes the override. Separately, product-loop says unclassified changes produce `NO-GO(classification-missing)`, while the governor can return `ESCALATE` when classification alone fails.

Sources: [classifier override and any-path matching](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:200), [CLI declared class override](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:289), [unclassified escalation](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:241), and [product-loop unclassified NO-GO contract](C:/Users/vijay/.agents/skills/product-loop/SKILL.md:427).

Treatment: derive the complete changed set from the verified repository/artifact, classify every relevant path or semantic surface, and fail closed on unmatched surfaces. A caller-supplied class may add restriction; it must not lower derived risk. Use one agreed decision contract.

### PLC-REL-007 — Missing limits and incomplete health evidence can pass gates

Priority: P1. State: source-confirmed fail-open validation. Execution verification: not run.

The release-rate gate passes when both the rate ledger and configured ceiling are absent. The oversight gate accepts an empty JSON object as healthy because absent anomaly/drift fields are falsey. Hash matching also accepts matching prefixes as short as seven characters rather than full artifact identity. These behaviors are weaker than the declared missing-evidence and exact-hash contracts.

Sources: [missing release ceiling passes](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:168), [missing oversight fields appear healthy](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:187), and [prefix hash matching](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:85).

Treatment: require typed, complete limit and oversight records for unattended eligibility; validate complete hashes, scope, producer, and expiry. `UNKNOWN`, absent, malformed, stale, and unconfigured are distinct from a passing control.

### PLC-REL-008 — Live pointer acquisition and artifact identity are insufficiently verified

Priority: P1. State: source-confirmed preflight gap. Execution verification: not run.

The current-pointer command is optional and a nonzero lookup result does not stop deployment. A missing pointer remains empty. Deployment identity is taken from the last stdout line without verifying the associated source hash or provider project. Promotion is optional. The sample deployment command deploys the existing prebuilt output and does not bind it to the hash supplied to the script. A hash recorded in an audit row is not proof that the provider served that artifact.

Sources: [pointer lookup and deployment output parsing](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:105), [optional promotion](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:135), and [prebuilt command in policy template](C:/Users/vijay/.agents/skills/deploy-provision/assets/DEPLOY-POLICY.template.md:25).

Treatment: require exact account/project/environment, immutable artifact digest and source revision, verified previous pointer when rollback is promised, and provider-readback after promotion. Initial deployment without a predecessor needs its own explicit recovery contract.

### PLC-REL-009 — Packaged provider commands do not match the command executor

Priority: P2. State: source-confirmed command contract mismatch. Execution verification: not run.

The provider template uses `$VERCEL_TOKEN` and a shell pipeline (`| tail -1`). The executor invokes `subprocess.run(shlex.split(cmd), ...)` without a shell. This executor does not expand the environment variable or interpret the pipeline. The example therefore cannot be relied on as a proven portable provider adapter, including in the current Windows environment.

Sources: [executor argv invocation](C:/Users/vijay/.agents/skills/deploy-provision/scripts/deploy.py:42), and [template shell syntax](C:/Users/vijay/.agents/skills/deploy-provision/assets/DEPLOY-POLICY.template.md:24).

Treatment: use structured argv and explicit environment injection without printing secrets; consume machine-readable provider output. Do not repair by blindly enabling shell execution. Verify the exact provider/runtime contract in an authorized non-production environment.

### PLC-REL-010 — Claimed integrity controls exceed inspected implementation

Priority: P2. State: source-confirmed composition gap. Execution verification: not run.

Product-loop requires fleet leases with expiry and monotonically fenced writes. The fleet skill instead describes `flock` and a cooperative active marker, explicitly acknowledging that it cannot enforce exclusion against other processes. Product-loop also describes governance rows chained by prior hashes, while the inspected governor append function writes plain JSON blocks without generating or checking a prior-row hash. These must not be advertised as implemented tamper/fencing guarantees.

Sources: [fleet fencing requirement](C:/Users/vijay/.agents/skills/product-loop/SKILL.md:769), [fleet cooperative mechanism](C:/Users/vijay/.agents/skills/loop-fleet/SKILL.md:62), [governance chained row contract](C:/Users/vijay/.agents/skills/product-loop/SKILL.md:100), and [governor plain append](C:/Users/vijay/.agents/skills/release-governor/scripts/governor.py:269).

Treatment: report the current cooperative/append-only properties accurately. Enforced fencing and tamper evidence require implementation plus negative tests at the write boundary; wording alone is not enforcement.

### PLC-REL-011 — The legacy readiness guard is an inventory precheck, not run admission proof

Priority: P2. State: source-confirmed scope limitation. Execution verification: not run.

The v13 guard checks selected loop-file presence, some Git state, core-owner directory names, STOP, holds, and its reference digest. Its skill resolver checks only user `.codex/skills` and `.system` immediate children, missing workspace copies, `.agents/skills`, and plugin roots. It can emit `ready` without validating a running sandbox, active bundle, budget, hooks, complete command/evidence contracts, or provider authority. Its exit code is also zero for `init_required` and `hold_review_required`.

Sources: [limited installed-skill roots](C:/Users/vijay/.codex/skills/agentic-product-loop/scripts/loop_guard.py:71), [guard assessment](C:/Users/vijay/.codex/skills/agentic-product-loop/scripts/loop_guard.py:96), and [zero exit for non-ready states](C:/Users/vijay/.codex/skills/agentic-product-loop/scripts/loop_guard.py:203).

Treatment: a new capability resolver should inventory known roots, preserve provenance, detect duplicate-name drift, and distinguish available from selected, configured, exercised, and proven. The lifecycle conductor must not read a zero exit or `ready` from this guard as permission to run unattended.

## Lifecycle gaps to cover without duplicating specialist owners

The supplied phase map is useful as a routing map, but security, privacy, commercial assumptions, and recovery start during discovery and design. Business work cannot be postponed until after production if pricing, entitlements, data usage, consent, or promises affect architecture and user trust.

- **Commercial delivery:** pricing hypothesis, entitlement model, server-side enforcement, checkout/provider integration, webhook authentication and replay handling, invoicing/refunds/cancellation, reconciliation, and support ownership. Test-mode billing proof remains separate from live money movement.
- **GTM:** audience, positioning evidence, channel experiments, accessible landing journey, instrumentation, attribution limits, opt-in lifecycle communication, and bounded acquisition spend. Publishing campaigns, sending messages, or spending requires the user's existing authorization for those effects.
- **Legal/privacy documents:** source-backed data inventory, subprocessors, retention/deletion behavior, jurisdictions and audiences, versioned policy delivery, consent evidence where applicable, and review ownership. Draft legal documents are not legal approval or evidence of compliance.
- **Operations:** authenticated critical journeys, capacity and dependency limits, monitoring ownership, alerts with tested response, backups/restores, recovery drills, incident handling, cost limits, and update triggers.
- **Capability resolution:** distinguish a personal skill, plugin skill, system skill, tool, and suggested-but-unavailable capability. Exact names such as `claude-api`, `frontend-design`, or `verify` must not be assumed to be installed Codex skills merely because they appear in the original map. Use actual inventory and state alternatives explicitly.

## Useful behavior tests for a replacement adapter or conductor

Status for every item below: **proposed; not executed in this source review**. Use local temporary fixtures and fake effect adapters only to test control logic; such fixtures prove no provider behavior.

1. **No external effects from planning:** doctor/plan/readiness modes produce scoped findings while an effect callback remains uncalled, including when all evidence fixtures are green.
2. **No recursive orchestrators:** reject a routing graph containing lifecycle → engineering engine → lifecycle or more than one cycle owner for the same item.
3. **Missing capability stays explicit:** unavailable required owner blocks its capability; an unrelated optional visual skill does not block an API-only local change; duplicate differing skill names require explicit resolution.
4. **Dry-run purity:** simulated deployment never emits `executed=true`, updates release counters, or changes an active pointer.
5. **Mandatory smoke:** missing/empty probe configuration and missing smoke executor refuse live execution; optional passing probes cannot substitute for a missing required probe.
6. **Recovery honesty:** failed rollback yields `RECOVERY_FAILED`, records the attempted target, and never emits verified rollback evidence.
7. **Provenance preservation:** source evidence for hash A cannot become evidence for hash B; missing result does not become success; matching seven-character prefixes remain distinct full revisions.
8. **Authorization separation:** an arbitrary `authorized=true` file, elapsed deadline, old GO, revoked policy, or another project's approval cannot admit an effect. Prior valid user authorization should not generate repeated permission requests when unchanged and in scope.
9. **Execution-time revalidation:** changing STOP, hold, target, policy digest, artifact digest, evidence expiry, anomaly state, or release limit after planning prevents deployment.
10. **Complete classification:** a matched low-risk file plus an unmatched file is unclassified; a declared class cannot lower a sensitive derived class.
11. **Empty evidence fails closed:** `{}`, nulls, unreadable JSON, absent limits, empty scope, or missing full digest never produce healthy/eligible states.
12. **Exact served artifact:** a successful command returning the wrong project, wrong artifact, empty deployment ID, or missing predecessor cannot satisfy deployment/recovery proof.
13. **Resume safety:** a crash between effect and record finalization causes reconciliation using provider state, without silently reissuing a non-idempotent effect.
14. **Proof-state separation:** local tests and a public health route cannot satisfy authenticated-live, provider payment, backup restore, sustained monitoring, or legal review requirements.
15. **Native automation routing:** recurring work uses the supported app automation capability when requested, with bounded scope and meaningful-change notification intent; the skill itself does not invent an in-chat daemon.

## Scope and completion

Reviewed skill sources: `product-loop`, `agentic-product-loop`, workspace `codex-product-build-loop`, `loop-fleet`, `product-vision`, `release-governor`, `deploy-provision`, `ship-release`, `agent-release`, `migration-safety`, and workspace `agentic-assurance-loop`; selected composition, proof, guard, provider, governor, deployment, and evidence-adapter sources were also inspected.

This report completes a bounded compatibility review. The broader skill catalog, current provider configuration, deployed enforcement, production authorization, and hosted behavior require separate evidence. None of the legacy findings above was remediated by this review.
