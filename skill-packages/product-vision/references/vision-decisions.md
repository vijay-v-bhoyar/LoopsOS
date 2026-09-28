# Owned experiments and founder decisions

Write the dossier to the user/host output root or the current workspace's `output/` directory. Keep a companion `vision-decisions/<slug>/record.json` containing only the material assumptions for the currently proposed scope. Use safe slug filenames. Return absolute file links after verifying the files exist.

Read [evidence-format.md](evidence-format.md) and use `scripts/vision_ledger.py`. Exact top-level fields:

```text
id: stable vision ID
owner: named founder/product decision owner
criteria: nonempty proposed scope criterion IDs
assumptions: nonempty records defined below
events: ordered experiment and decision events
```

Each assumption has exactly `id`, `claim`, `owner` (experiment owner), `affected_criteria` (nonempty subset), `experiment` (discriminating procedure), `decision_owner`, and `revisit_trigger`. Every criterion must be covered. Preserve supplied founder facts verbatim in the dossier; distinguish their provenance from hypotheses and researched evidence. The helper tracks material questions, not every sentence of the dossier.

| kind | Additional fields |
|---|---|
| experiment | assumption_id, receipt, interpretation |
| decision | assumption_id, actor, outcome (accepted/rejected/deferred), rationale, acceptance (artifact), evidence_sha256 |

The experiment receipt may describe a research validation procedure or executed local check. Its successful exit/assertions mean that procedure ran and its stated checks passed, not that a market prediction is true. Keep cited research, collection dates and uncertainty in the archived output. The interpretation must state whether findings support, weaken or contradict the assumption. A rejected hypothesis can still have a successful evidence-collection procedure.

The decision must name the designated decision owner, cite the current experiment output's SHA256 and retain the actual decision artifact. A written agent claim is not founder approval. The host verifies the decision source and actor identity. A new experiment invalidates the old decision until reviewed again. Subject changes and expired evidence withdraw readiness without deleting the earlier decision.

`PROPOSED_OR_PARTIALLY_ACCEPTED` lists unresolved owners, questions, experiments and revisit triggers. `accepted_criteria_recorded` excludes a criterion whenever any of its required assumptions is unaccepted or stale. `VISION_ACCEPTANCE_REVIEW_READY` means all recorded decisions are current and bound; it still returns `execution_authorized: false`. Check actual authority and the exact accepted wedge before allowing dependent planning or construction.

Continue independent diligence while waiting for a material decision. Ask the blocking question through the existing parent help route, with the smallest acceptable response. Do not repeat specialist work when the question and evidence remain current. Track selected skill path/hash and question in the dossier's evidence index; changed inputs trigger only the affected specialist.

Run `python -B scripts/test_owner_ledger.py` after changes. The suite uses actual local process/output files and tests persistent acceptance, wrong decision owner, deferred decisions, shared criterion dependencies, stale experiments and mismatched evidence.
