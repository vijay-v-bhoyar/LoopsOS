# Independent progress-ledger red check

Executed 2026-09-13 UTC. Scope: the new advisory local `progress_state.py` and its test suite. No expected scenario manifest was read. Initial checked source SHA256: `dcaa3e405f4f433c594b2d3cc1b42897b1b9433c84c1e232008396ad848bc530`.

**Final local result: 10/10 independent probes and 38/38 unit tests passed after blue-team repairs.** The seven reproduced findings below are closed for their tested local transition scope. They are not proof of producer trust, provider effects, production authority, or an unattended runtime.

**Initial result: changes required.** The author's 27 tests passed, while independent adversarial transitions reproduced four material state/identity gaps and one diagnostic gap. Further probes found a malformed-input error and a reconciliation/blocker bypass. The helper does correctly label its output `authority: none` and `recorded local integrity only`; findings below do not imply that it executed a provider action or independently granted permission.

The independent harness is [product-lifecycle-progress-redcheck.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/output/product-lifecycle-progress-redcheck.py). Run it using the bundled Python with `-B`. It imports the source, creates isolated temporary ledgers and simulated receipts, exercises public ledger functions, runs a malformed-state CLI probe, prints observations and cleans up fixtures. The mocked clock is used only for expiry testing. No fixture proves producer trust, provider behavior, or an actual user journey.

## PLC-PR-001 — An ordinary verify event resolves an unknown external operation

P1. Observed local execution.

Reproduction: start task `a` as external with key `logical-one`; `next` correctly recommends `RECONCILE_EXTERNAL_EFFECT`; apply an ordinary `evidence` receipt through `verify`, with no reconciliation record or operation key. It is accepted, status becomes `verified`, and the operation's effect becomes `applied`.

Source: initial [progress_state.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/skill-packages/product-lifecycle-loop/scripts/progress_state.py:352) permits verify from `active`; line 357 marks any associated operation applied. The ordinary evidence schema at line 217 does not require an operation key.

Impact: a lost-response operation can be “settled” by unrelated or insufficiently bound evidence even though the advice explicitly required reconciliation. Parent integrations may trust the record and continue dependent work.

Repair: require operation-key-bound reconciliation before accepting ordinary verification whenever effect is unknown. If a combined verify-and-reconcile receipt is desired, define that explicitly and validate its complete operation identity and effect assertion. Oracle: the direct path rejects without changing state; a matching reconciliation then verification succeeds; mismatched key/subject rejects.

## PLC-PR-002 — A failed recheck cannot enter recovery from verified state

P1. Observed local execution.

Reproduction: start and verify task `a`; mutate the recorded artifact so its hash no longer matches; `next` correctly recommends `REVERIFY_EVIDENCE`; applying `block` for the failed recheck rejects with `only running work may fail/block`.

Source: initial [progress_state.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/skill-packages/product-lifecycle-loop/scripts/progress_state.py:326) only admits fail/block from `active` and `verify_existing`; line 499 recommends rechecking a `verified` task. Start also requires `pending`.

Impact: the loop can recommend a diagnostic action whose failure has no honest transition to help and repair. Changing subject solely to escape this state would falsely describe a product change; repeated rechecking is ineffective.

Repair: add an explicit bounded recheck transition or permit verified→blocked on recorded recheck failure, discard stale accepted receipt, retain failure history, then use normal scoped revalidation and retry rules. Oracle: after stale evidence and a failed recheck the blocker is durable, a relevant helper can resolve it, and the same subject can eventually complete without fabricated invalidation.

## PLC-PR-003 — Expired unblock evidence still allows starting work

P1. Observed local execution with a controlled clock.

Reproduction: start→block; apply a `revalidation` receipt that expires in twenty seconds; move the helper's clock to one hour after expiry. `next` reports `START_TASK`, and a new start event is accepted.

Source: initial [progress_state.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/skill-packages/product-lifecycle-loop/scripts/progress_state.py:348) validates resume once and changes status to pending. The accepted revalidation is not retained in task projection or checked at start, unlike ordinary completion evidence.

Impact: capability, configuration, input or external-state evidence used to clear a blocker may expire while waiting for another task or a later invocation. A saved pending state then loses the condition that made progress admissible. This helper does not enforce actual authorization; that remains a separate caller obligation.

Repair: retain the accepted resume receipt and bind it to the blocker fingerprint, subject and changed condition; recheck its file identity, artifact and freshness before presenting/accepting start. Route expired revalidation to help/recheck, preserving attempts. Oracle: expiry or mutation after resume blocks start; current valid replacement revalidation can resume without resetting attempts.

## PLC-PR-004 — Distinct tasks can reuse one external operation key

P1 for a future effect adapter that relies on these keys; observed local acceptance only.

Reproduction: start external task `a` with `one-key`; start distinct external task `b` in the same subject with `one-key`. Both are accepted and retain the identical key.

Source: initial [progress_state.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/skill-packages/product-lifecycle-loop/scripts/progress_state.py:314) checks stable key reuse only within the current task; no registry binds keys to a unique logical operation across tasks.

Impact: an effect adapter can accidentally use the same idempotency key for different intended operations. Depending on the provider's key scope, the second operation may be deduplicated into the first, rejected, or ambiguously reconciled. No provider collision was tested.

Repair: define the intended uniqueness scope (provider/account/operation family, or conservatively the whole goal) and bind each key to one logical task/operation. Allow retries of that same operation, reject another task claiming it. Oracle: same-task retry after not-applied reconciliation preserves the key; cross-task reuse in the same scope rejects before any effect intent is admitted.

## PLC-PR-005 — Deleted help artifacts are still offered as actionable responses

P2. Observed local execution.

Reproduction: blocked task receives a hashed help artifact; delete that file; `next` still includes `REVALIDATE_HELP` and the reference without an integrity issue. Independent runnable work remains available, which is good, but the helper may repeatedly select a vanished response once that work ends.

Source: initial [progress_state.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/skill-packages/product-lifecycle-loop/scripts/progress_state.py:489) returns stored help references; line 503 treats any nonempty stored help list as revalidation-ready. Replay intentionally avoids live checks on historical artifacts, so a live help check must happen separately.

Repair: report per-response current integrity status, distinguish missing/corrupt from usable help, and request replacement evidence when needed. Do not interpret response text as instructions or authority. Oracle: missing/changed help is explicitly stale/unavailable and cannot repeatedly be selected as usable evidence; a current replacement restores the revalidation option.

## Checks that passed and remaining limits

### PLC-PR-006 — Runtime-rejected JSON integer loses structured CLI errors

P3. Observed local execution. A 5KB state file containing a 5,000-digit JSON integer returned exit 1 with empty stdout and a Python `ValueError` traceback. The runtime rejects integer conversions above 4,300 digits; `read_json` only catches JSONDecodeError/UnicodeError. No unsafe pass occurred, but callers expecting structured blocked state lose the diagnostic/recovery contract. Catch and wrap decoder ValueError appropriately; do not increase the interpreter limit. Oracle: this fixture returns exit 2 with `INVALID_OR_BLOCKED`, no traceback and no state mutation. Added to the persistent independent harness.

- The author's 27 unit tests passed in this run. This includes current dependency evidence, duplicate JSON keys, attempt limits, revision conflict, lock behavior and change detection cases. Those results do not cover the five transition gaps above.
- The independent malformed-ledger CLI probe returned exit code 2, structured `INVALID_OR_BLOCKED`, error `invalid JSON`, and `authority: none`, with no traceback.
- The independent harness observed exact source identity and stores a source hash in its output. Original source locators above refer to that identity; later blue-team repairs require rerunning the probes and updating the final status below.
- Hash-chained records and writable engine/plan hashes detect accidental or unsophisticated inconsistent edits. They are not tamper-resistant history or an authority boundary against a writer able to rewrite the entire ledger consistently. This is an acknowledged design limit, not a newly claimed exploit.
- No filesystem race, real process crash between external effect and receipt, distributed lock contention, billing/provider idempotency, or enforcement of token/money ceilings was tested. The lock is an exclusive local file and requires manual recovery after a crash; no automatic lock stealing was attempted.

## Repair verification

The initial findings were sent to the integration owner with exact reproductions before final acceptance. Blue-team fixes were then independently rerun with the same adversarial fixtures.

### PLC-PR-007 — Reconciliation clears an unrelated blocker without revalidation

P1. Observed during repair verification against source `c90cc198ee313066c7a8520fc93ed297357b03f7ec268e576943d9fa583160ac`. Start an external task; block it for missing capability; reconcile its operation as applied; apply ordinary evidence verification. Verification succeeds while the original capability blocker remains recorded and `revalidation` is null. The reconciliation settles effect uncertainty but does not establish that the missing capability or a changed-subject prerequisite is resolved. Preserve blocked state until relevant current revalidation; then route to verification of the existing effect without redispatch. This case is retained as `unrelated_blocker_after_reconcile` in the independent harness.

Two additional discriminating liveness probes were added at the integration owner's request. Applied effect→failed verification→revalidation must resume `VERIFY_EXISTING_EFFECT` without redispatch; invalid prerequisites must prevent offering downstream `VERIFY_EXISTING_EFFECT`. Both passed on the intermediate repaired source. They validate local transition behavior only.

### Final evidence

Final source `progress_state.py` SHA256: `99fd31d8ed03d9db5bd6ecc1a171921bf57d047fa4707748982384bf39a63aa3`.

Unit test source `test_progress_state.py` SHA256: `6b05bc2bb9e1791ab8e5299b0f86c54cf700d9429c41992641a1ee7f006072ff`.

Independent harness SHA256: `a6526bd6c9681973bf922615632f0a05aa96643859571643900f6119ebe592ca`.

Executed with `C:/Users/vijay/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B`:

- `output/product-lifecycle-progress-redcheck.py`: **10/10 explicit oracles passed**, exit 0. This includes all seven reproduced failures, two added liveness paths and the original malformed-JSON CLI control. The harness exits nonzero if an oracle fails.
- `-m unittest discover -s skill-packages/product-lifecycle-loop/scripts -p test_progress_state.py`: **38/38 tests passed**, exit 0.

Observed repairs: unknown external outcomes require matching applied reconciliation before verification; stale verified work can enter blocked recovery; expired revalidation blocks restart; operation keys cannot alias different tasks across the goal; vanished help is reported with an integrity issue and not offered as usable; malformed large-integer JSON returns structured exit 2; reconciliation preserves unrelated blockers until revalidation. Existing applied effects can resume verification without redispatch, and stale prerequisites suppress inadmissible verification actions.

The helper remains advisory local bookkeeping. Producer assertions and semantic test coverage need independent review. Provider-specific compensation followed by reapplication may need a new logical operation rather than reuse of a cached provider idempotency key; the ledger's local uniqueness rule alone cannot establish those semantics. Consistently rewritten history, independent runtime limits, scheduler liveness, distributed enforcement and real external recovery remain outside this proof.
