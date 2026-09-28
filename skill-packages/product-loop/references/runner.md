# Running a bounded local product cycle

The supported executable is `scripts/cycle_adapter.py`. The former `run_loop.sh`
refuses execution because it admitted missing bundle/budget inputs and executed
shell text. Historical v13 I1-I30 probes remain a requirements suite; passing the
local adapter tests does not claim they all passed.

## Admission and execution

Use an available Python 3 runtime and absolute paths:

```text
python -B cycle_adapter.py snapshot --repo REPO
python -B cycle_adapter.py admit --config CONFIG --config-sha256 FULL_FILE_SHA
python -B cycle_adapter.py init --config CONFIG --config-sha256 FULL_FILE_SHA --state STATE
python -B cycle_adapter.py run --config CONFIG --config-sha256 FULL_FILE_SHA --state STATE
```

Read `local-cycle-contract.md` for configuration and receipt schemas. `snapshot`
reads Git identity and hashes every tracked or nonignored untracked file; it does
not approve that identity. `admit` checks the exact snapshot, full control hashes,
expiry, STOP, branch and finite local limits. `init` creates one new ledger, and
`run` reserves one complete maximum duration before dispatching exactly one argv
process. Each invocation uses `shell=False`; it never discovers executable text
from COMMANDS.md. The caller supplies the previously reviewed configuration file
SHA from trusted context and must enforce actual authority and host containment.

The ledger is outside the product repository so execution records do not change
product identity. An exclusive-create lock prevents simultaneous cooperating
writers. Atomic replace protects ordinary interrupted writes. No stale lock is
silently stolen. An interrupted active cycle or uncertain cancellation blocks
restart pending inspection; old persisted PIDs are never killed automatically.
These are local integrity controls, not a defense against a malicious state owner.

On Windows a waiting Python wrapper joins a kernel Job object before dispatching
the target process; killing or closing the job terminates its process tree. On
POSIX a process group receives termination. STOP is checked before reservation,
before dispatch and during execution. The host still owns filesystem/network
isolation, secrets, memory/CPU limits, and preventing deliberate process escape
on POSIX. Windows requires the wrapper Python executable in the pin set.

The ledger charges the entire reserved per-cycle duration and one attempt even
when work fails, times out, or finishes quickly. This conservative local resource
allocation never refunds an unknown outcome. The receipt records actual elapsed
seconds separately; the measured number can include polling/termination overhead.
There is no dollar or token meter: provider-capability configurations are refused.
The parent scheduler must preserve aggregate budgets across changed configurations.

## Completion, failure and parked work

A zero exit without a fresh exact-subject receipt fails. A valid receipt names the
actual local artifact and full hash, parent goal/criteria, and current run identity.
`CYCLE_REPORTED` means the process supplied that report. It does not verify product
correctness, full v13 compliance, release authority or parent acceptance. The parent
conductor independently checks the original acceptance before closing the goal.

Failures produce `FAILED`, `TIMED_OUT`, `CANCELLED`, or `UNKNOWN_CANCELLATION`.
Uncertain cancellation retains active state and blocks another run. Terminal
failure preserves the consumed reservation. The adapter does not reset user work,
create branches, make commits, deploy, retry effectful operations, or run model
commands implicitly. Local command classification is host-owned; a malicious argv
can do whatever its OS credentials allow.

`park --event EVENT` records a concrete item/reason/prerequisite fingerprint.
Reconsidering unchanged prerequisites or the same changed fingerprint twice fails.
A changed fingerprint yields `REVALIDATION_REQUIRED`, never an execution permit.
The parent resolves help and integrates verification before a new cycle.

Automatic legacy release remains `BLOCKED_LEGACY_COMPATIBILITY`. Release preparation
can be local work; actual effects require a separately repaired/verified owner and
current authorization. This adapter never interprets veto silence as consent.

## Verification

```text
python -B -m unittest discover -s scripts -p test_cycle_adapter.py -v
```

Tests execute only temporary local fixture repositories/processes. Use a clean
isolated target for real delivery. Re-run affected tests when invocation, identity,
reservation, receipt or process-control behavior changes. No scheduler is started
by merely installing this package.
