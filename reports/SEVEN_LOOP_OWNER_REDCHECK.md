# Independent owner-ledger redcheck

Result: **PASS for eight bounded local structural cases; no reproduced defect.** This is not authenticated approval, independent-person verification, parent acceptance, or production evidence.

The reviewer derived cases from the three owner SKILLs, their new ledger scripts, `evidence_io.py`, and repair/finding/vision/evidence references. Author reports, intended test scripts and evaluation cases were not opened. Skill source was read only; all fixture mutations remained beneath `output/seven-loop-owner-redcheck*`. No cloud or global installation writes occurred.

## Evidence

Run on 2026-09-13 with the bundled Python executable:

```powershell
& 'C:/Users/vijay/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B output/seven-loop-owner-redcheck.py
```

The run passed 8/8 case groups and exercised 62 fresh ledger CLI processes. Receipt outputs came from actual local Python assertion probes against versioned JSON source snapshots. Original probes deliberately failed on values 1 and 0 and passed after correction to 2; the adjacent regression probe asserted integer type and positive value. Fixture decision artifacts explicitly disclaim actual founder authority.

| Case | Discriminating sequence and oracle | Observed |
|---|---|---|
| 1. Build lifecycle across revisions | Persist v1 failure, owned help, v2 repair and verification. Reopen on v3 source regression; repair v4. Earlier failure must remain pending until independently rerun in the current subject. Preserve all nine events and cumulative counts. | PASS: readiness withdrew with subject drift; second repair alone left f1 pending. Reverification restored `PARENT_REVIEW_READY`; `parent_complete` remained false. |
| 2. Repair budget across processes | With limit 2, append two repair events for one failure, then attempt a third using a fresh process. | PASS: third append rejected with `repair attempt cap reached`; stored bytes unchanged; count stayed 2. |
| 3. Finding independence and reopening | Reject a verification naming the repair owner; accept named distinct verifier receipts; then append failed reproduction under the same ID after changed source. | PASS: self-verification rejected; structural closure readiness never set `closed` true; failed retest returned `FINDING_OPEN` and empty verified criteria. |
| 4. Original oracle and changed scope | Substitute the regression oracle as the original oracle; omit repaired artifact from regression receipt; then submit coherent receipts. | PASS: changed original oracle and omitted artifact rejected without record mutation; coherent version reached closure review readiness. |
| 5. Partial strategic acceptance | a1 affects c1/c2, a2 affects c2. Run a1 without decision, attempt wrong owner, accept a1, defer a2, then accept a2. | PASS: experiment alone accepted nothing; wrong owner rejected; c1 alone accepted until a2 accepted. All-ready output retained `execution_authorized: false`. |
| 6. New experiment and stale decision | Accept both assumptions, repeat a1 experiment with byte-identical output, then change subject after recording renewed decision. | PASS: new experiment invalidated its previous decision despite identical output hash. Subject revision change withdrew both accepted criteria. |
| 7. Atomic append and artifact integrity | Pre-create another writer's lock, attempt append, recover fixture lock explicitly, submit malformed event, append valid history, tamper tested artifact, then restore original bytes. | PASS: competing lock preserved; rejected append left bytes unchanged and removed only its own acquired lock; tamper rejected; restored artifact recovered readiness. |
| 8. Time and assertion validation | Submit future-dated original receipt, zero assertions, expired original/regression receipts, then current valid receipts. | PASS: future and zero-assertion append rejected; expired history retained but stayed pending; current receipts restored readiness. |

Retained artifacts:

- `output/seven-loop-owner-redcheck.py`: independent reproducible harness, with no imports from author tests.
- `output/seven-loop-owner-redcheck-evidence/results.json`: group outcomes.
- `output/seven-loop-owner-redcheck-evidence/commands.json`: every CLI argument array, exit code, stdout and stderr.
- `output/seven-loop-owner-redcheck-evidence/01-*` through `08-*`: source snapshots, probes, direct outputs, event files and persistent records.
- `output/seven-loop-owner-redcheck-source-hashes.json`: reviewed script hashes. All three vendored evidence helpers have SHA256 `325b92a928050a0f491112fddf2ff455806b850b65afa4f5fd93a342abbbe8a9`.

## Limits

The harness supplies the current subject and actor labels as local fixture data. It verifies mechanical binding, event behavior, and honest readiness boundaries. The host still owns real identity authentication, founder authority, exact accepted goal and criteria, mapping archived snapshots to actual source/runtime, semantic adequacy of the oracle, external evidence, and final integrated acceptance. The ordinary lock exclusion probe is not a hostile filesystem race or network-filesystem concurrency test. No finding or owner upgrade request is warranted by these eight cases.
