---
name: loop-fleet
description: Coordinate bounded parallel product work after the solo loop is proven. Use for atomic admission, shared contract and state reservations, cumulative budgets, cancellation, and serial integrated acceptance. A local cooperating-process coordinator, not provider billing authority or a deployment engine.
---

# Loop Fleet

## Fleet binding

Read [fleet-binding.md](fleet-binding.md) before admitting concurrent work or recording integrated completion.

Use parallel workers for independent work with a stable solo engine. Measure solo failure and recovery rates before increasing concurrency; a fixed cycle count does not prove readiness. Start with two workers and raise the ceiling only when integrated outcomes justify it.

Use `scripts/fleet_runtime.py`. Read [runtime-contract.md](references/runtime-contract.md) before creating a fleet. The former `fleet.sh` coordinator and its destructive cleanup mode are disabled. The old partitioner remains a candidate-generation library; its CLI cannot grant admission. Filename predictions alone do not establish independence.

## Run the fleet

1. Freeze the parent goal, product/target/revision/configuration identity, acceptance criteria, dependency order, executable invocations and oracle. Select one cumulative parent budget owner. If a parent schedules a fleet, reserve the entire fleet ceiling there; child accounting subdivides it.
2. Prepare bounded, isolated worker directories inside the declared workspace. Preserve branches and unmerged artifacts. Resolve read/write claims for files, APIs/contracts and shared state. Unknown surfaces use exclusive `*` admission. Delegate genuinely independent work. The parent must verify predecessor artifacts before admitting dependent work.
3. Initialize one durable database, acquire its coordinator lease, and run workers using the same owner/fence. `run` atomically reserves concurrency, worst-case credits and resource ownership before launching, then hashes changed files and outputs. Creating a second database cannot renew the parent budget.
4. Cancellation is durable: `cancel` stops further admission; active runners observe it, terminate owned processes and wait. Windows runners use a Job object assigned before dispatch, with descendant termination on Job close. Do not substitute `taskkill`: it failed in host verification. POSIX process groups are implemented but were not exercised in that Windows run.
5. Integrate serially with the exact expected job set, a nonempty final verification command, parent criteria, output artifacts and its own reservation. Output hashes are rechecked before integration. Empty commands, failed workers, stale outputs or failed final checks prevent local acceptance. Authorized git merge commands can be explicit serial steps in an isolated integration checkout. No automatic branch deletion, force-cleanup, rebase or promotion is supplied.
6. Return the receipt and unmet parent criteria. `INTEGRATED_LOCALLY` means the recorded local acceptance command passed for those artifacts. Recheck exact git identity and current artifacts at the parent acceptance/release boundary.

## Recovery and help

Budget charges survive completion, failure and cancellation; no child-reported cost reduces them. Credits and wall time are enforced locally, not live provider money. Enforce provider spending through the authorized host/provider adapter before using paid tools.

An expired lease with running work is unresolved. Do not steal it, delete the database, kill a persisted PID or discard worktrees. Preserve state, collect process/operation evidence, and ask the parent recovery owner for reviewed migration or reconciliation. There is no automatic unsafe takeover. A lease may be replaced only when no recorded work is running; old fencing tokens cannot write afterward.

If admission fails, act on the reason: wait for conflicting work, serialize unknown resources, repair claims, obtain budget authority, or diagnose unresolved execution. Never change task IDs, databases or owners to evade a limit.

## Scope of proof

SQLite serializes cooperating processes sharing a local database. It is not a distributed lock, a secure boundary against a hostile writer, filesystem sandbox, semantic contract detector, or release gate. Actual file changes are checked inside each bounded worker directory (64 MiB snapshot cap); external writes and semantic API effects require host containment and domain verification. Parent acceptance owns goal coverage, dependency evidence, authenticated authority, billing and hosted behavior.

Run `python -B -m unittest discover -s scripts -p 'test_*.py' -v` from this skill folder after runtime changes. Tests include actual competing processes, cancellation, timeout, descendant containment and serial combined-artifact checks.
