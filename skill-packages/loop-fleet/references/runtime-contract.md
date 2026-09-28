# Local fleet runtime contract

Use `python -B scripts/fleet_runtime.py ABS_DATABASE ACTION --input ABS_JSON`.
Input is a JSON object with the named arguments below. Denied admission and invalid
inputs return nonzero. `run` also returns nonzero for failure, cancellation and
timeout. A successful CLI command is not a release decision. Database parent
directories must exist; use a local disk outside the product tree when possible.

| Action | Input |
| --- | --- |
| init | `subject` with exactly product/target/revision/configuration nonempty strings; positive integer `budget`, `concurrency`, `spawns`, `deadline_seconds`; optional absolute `workspace` (defaults to database directory) |
| acquire | `owner` string; optional positive `seconds` (default 30). Returns integer fence. Only an expired quiescent lease can be replaced. |
| renew | `owner`, `fence`; optional `seconds` |
| admit | `owner`, `fence`, unique `job_id`, nonempty `claims`, positive `reserve`. A reviewed host adapter must implement attach/finish and cancellation; prefer `run`. |
| run | Admission fields plus `argv`, absolute `cwd`, positive finite numeric `seconds` (booleans rejected), nonempty relative `artifacts` list |
| integrate | `owner`, `fence`, `plan` below |
| cancel/status | Empty object or omit input |

Claims contain exactly `resource` and `mode`. Resources are lowercase, for example
`file:worker-a/src/api.py`, `contract:registration/v2`, or `state:database/users`.
Mode is `read` or `write`. Exact and parent/child resources conflict when either
side writes. Two reads can coexist. `*` must be a write and serializes all work.
Files are relative to the workspace; case-folding is conservative on Linux.
Contract names require a shared registry: semantic aliases are not detected.

The full worst-case reservation remains charged regardless of outcome. Duplicate
job IDs cannot restart. Reservation, spawn, concurrency and conflict checks share
one SQLite transaction. Integration also reserves credits. There is no refund or
reset API. This prevents cooperative allocation races; provider billing requires
the parent host's separately enforced authority and metering.

`argv` is an array whose first member is an absolute executable; shell strings
are rejected. Artifacts use relative forward-slash paths without traversal or
alternate data streams. Keep worker directories independent: snapshots include
the whole worker directory and conservatively flag other workers' concurrent
edits in overlapping directories. Snapshot size is limited to 64 MiB, symlinks
are rejected, and database/SQLite sidecars are excluded. Writes outside the
directory and semantic contract effects are not observable by this snapshot.

On Windows, a wrapper waits on stdin while the coordinator assigns a kill-on-close
Job object. The dispatch byte is sent only after assignment. Descendants inherit
the Job. Assignment failure stops dispatch; cancellation terminates the Job and
waits for the wrapper. Closing the Job also kills descendants after normal parent
exit. POSIX uses a process group; escaping children require stronger containment.
Neither implementation is a filesystem/network sandbox.

## Integration plan

The plan has exactly `expected_jobs` (unique full list), `steps` (list of argv
arrays), `verify` (nonempty argv), `cwd` (absolute), `seconds` (positive total time
limit allowing finite positive fractions), `reserve` (positive integer credits), `artifacts` (relative files), and `criteria`
(nonempty parent criterion IDs). `steps` may be empty if no merge is needed.

All jobs must have succeeded and their output hashes must still match. Steps
execute serially, followed by final verification. No workers may be admitted
after integration starts. Failed integration preserves state and charges; no
automatic rollback/retry can repeat an uncertain effect. The receipt binds the
subject, plan hash, worker evidence hash, parent criteria, process results and
final artifact hashes. The parent must compare criteria to its accepted goal and
review the oracle: a helper cannot tell whether a successful command meaningfully
proves the requested behavior.

## State and recovery

The database is cooperative local state, not signed evidence. Protect it with
host permissions and pin runtime/configuration hashes in the parent. Leases use
wall clock, while active process time limits use monotonic time. Clock changes
can defer takeover. A new database must never reset consumed parent budgets.

Unknown termination leaves the job running and blocks takeover. Recovery never
kills a persisted PID, avoiding PID reuse mistakes. This version has no reviewed
reconciliation command for unknown jobs or interrupted integration. Preserve
branches, output files, original owner/fence, invocation evidence and remaining
criteria; route observed process/operation evidence to the parent's recovery and
migration owner. Do not claim automatic recovery across that boundary.
