# Portable local cycle contract v1

The contract ID is `product-loop/local-cycle@1`. All JSON objects have exact fields;
unknown fields, duplicate keys, nonfinite numbers and malformed required data fail.
Configuration and state files are bounded to 4 MB. Paths must not traverse symlinks
or Windows reparse points. Hashes are full lowercase SHA-256 values.

## Configuration

Construct the actual reviewed configuration using these fields, then compute its
**file SHA-256** for `--config-sha256`. Do not substitute a canonical object hash
for this file hash. The CLI verifies both the file bytes and parsed structure.

| Field | Required value |
|---|---|
| `schema` | Integer `1` |
| `capability` | `local-process`; release/provider modes are rejected |
| `parent_goal` | `{ "id": nonempty string, "criteria": unique nonempty string array }` |
| `identity` | Exact output of `snapshot --repo`: `repo`, `head`, `branch`, `files_sha256`, `status_sha256` |
| `argv` | Nonempty array of literal strings; absolute executable first; no shell parsing |
| `pins` | Nonempty array of `{ "path": absolute existing file, "sha256": full hash }`; executable must be pinned, and on Windows the current Python wrapper runtime must be pinned |
| `limits` | `{ "max_cycles": positive integer <=10000, "wall_seconds": positive finite number, "per_cycle_seconds": positive finite number <= wall_seconds }` |
| `expires_at_epoch` | Future Unix timestamp in seconds |
| `environment` | `minimal-local` |

The config must pin every reviewed control input used by its command, including
scripts, command registry and skill/control files when applicable. The adapter can
check the declared set; it cannot discover every dynamically loaded dependency.
The caller must review executable arguments and pin coverage before approval.
The minimal environment includes only OS path/temp essentials plus receipt fields;
it does not prevent a child from reading files its OS principal can access.

Identity is bound to an exact Git root, full HEAD, branch and file/status snapshot.
Allowed branches start with `codex/` or `loop/`; no branch is created automatically.
Submodules are not supported by this adapter and fail admission. Ignored untracked
files are outside the Git snapshot, so relevant ignored controls must be pins.
Unrelated user edits are preserved and invalidate an older configured snapshot.
After product content changes, a fresh reviewed configuration is required. A
parent controller must retain the original goal and aggregate budget when moving
between configurations; initializing another ledger is not a budget extension.

The state path must be outside the product repository and its parent must already
exist. The ledger pins the canonical configuration digest and the adapter source
digest. There is no in-place migration/reset or recovery permission API. Changed
code/configuration or active interrupted work requires reviewed reconciliation.

## Child handoff

The child receives `LOOP_RUN_ID`, `LOOP_CONFIG_DIGEST`, `LOOP_RECEIPT_PATH` and
`LOOP_PARENT_GOAL` (JSON) in its environment. It must write the following exact
receipt fields to the unique receipt path before exiting with code zero:

| Field | Required value |
|---|---|
| `contract` | `product-loop/local-cycle@1` |
| `run_id` | Exact `LOOP_RUN_ID` |
| `config_digest` | Exact `LOOP_CONFIG_DIGEST` (canonical parsed configuration digest) |
| `parent_goal` | Exact parsed `LOOP_PARENT_GOAL` |
| `result` | `LOCAL_WORK_REPORTED`, `PARKED`, or `REVIEWED` |
| `artifact` | `{ "path": existing artifact inside product repository, "sha256": full file hash }` |

An already-existing receipt is rejected before spending. A missing receipt, stale
run identity, wrong parent, nonzero process exit, missing artifact or hash drift
fails the invocation. A process may truthfully report a parked cycle. The parent
must read `receipt.result`; `CYCLE_REPORTED` does not imply the selected item passed.
The artifact proves file identity, not semantic correctness. A caller-controlled
receipt is not an independent verifier or authenticated release approval.

## Results and accounting

`admit`: `LOCAL_PROCESS_ADMITTED`, contract, exact identity, parent goal,
`authority: caller-must-enforce`, `release: BLOCKED_LEGACY_COMPATIBILITY`.

`run`: `run_id`, `status`, `elapsed_seconds`, `reserved_seconds`, `returncode`,
`receipt` or null, `error` or null, `parent_acceptance: NOT_EVALUATED`, and the same
blocked release value. Run statuses are `CYCLE_REPORTED`, `FAILED`, `CANCELLED`,
`TIMED_OUT`, `UNKNOWN_CANCELLATION`. All but `CYCLE_REPORTED` exit 2. Structural or
admission refusal emits `BLOCKED` with its reason and exits 2. Process output is
not copied to stdout; the configured child must put diagnostic evidence in its
artifact. No test, security, release, rollback, or parent-goal PASS is fabricated.

Each initialized ledger cumulatively reserves one cycle and the full per-cycle
duration before invocation. Budget reservations survive failures and ordinary
crashes. State checksums and an exclusive local lock detect accidental corruption
and concurrent cooperating access, not hostile rewriting or lost external copies.
Actual elapsed time includes startup, polling, and termination overhead; it is
reported separately and is not claimed as an exact OS hard wall-clock cutoff.

## Parked prerequisite events

`park --event PATH` accepts `{ "action": "park" | "reconsider", "item": ID,
"prerequisites": nonempty string-to-string map, "reason": concrete string }`.
Prerequisite values should be verified source digests or explicitly typed missing
states. `park` stores its fingerprint. `reconsider` requires a different fingerprint
and refuses a previously reconsidered value. It emits `REVALIDATION_REQUIRED`
with `execution_authority: none`; the parent checks evidence and current authority.
This is local durable eligibility tracking, not a help message sender or oracle.
