# Local scheduling, delivery and reviewed migration

Use these helpers only when a project does not already have an adequate controller.
They provide actual local execution and persistence, not hosted availability or
provider authorization. The installed `product-loop/scripts/cycle_adapter.py`
owns each finite cycle. The lifecycle scheduler owns cumulative dispatch/time
reservations across those cycles. Do not nest another independently resettable
goal budget around the same work.

## Scheduling and process limits

`scripts/local_scheduler.py` supports `register`, `tick`, finite `serve`, `status`,
`cancel`, `reconfigure` and `complete`. Invoke with the real host Python and
`--db` pointing to a local SQLite file outside the product repository. The database
must be on a filesystem that supports SQLite's locking; network filesystems and
distributed coordinators are not supported by these tests.

Before registration, use the installed product-loop adapter's portable-runner
reference to prepare, inspect and initialize the real cycle configuration/state.
Supply the exact repository, current files/HEAD/branch, executable and control pins,
existing authority, finite local argv and accepted parent criteria. A configured
path is not proof of callable capability or authority. Legacy provider/release
execution remains blocked.

The scheduler specification has exactly:

| Field | Meaning |
|---|---|
| `id`, `goal` | Stable local job ID and the cycle configuration's parent goal ID |
| `python`, `adapter`, `config` | Each has an absolute `path` and full file-byte `sha256`; inspect the actual interpreter, adapter source and configuration before accepting pins |
| `cycle_state` | Absolute initialized cycle ledger path outside the product repository |
| `interval_seconds`, `due_epoch` | Positive interval and initial UTC Unix due time; no catch-up bursts |
| `max_dispatches` | Positive cumulative dispatch ceiling, at most 10,000 |
| `per_dispatch_seconds`, `total_seconds` | Positive outer wall-time reservation per dispatch and cumulative ceiling; include adapter startup/admission/cleanup overhead |

For an actual spec file:

```text
python scripts/local_scheduler.py register --db SCHEDULER.db --spec JOB.json
python scripts/local_scheduler.py tick --db SCHEDULER.db
python scripts/local_scheduler.py serve --db SCHEDULER.db --ticks 5 --poll-seconds 1
python scripts/local_scheduler.py status --db SCHEDULER.db
python scripts/local_scheduler.py cancel --db SCHEDULER.db --job JOB_ID
```

Capitalized tokens are actual run-specific inputs, not defaults. `serve` executes
in the calling foreground process and exits at its finite tick bound. It is not
installed as a service. For an explicitly requested Codex recurring task, discover
the actual automation tool, inspect existing automations, and schedule a bounded
invocation with exact product/state paths. Store the returned automation ID and
verify it. Do not create a background schedule merely because this skill was read.

SQLite transactions prevent cooperating scheduler processes from claiming the
same due job. Reservations are charged before spawning and are not refunded on
failure, cancellation or interruption. Every cycle also uses the adapter's own
local limits. These are dispatch count and time controls, not provider/token/money
metering. Provider calls require an appropriate enforcing host/provider adapter;
the current local lane cannot prove a billing cap or network isolation.

Cancellation targets only the currently owned process. Uncertain termination
remains `UNKNOWN`. A crashed scheduler leaves the durable job `RUNNING`; age or a
saved PID cannot authorize takeover. Inspect actual process and cycle state, retain
the reservation, and resolve the exact missing condition before any new operation.
There is no automatic PID-based crash recovery or state reset.

Pin/configuration drift sets the job `BLOCKED`. `reconfigure --spec NEW_JOB.json
--previous-spec-sha256 DIGEST` accepts a reviewed replacement for an idle READY or
BLOCKED job while preserving job/goal, repository, parent criteria, attempts and
resource ceilings. DIGEST is the old specification's canonical `progress_state.digest`.
Keep the old config file intact. A changed product requires a fresh inspected
adapter config and initialized cycle state; reconfiguration does not erase the
parent's cumulative reservations. It cannot reopen a cancelled or uncertain job.

## Help delivery and response

Prefer the current Codex task's actual input tool for user questions. Persist its
request/event identity and wake condition in the existing help tracker. Use an
external messaging connector only with explicit authorization for the recipient.

For a local operator/worker inbox, `deliver-help --request REQUEST.json --sha256
FULL_FILE_HASH --spool EXISTING_DIRECTORY` atomically writes a real local file and
records its content hash. Request fields are exactly `id`, `goal`, `question`,
`recipient`, `acceptance`, `wake_condition`. IDs are stable lowercase alphanumeric,
underscore or hyphen identifiers. Repeated identical delivery is deduplicated;
changed content under the same ID requires inspection. `FILE_DELIVERED` does not
mean a human received, read or approved it.

`receive-help --response RESPONSE.json --sha256 FULL_FILE_HASH` records matching
`id`, `goal`, `responder`, `answer`. It validates delivery identity and keeps the
response as data. Conflicting responses do not overwrite history. Revalidate the
actual condition through the progress helper before resuming work. No response
text is executed; a responder name is not an authenticated principal.

## Goal completion stops scheduling

A cycle's `CYCLE_REPORTED` is not parent acceptance. After the actual final
integrated review, `complete --job ID --review REVIEW.json --sha256 FULL_FILE_HASH`
requires a review with `goal`, `reviewer`, `result: GOAL_VERIFIED`, `state` and
`artifact` pins. The current progress state must independently evaluate to
`READY_FOR_GOAL_REVIEW` for that same goal. The pinned artifact records the actual
final review. Criteria must exactly match the scheduled cycle's parent criteria.
Its current subject must be `{product: repository absolute path, target:
local-process, revision: full Git HEAD, configuration: cycle config file SHA256}`.
The pinned adapter reruns repository admission to reject changed source/content.
After product changes, inspect and reconfigure the cycle before final verification.
A successful local completion prevents further scheduled dispatches.
Review contents still require caller judgment; hashes do not authenticate truth.
Cancel/pause the actual host automation too when its continuing purpose has ended.

## Reviewed progress-limit migration

`scripts/migrate_state.py` implements a deliberately narrow, same-engine migration:
increase reviewed local attempt limits without changing goals, tasks, dependencies,
subjects, controls, work history, blockers, operation keys or counters. Other schema,
engine or scope changes remain unsupported and require their own reviewed adapter.

Prepare the replacement plan and a `limit_migration_review` with exact
`previous_state_sha256`, canonical `new_plan_sha256`, `reviewer`, `reason`, aware
`issued_at`/`expires_at`, and a relative hashed evidence `artifact`. Authenticate the
actual review/authority outside the JSON. Then invoke the migration with `--state`,
`--plan`, `--review`, `--expected-state-sha256` and `--expected-review-sha256`.

Migration uses the same exclusive ledger lock, rejects active/unknown effects,
validates the old history, prepares a before/after journal, and atomically replaces
the same state file. Repeated identical execution reconciles the committed result.
An interruption after journaling can resume with the same reviewed inputs. The
journal preserves the original chain while the replacement chain binds the new
plan; no historical events or counters are removed. These local files are not
tamper-resistant against an actor allowed to rewrite all artifacts.
