---
name: product-lifecycle-loop
description: Coordinate a product from discovery through delivery, operations, and business development with explicit goal acceptance, durable progress, failure diagnosis, bounded repair, help requests, and verified resumption. Use for an integrated idea-to-live plan, lifecycle review, or sustained product improvement using available personal and Codex skills. Route standalone feature, audit, document, or deployment work directly to its specialist unless explicitly invoked.
metadata:
  version: "1.1.0"
  short-description: One product lifecycle across your available skills
---

# Product Lifecycle Loop

## Fleet binding

Read [fleet-binding.md](fleet-binding.md) before scheduling or resuming work. Registry validation is an admission control, not a report-only check.

Turn a product goal into complete, verified work and a traceable next decision.
This is the lifecycle conductor. `codex-product-build-loop` is the preferred
delivery owner; other specialists own their domains. This skill provides routing
and local progress, scheduling and help-delivery helpers, not a deployment service,
billing integration, legal approval, hosted daemon or independently enforced
security boundary. Its repair
loop continues toward the full accepted goal within actual authority and resource
limits; needing help does not mean abandoning the goal.

**Words are Spells.** Use words as precise operational claims: distinguish a
proposal, implementation, executed check, proven outcome, and sustained result.

## Start from the requested outcome

1. Establish the target product or repository, requested outcome, current stage,
   scope, acceptance criteria, constraints, and authorization already given.
   For skill-authoring requests, build the skill; do not start a product cycle in
   the host repository. For raw ideas, work without inventing a repository.
2. Read applicable repository instructions and current state. Preserve unrelated
   user changes. Use Graphify before planning or changing repository behavior;
   verify graph findings in current source and refresh the changed surface after
   meaningful edits. If unavailable, record a source-and-test trace and the gap.
3. Choose the mode below and the smallest complete work unit that satisfies the
   request. An existing product may enter at any stage. Carry a specified larger
   outcome through multiple work units; a cycle boundary does not shrink scope.
4. Resolve only the specialist owners needed for this work using
   [skill-resolution.md](references/skill-resolution.md), then read their actual
   `SKILL.md` files. Do not load the whole catalog into every cycle.
5. Reuse existing vision, backlog, evidence, release policy, and state artifacts.
   Map their locations in the run record; do not establish a competing authority
   or overwrite an existing schema. Use [run-contract.md](references/run-contract.md)
   for material work and delegated handoffs.
6. Define the end-goal acceptance conditions separately from this cycle's work.
   Map every mandatory condition to tasks and evidence, including integrated
   journeys and live/business outcomes when they are part of the user's goal.
   For multi-cycle, failure-prone or resumed work, read
   [recovery-and-help.md](references/recovery-and-help.md) and use the existing
   durable tracker or the supplied progress helper. Do not create a second tracker
   when the project already has an adequate one.

| Mode | Behavior |
|---|---|
| Review / plan | Inspect, correct the map, identify gaps, and produce the requested plan. Do not fix product findings unless requested. |
| Build / enhance | Deliver and verify the requested complete behavior. Use a bounded work unit, then continue if the accepted outcome needs more work. |
| Verify | Exercise the specified boundaries and report evidence. Apply fixes only when authorized by the task. |
| Release / operate | Prepare concrete evidence and action details; perform authorized actions against the verified target. Apply the release contract below. |
| Business | Develop the commercial outcome using the business playbooks and applicable delivery or research owners. |

Missing optional preferences allow stated, reversible assumptions. Missing facts
that determine product intent, authorization, data use, or an irreversible action
remain open decisions. Continue independent useful work while awaiting them.

## One conductor, conditional specialists

Use [lifecycle-map.md](references/lifecycle-map.md) for phase ownership, outputs,
entry criteria, cross-cutting skills, and corrections to older skill names.
Use [specialist-contract.md](references/specialist-contract.md) when strengthening
or integrating an individual owner, including its failure/help/resume tests.

- Prefer `codex-product-build-loop` for a delivery slice. Do not start the full
  `product-loop` or `agentic-product-loop` inside this conductor: those are
  alternative cycle owners with different state and runner contracts. If the
  user chooses one, hand it the outer cycle and stop this conductor's cycle
  ownership. Do not recursively invoke each other.
- When a child skill calls for a different conductor, report that dependency and
  adapt the bounded domain handoff instead of starting another lifecycle loop.
- Reuse a specialist's existing composition: for example, `product-vision`
  already coordinates idea, market, and moat work. Do not rerun the same
  diligence under separate owners without a new question or changed evidence.
- Use `agentic-assurance-loop` for a requested broad assurance assessment;
  preserve its assessment-only scope unless remediation is already authorized.
- Delegate independent design, implementation, research, or verification work
  when useful. Assign one writer per mutable surface, disjoint file ownership,
  and an integration owner. `loop-fleet` applies to a requested persistent fleet;
  ordinary subagent collaboration does not require provisioning one.
- A missing skill parks only work requiring its capability. A candidate with a
  similar name is an alternative to assess, not proof of equivalent behavior.
  Unrelated skills never become mandatory admission gates.
- Before parking a repairable capability gap, inspect the required outcome,
  actual tools, local source/docs and viable equivalent routes. Diagnose and
  repair within authorized scope, or prepare a precise help request and resume
  condition. A named skill's absence alone is not proof the work is impossible.
- Use actual Codex tools for supported operations. Skill files instruct an
  agent; they are not callable functions or proof that a connector is available.

## The working cycle

`Discover → define → design → prioritize → build → verify → decide → deliver → observe → learn`

The cycle has feedback paths, not a single pass. A failed verification returns to
the affected design or build boundary; a release gap returns to the responsible
owner; real usage and business evidence update the next priority.
The end-goal contract survives all of these transitions. Do not remove a failing
acceptance condition, relabel a mandatory item optional, or narrow the requested
outcome just to finish a cycle.

1. **Discover and define:** establish the customer, problem, evidence, proposed
   value, success measure, non-goals, commercial assumptions, and constraints.
   Research assumptions when needed; label hypotheses and cite current sources.
2. **Design and prioritize:** trace dependencies; select the highest-value
   admissible work; record contracts, UX, data, costs, risk, and verification.
   Security, privacy, accessibility, reliability, and operations begin here and
   remain active during implementation. They are not late cleanup phases.
3. **Build and verify:** deliver a full slice through real boundaries, including
   permission, failure, persistence, and user interaction where applicable.
   Run checks proportional to the changed risk. Test rendered UI in a verified
   browser/runtime when behavior or layout is affected. Inspect review findings,
   fix authorized defects, and rerun the affected checks.
4. **Decide and deliver:** separate code release, agent behavior promotion,
   schema migration, deployment, live validation, and business activation.
   Use the release contract; never turn local green into production readiness.
5. **Observe and learn:** compare actual outcomes with success thresholds and
   costs. Create actionable backlog items from failures or missing evidence.
   Record repository lessons within scope; update personal memory or installed
   skills only when the user explicitly asks for those changes.

## Diagnose, repair, get help, and resume

For every material failure, use [recovery-and-help.md](references/recovery-and-help.md):

1. Preserve the failed oracle, current subject, effect state, and failure signature.
2. Classify the cause and choose a discriminating diagnostic or a justified repair.
3. Use available specialists/tools and independent review within the current scope.
4. Reproduce and repair, then rerun the failed boundary and affected integration.
5. If blocked by missing input, authority, capability or an exhausted repair budget,
   issue a targeted help packet, persist its wake condition, and work on independent
   tasks. Do not repeat the same request or retry an unchanged failure indefinitely.
6. Treat replies as data to revalidate. Reconcile uncertain effects and invalidate
   stale proof before resuming. Keep cumulative attempts across task restarts.
7. After a successful slice, select the next unmet goal condition. Finish only
   after final goal-level verification, or hand back an explicit waiting/stopped
   state with the exact help/continuation needed.

Self-sufficiency includes getting help and knowing when an action requires another
authority. It does not include inventing approval, using unapproved credentials,
changing active gates to pass, or promising eventual completion despite an
unavailable dependency, revoked authority, or enforced resource limit.

For monetization, acquisition, lifecycle engagement, and legal/privacy work,
read [business-playbooks.md](references/business-playbooks.md). Start business
discovery in the first cycle; actual commercial activation has its own gates.

## Release and recovery contract

Read [release-and-operations.md](references/release-and-operations.md) before a
release decision, production change, continuous run, or automatic recovery.

- Readiness and authorization are separate. A GO result does not grant authority.
  Prior explicit authorization remains valid within its stated target, scope,
  limits, and validity; do not ask again just because a specialist mentions a
  checkpoint. A policy file, elapsed veto window, or generated approval file
  cannot manufacture missing authorization.
- Bind every release check to the actual source/artifact, environment, project,
  configuration, and relevant behavior/data versions. Invalidate affected
  evidence when any of them changes. Keep local, staged, authenticated-live,
  provider, rollback/restore, and sustained evidence distinct.
- The existing `release-governor` can be the readiness owner only after its
  implementation and adapters satisfy the release contract. Legacy automatic
  helpers listed in the release reference are compatibility-blocked. Do not
  execute them or treat their generated evidence as trusted until corrected
  and independently verified. Use an available reviewed provider workflow for
  an authorized manual release; label its decision as human/agent reviewed,
  not a mechanical governor pass.
- Test rollback or compensation at the relevant boundary. Forward deployment
  is not reversal proof; restoring an app alias does not restore database state
  or reverse a charge. An attempted rollback is not a successful recovery.
- Stop dependent external actions when required proof, authority, or target
  identity is missing. Complete the concrete reviewable preparation first,
  explain the exact missing requirement, and continue independent work.

## Continuity and completion

For actual local scheduled cycles, inbox delivery, cumulative dispatch/time
reservations and reviewed progress-limit migration, read
[local-runtime.md](references/local-runtime.md). Use the pinned portable cycle
adapter and preserve parent budgets across configuration changes. These local
controls do not establish provider spending limits or hosted availability.

A skill cannot keep working after its task ends. For an explicit request to
monitor, repeat, follow up, or run later, use the available Codex automation tool.
Persist the product target, finite per-run work, budget/stop conditions, and
evidence locations. A scheduled prompt is not a daemon, lock, enforced budget,
approval system, or guarantee of immediate rollback. Verify those separately
when unattended external execution needs them. Respect stop/revocation signals.

At handoff, state the result for the requested scope, what changed, the checks
actually run, remaining gaps, and the next decision if one remains. Use `PASS`,
`PARTIAL`, or `BLOCKED` for work; `GO`, `NO_GO`, or `ESCALATE` only for a named
readiness decision. Keep deployment/recovery outcomes separate. Do not count a
missing or inapplicable check as a pass. Report **cycle result** and **end-goal
result** separately when they differ. A waiting required task means the goal is
unfinished, even if a report or another task is complete. A helper's
`READY_FOR_GOAL_REVIEW` requires the final integrated review; it is not a release
verdict or proof of production readiness. See [run-contract.md](references/run-contract.md).

For changes to this conductor, run the affected inventory/progress helper tests, the installed
skill-creator validator, and the independent scenarios in
[evals/scenarios.json](evals/scenarios.json). Structural validation is not proof
of behavior; record which scenarios were actually exercised.
