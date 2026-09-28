# Implementation, verification, and stopping

## Before implementation

Confirm the current decision ID, selected option, user constraints, affected paths, target environment, permitted side effects, acceptance criteria, and rollback or compensation path.

Inspect the relevant code paths and existing behavior. Search for existing implementations before adding new ones. Record pre-existing failures before changing related code when safe and feasible.

Inspect branch and working-tree state before Git operations. Stay in the current checkout unless a branch change is both necessary and safe for unrelated work. Make a commit only when slice-owned changes can be isolated; stage explicit paths or hunks. Never push without separate approval.

## Implementation constraints

- Preserve the current language, architecture, database, agent runtime, and product scope unless the selected option changes them.
- Validate untrusted input and enforce least privilege at the execution boundary.
- Fail closed where required. Do not rely on prompt wording alone for authorization or safety controls.
- Use established cryptographic libraries and protocols; do not invent cryptography.
- Use the existing secret mechanism. Never put secrets in examples, tests, logs, commits, or responses.
- If the slice changes an environment variable, migration, run command, or recovery behavior, update its examples and operating procedure in the same slice.
- Leave no new placeholders, fake handlers, dead code, TODOs, or competing implementations.

## Verification

Inspect commands before running them; a local command may contact providers or shared systems.

Run the relevant repository suite and slice-specific checks. For agent behavior, exercise applicable happy path, refusal, injection, wrong-tool, timeout, cancellation, and duplicate-submission cases. Explain why any scenario is inapplicable.

Boot the application and exercise the affected critical path when safely possible. A green compile is insufficient. Mocks may support diagnosis and deterministic checks but cannot replace required real-integration evidence.

Record actual commands/procedures, environment, result, failure output, and limits. Distinguish new regressions from baseline failures and unavailable infrastructure.

## Bounded repair cycles

A verification cycle is one substantive repair followed by relevant verification. Allow at most three cycles for the selected slice.

Infrastructure outages or unchanged external blockers do not count as code-repair cycles; record them and do not repeatedly retry the same condition.

If the slice remains red after three cycles, ask whether to:

1. continue for one final extension of up to three cycles;
2. run a bounded mocked diagnostic while leaving acceptance open; or
3. `SKIP` the slice.

Do not start another decision while awaiting this choice. Allow only one extension. If still red afterward, mark the slice blocked, preserve the unresolved evidence, and present the next eligible decision.

Never weaken, remove, or bypass a valid test or control to obtain green. When intended behavior legitimately changes, explain the oracle change and preserve equivalent or stronger coverage.

## After each slice

Update the readiness state and report only:

- selected option and commit identity, or why changes remain uncommitted;
- resulting behavior and residual risk;
- commands/procedures and actual results;
- gate status changes and remaining open gates;
- next decision card or a recommendation to `STOP`.

Do not describe a blocked or verification-pending slice as complete.

## Stop report

On `STOP` or when local progress is exhausted, stop all further work and report:

- verified behavior and evidence environment;
- open, deferred, blocked, and externally dependent gates;
- documented boot command and whether it was verified;
- assumptions still in force;
- what remains unproven or unsafe for intended users;
- working-tree and commit status;
- exact resume prerequisite or next authorized action.

Stopping the session does not close unresolved gates.
