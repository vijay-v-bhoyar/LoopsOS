<!-- Field-by-field LOOP_LOG entry template. Append only, one terminal entry
     per cycle. In governed mode (SKILL.md § 6 Phase 7) a Phase-7 cycle also
     appends one immutable Result: PENDING sentinel BEFORE any external
     effect; REFLECT then appends the terminal entry with Finalizes: pointing
     at it. The sentinel and its finalizer are one logical cycle record —
     never edit either after it's written. -->

## Cycle N — YYYY-MM-DD — <item>
Vision: <first 8 hex of sha256(VISION.md) — display only; the full digest lives in the RunRecord>
Skills: <skills loaded, or none>
Plan: <1–2 lines>
Result: SHIPPED | REVERTED | PARKED | REVIEWED | HALTED | PENDING
        <PENDING appears only on a Phase-7 sentinel; its Finalizes:-bearing
         partner entry carries the terminal Result>
Cause: <CauseCode — pure closed enum, references/contracts.md; REQUIRED on
        REVERTED/PARKED/HALTED, absent otherwise; never carries parameters
        or prose>
Quarantine: <sha256 of the .loop/quarantine/ artifact; REQUIRED iff
             Cause: hostile-input, absent otherwise>
Recovery: pending-recovery <REQUIRED iff this entry was appended by runner
           crash recovery rather than a live REFLECT — orthogonal to Result,
           so a recovered successful deploy is Result: SHIPPED plus this
           field>
Finalizes: <EntryHash of this cycle's PENDING sentinel; REQUIRED on the
            terminal entry of any cycle that wrote a sentinel, absent
            otherwise>
Learned: <1–2 lines — the only free-prose field>
Next candidate: <item>
Prev: <EntryHash of the previous entry; GENESIS for cycle 1>
EntryHash: <sha256 of this entry's canonical bytes, Prev included>

<!-- Machine contract: the header line is exactly
     "## Cycle N — YYYY-MM-DD — <item>" with N = previous terminal-entry N + 1.
     The runner greps ^## Cycle to detect progress; format drift breaks
     unattended operation. The Prev:/EntryHash: chain makes append-only
     checkable — editing any historical entry breaks every subsequent Prev,
     and chain:verify: names the first broken row. -->
