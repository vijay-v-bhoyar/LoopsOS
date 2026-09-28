# Durable repair history and parent acceptance

The delivery owner maintains `.loop/repairs/<episode>/record.json` for a material repair episode. Reuse an existing matching record; do not create a second tracker for the same repair. The lifecycle conductor owns the full goal, dependencies, scheduling, help delivery and aggregate budget. This record owns diagnosis and repair evidence only.

Read [evidence-format.md](evidence-format.md) for the portable CLI, receipt format and trust limits. Use `scripts/repair_ledger.py`. Top-level fields are exactly:

```text
id: stable episode ID
parent_goal: conductor's stable goal ID
criteria: nonempty list of the parent's accepted criterion IDs
mode: IMPLEMENT | DIAGNOSE | TEST
max_attempts: positive integer, inherited within the parent's remaining limit
events: ordered list, initially empty
```

Event fields (all text fields are nonempty):

| kind | Additional fields |
|---|---|
| failure | id, criterion, category, hypothesis, receipt |
| finding | id, criterion, category, hypothesis, observation, receipt |
| repair | failure_id, owner, diagnosis, changes (artifact references) |
| verify | failure_id, criteria, original (receipt), regression (receipt) |
| help | failure_id, owner, question, needs, wake_condition |

Categories: product, baseline, environment, dependency, test, capability, authority, unknown. A `failure` receipt records a nonzero exit code from an actual diagnostic or original check. Use `finding` when an exploit or adversarial probe exits successfully because it reproduced unsafe behavior; retain its observed result, then verify that the same probe is rejected after repair and that a secure acceptance oracle plus adjacent regression pass. A finding's closure oracle may differ from its reproduction oracle, but the same reproduction oracle must be rerun and remain hash-bound. A missing test result is not a failed test. For an unexercised blocker, retain the conductor's typed help record until a diagnostic can run. Do not fabricate an exit code or failure to satisfy this helper.

Archive pre-fix source, output and oracle under the episode directory so historical evidence remains readable after source changes. Repair events record the resulting changed artifact snapshots. Across the original and adjacent regression receipts, verification must cover every changed artifact; each receipt should list only artifacts its command actually exercised. A finding's post-repair reproduction must use the same oracle hash and name at least one repaired runtime artifact, then the original and adjacent regression receipts jointly cover the full repair. If an oracle itself was defective, retain the finding as unresolved and obtain a separately reviewed replacement acceptance contract; this helper has no automatic oracle-waiver path.

Each failure ID is unique. Failure count and repair-event count independently cannot exceed `max_attempts`; the host enforces actual CPU, time, spend and the parent's remaining budget. Append a help event before returning a blocked episode. Receiving a reply is not verification: inspect it, perform the authorized correction, then rerun the original and regression checks.

`PARENT_REVIEW_READY` means all recorded failures have current verification and the episode covers its assigned criteria. It always returns `parent_complete: false` and `authority: none`. The conductor checks the assigned criterion set against its own accepted goal, integrates the child changes, and verifies the final journey. `REPAIR_OR_HELP_REQUIRED` preserves unmet criteria and pending failure IDs across processes. Expiry or a changed current subject removes readiness while retaining history.

Run `python -B scripts/test_owner_ledger.py` with the host's Python executable after modifying the helper. Tests execute a deliberately failing local Python assertion, retain it, exercise the corrected value, then challenge stale scope, changed artifacts, incomplete combined coverage, finding-oracle identity, competing writers, attempt limits, modes and partial parent criteria.
