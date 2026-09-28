# Running the product-diligence loop

## Current invocation and integrity contract (2026-09-19)

Run `python /absolute/path/to/this-skill/orchestrate.py COMMAND` from the product
workspace. In the shorthand examples below, `orchestrate` means that invocation;
there is no installed shell command by that name. Scripts, rules and prompts are
resolved inside this skill, with no dependency on neighboring skill directories.

The executable checker verifies local evidence integrity, not source truth or
authenticated actors. Give `config.json` actual `model_pins.sweep` and `.challenge`.
For model-evolution assessment also supply `subject` (product, revision,
environment, configuration) and `model_evolution` (path, sha256). Read
[the evolution contract](references/evolution-contract.md) for its typed evidence.
The input config's evolution path is relative to that config file and must resolve
inside `.diligence`; init stores it relative to `.diligence`. All proof paths are
also relative to `.diligence`. Ordinary checklist artifact paths are made absolute.
Map evolution and proof artifacts to free A-22+ IDs so the
reviewer can inspect and cite them. Existing IDs are never silently reassigned.

`evolution-check` prints capability and candidate decisions. Exit 0 means the
capability contract qualifies; inspect each candidate's decision separately.
Exit 2 means evidence is missing/invalid or criteria are not met. Neither is a
deployment operation. The scorecard includes the evolution result automatically.
Use `sweep-payload --group model_evolution` for the new E-01..E-08 surfaces; that
group also includes artifacts beyond the original A-01..A-21 checklist.

`init` refuses to overwrite existing state. Use `rerun --map map.json [--config
config.json]` to refresh artifact/config/model identity; old state is archived in
`.diligence/history`. Any changed/removed artifact, model/config/subject, rule or
prompt marks existing findings pending revalidation. Supply current findings with
`revalidates: "ID"` to replace them while retaining IDs/history. Unresolved unknowns
may stay unknown; they must still be assessed. Re-run the challenge on current
evidence, ingest even an empty result, reconcile and render. The local challenge
receipt binds inputs but does not prove evaluator independence. Historical markdown
reports are snapshots and cannot be reused as current readiness decisions.

For automatic product improvement, follow [the adaptive method](references/adaptive-method.md).
This package prepares and checks evidence. Actual recurring discovery, provider
evaluation, budget enforcement and deployment need the product's configured
adapters and authority; no service is started by invoking the checker.


## Full command sequence

Use one writer per product state directory. These are local assessment files, not
an authenticated concurrent queue or an always-on autonomous runtime.

```text
orchestrate init --map map.json --config config.json
orchestrate admit
orchestrate status
orchestrate sweep-groups
orchestrate sweep-payload [--group model_evolution]
# Run the payload in the supplied sweep-model context; save findings.json.
orchestrate ingest-findings findings.json
orchestrate derive
orchestrate challenge-payload
# Run a fresh reviewer against evidence and conclusions; save challenges.json.
orchestrate ingest-challenges challenges.json
orchestrate reconcile
orchestrate check --verbose
orchestrate render
orchestrate evolution-check
```

The four optional sweep groups are `security_and_data`, `product_and_strategy`,
`ops_and_release`, and `model_evolution`. Omit `--group` for all evidence. Each
stage uses supplied model results; the Python driver makes no provider calls.
The independent context must be real and disclosed. The scripts cannot verify
that two labels represent independent reviewers.

`map.json` maps artifact IDs to actual file paths, resolved from the invocation
working directory. Assign the original A-01..A-21 categories from the executive
method; additional artifacts use unused IDs. The operator classifies artifacts;
file presence alone does not prove that they support a claim. `config.json`
contains actual review-model pins and optional owner_roster, release_calendar,
valuation, subject and model_evolution fields. Omitted business inputs stay unknown.
During rerun, explicitly supplied config fields replace previous values; omitted
fields are retained. Use explicit null to clear an optional value.

## Reassessment and recovery

```text
orchestrate rerun --map current-map.json --config current-config.json
orchestrate status
orchestrate sweep-payload
# Reassess pending IDs; each replacement includes revalidates: existing-ID.
orchestrate ingest-findings current-findings.json
orchestrate derive
orchestrate challenge-payload
orchestrate ingest-challenges current-challenges.json
orchestrate reconcile
orchestrate render
```

Changed inputs invalidate prior review receipts. All rows are conservatively
reassessed after any source or contract change, including supplied ownership,
release-calendar or valuation parameters. A changed model-evolution file must have
its new hash supplied explicitly; the driver never silently endorses new bytes.
An expired proof needs newly executed evidence, not just a new timestamp.

Render refuses pending revalidation, stale review bindings, changed artifact bytes,
missing pins, inconsistent decisions, or invalid supplied evolution evidence.
If a write is interrupted, inspect current state and its archived prior snapshot
before resuming; the package is not a transactional multi-writer service. Do not
use its output as an authorization token. A stale markdown snapshot remains
historical even if it says PASS.

## Evidence integrity and model-evolution gate

The checker P1-P11 covers register schema/dedup, citations, severity modes,
rederived decision fields, admission, challenge resolution, supported owners/dates,
structural lifecycle proof, scorecard parity, current manifest hashes/pins/pending
state, and supplied evolution evidence. These tests do not prove that a cited
sentence is true, a named reviewer is authenticated, or an evaluation actually ran.
The original business lenses remain engineering heuristics, not financial advice.

D6 reads the current evolution config and proof receipts in addition to register
rows. It cannot use MC-5/6/7 strength labels alone to claim evaluated resilience.
Read [the evolution contract](references/evolution-contract.md) before preparing
those receipts. To obtain useful missing-evidence reporting, omit an unavailable
model_evolution field; never provide fabricated proofs to make the gate green.
The missing field keeps D6 unqualified while allowing a clearly partial review.

The helpers disclose oversized artifact truncation; pre-excerpt large files with
stable locators or record partial coverage. Four characters per token is only a
rough estimate. No external data is uploaded by the local scripts.
