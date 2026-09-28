# Independent local runtime redcheck

Initial challenge date: 2026-09-13. Scope: lifecycle scheduler, progress ledger and migration, portable cycle adapter and agentic guard, cooperative local fleet runtime. Challenges were derived from raw implementation before reading any author tests or reports. All executions used new local fixtures under `output/seven-loop-runtime-redcheck`; actual Python, Git, SQLite and Windows processes were used. No provider, cloud, external messages, installed skill writes or package edits were performed by this reviewer.

## Initial findings

### RRC-01 — High: scheduler completion accepts a different acceptance contract

`local_scheduler.complete` compares only the goal ID between scheduled configuration and verified progress state. A real schedule with `parent_goal.criteria=["hard-acceptance"]` was completed by a independently initialized and verified progress ledger covering `["easy-acceptance"]`, for `different-product/different-target/r1/c1`. The unchanged goal ID was sufficient. Every local integrity check passed and the scheduler became `COMPLETED`, preventing further delivery without satisfying its scheduled acceptance contract.

This is a structural binding defect, independent of whether the local reviewer identity or artifact semantics are authenticated. Expected repair: compare exact parent criteria and a documented mapping from the scheduled repository/configuration to the progress subject; validate current repository/configuration before final completion.

Reproduction: `output/seven-loop-runtime-redcheck/challenge.py`, case `completion_rejects_wrong_criteria_subject`. Original recorded result: `output/seven-loop-runtime-redcheck/run-1789331298703760600/results.json` and repeated in `run-1789331357298935200/results.json`.

### RRC-02 — Medium: integration discards fractional remaining time

`fleet_runtime.integrate` computes `int(plan["seconds"] - elapsed)`, whereas the process runner initially accepts only integer durations. An admitted one-second integration with a real first command sleeping 0.15 seconds and a real second command asserting an output artifact fails with `integration total duration exhausted` before verification, despite substantial time remaining. The integration reservation remains charged and the state becomes permanently `failed`. A one-command one-second plan can pass depending on Windows monotonic clock granularity, so a two-command case is discriminating.

Expected repair: retain positive finite fractional remaining time through the runner while leaving integer credit limits unchanged.

Reproduction: `output/seven-loop-runtime-redcheck/challenge.py`, case `fleet_preserves_fractional_remaining_time`. Recorded result: `output/seven-loop-runtime-redcheck/run-1789331357298935200/results.json`.

## Initial executable evidence

Command (from repository root):

```powershell
& 'C:/Users/vijay/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B output/seven-loop-runtime-redcheck/challenge.py
```

The bounded independent suite produced 16 cases: 14 passed and the two findings above failed.

| Case | Initial result |
|---|---|
| Agentic guard and cycle adapter admit the same real pinned configuration | Pass |
| Both admission surfaces reject STOP | Pass |
| Two scheduler processes claim a due job only once | Pass |
| Duplicate goal cannot create a fresh budget in the same database | Pass |
| Dispatch count and wall reservations remain exhausted across ticks | Pass |
| Cancellation stops the owned dispatch and prevents delayed output | Pass |
| New cycle configuration/state cannot reset outer scheduler reservations | Pass |
| Completion rejects different progress criteria/subject with same goal ID | **Fail: RRC-01** |
| Changed evidence artifact invalidates verified progress | Pass |
| Reviewed limit migration preserves counters/work and is idempotent | Pass |
| Help delivery deduplicates; conflicting response cannot overwrite history | Pass |
| One-command, one-second integration can complete | Pass |
| Changed worker artifact blocks integration before acceptance | Pass |
| Two-command integration retains fractional remaining budget | **Fail: RRC-02** |
| Killing scheduler and restarting does not reclaim unresolved work | Pass |
| Two real workers run successfully in separate declared directories | Pass |

The crash case retained scheduler `RUNNING`, one dispatch and eight reserved seconds after restart, while the separately bounded cycle eventually recorded its own timeout. This is fail-closed preservation, not automatic recovery. The parallel fleet case charged four credits and recorded both actual output hashes. Local receipts remain integrity evidence only; no run establishes authenticated authority, hosted availability or production acceptance.

## Additional source observation

The product cycle adapter initially used Windows Job kill-on-close but did not query that all descendant processes had exited before clearing its active reservation. The fleet adapter did query `ActiveProcesses == 0`. This observation was communicated to the parent reviewer for repair; it is not counted as an independently reproduced descendant survival defect in the 16 cases above.

## Repair verification

Both reproduced defects were repaired by the parent/team and independently rerun. RRC-01 now rejects the mismatched criteria fixture with `scheduled acceptance criteria mismatch`. An additional correctly bound progress ledger with the exact parent criteria and repository/local-process/HEAD/config-file-hash subject completed successfully; subsequent scheduling returned `NO_DUE_WORK`. RRC-02 now executes both the 0.15-second preparation and final artifact assertion inside the one-second integration budget and records `INTEGRATED_LOCALLY`.

The final frozen-source rerun produced **18/18 passing independent cases**, including the original 16, valid completion acceptance, and an actual successful cycle that launches a descendant before reporting. The descendant wrote its startup marker, then was prevented from writing its delayed output; the cycle successfully returned and cleared its active reservation. This validates ordinary Windows descendant cleanup on this host; forced API failure and hostile process escape are outside this independent case.

Final evidence: `output/seven-loop-runtime-redcheck/run-1789331547634617900/results.json`; exact source fingerprints: `output/seven-loop-runtime-redcheck/run-1789331547634617900/source-pins.json`. Console capture: `output/seven-loop-runtime-redcheck/final-run.log`.

| Source | Final SHA-256 |
|---|---|
| progress_state.py | `99fd31d8ed03d9db5bd6ecc1a171921bf57d047fa4707748982384bf39a63aa3` |
| local_scheduler.py | `b07d31d30d7c7fd42ddd9edcef6079175e9de01b006dba07b2f9771eb16e13ed` |
| migrate_state.py | `0fd654a5284d1613b183f0c46ebde62e321d1e3a3db3be713a0bb14a5ec404b0` |
| cycle_adapter.py | `2c64347a28a70e115c45b9bdcc0a75c8217d2c38eb6db8e8f27fe667cd60783f` |
| fleet_runtime.py | `dbcf1c7bd6b64b6245f8f95af0bc743754227f159b362239e037e47772ca8ff0` |
| loop_guard.py | `7a0ecd453854741c80503ff432b853e95de3da8d493f7700fcae669706deba3c` |

No reproduced defect remains open within this bounded independent local review. These results do not establish authenticated approval, semantic correctness of arbitrary caller-provided commands, provider enforcement, cross-host availability, or production readiness.

### Final STOP-race repair rerun

After the parent suite identified a narrow STOP-during-final-admission classification and stdin-cleanup issue, the independent 18-case harness was rerun against the repaired adapter and aligned guard. **18/18 passed**. This rerun preserves the independent scope above; the deterministic timing-specific STOP regression itself belongs to the parent suite.

The latest evidence supersedes the preceding final-run source binding: `output/seven-loop-runtime-redcheck/run-1789331697207277100/results.json`, `source-pins.json`, and `output/seven-loop-runtime-redcheck/final-stop-race-run.log`.

Updated cycle adapter SHA-256: `e1fee0004fbae6dd12302fdcf53cb6e1fb0f05b154f2f6d3eb03777b6e254468`. Updated guard SHA-256: `3afe300728a494b74667964c0c1356f5804eb848a7dcd2ba482727ad0bcc29fc`. The other four reviewed module hashes remain identical to the table above.
