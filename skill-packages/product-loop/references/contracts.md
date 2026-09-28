# Contracts — full schema

The run record is a **derived index, never a second source of truth**.
Authoritative facts live where owners write them (LOOP_LOG, METRICS.md,
verdicts/, GOVERNANCE.md, oversight store). Regeneration from sources must
be byte-identical or the index is wrong — not the sources.

```ts
type Sha256   = string;  // 64-hex lowercase sha256 digest
type GitOid   = string;  // 40-hex git object id (SHA-1 until the repo migrates; typed so migration is a type change, not a grep)
type BundleId = Sha256;  // hash of the canonicalized bundle manifest (agent-release)
// 8-hex prefixes are DISPLAY ONLY (LOOP_LOG readability). State stores full digests.

// Closed cause vocabulary. Prose goes in `Learned:`, never here.
type CauseCode =
  | "gate:tests" | "gate:lint" | "gate:smoke" | "gate:security" | "gate:diff-review"
  | "gate:impact" | "gate:govern"            // Phase 7 ESCALATE-park; the GOVERNANCE row
                                             // carries per-gate detail — CauseCode does not
                                             // duplicate it (one source of truth)
  | "owner-unresolved"                       // composition-map owner missing
  | "flaky" | "missing-infra" | "budget" | "bundle-drift"
  | "context-overflow" | "hostile-input"     // quarantine sha rides the separate
                                             // Quarantine: field, never this enum
  | "rebase-conflict" | "vision-conflict"
  | "needs-human" | "corruption";
// Crash recovery is NOT a cause — a recovered deploy may be Result: SHIPPED, and
// Cause is failed-terminals-only. It is the Recovery: field (see LOOP_LOG.template.md).
// Extending this enum is a behavior change → candidate bundle, not an inline edit.

// Identity = the loop's cycle number. The runner greps `^## Cycle` for liveness;
// a parallel id system is drift.
type RunRecord = {
  cycle: number;                    // == LOOP_LOG "## Cycle N"
  branch: string;                   // loop/* — the loop never commits to main
  visionHash: Sha256;               // FULL sha256(VISION.md); LOOP_LOG shows first 8 hex
  bundleId: BundleId | null;        // agent-release bundle serving this loop agent
  changeSetHash: GitOid | null;     // HEAD of the atomic commit; null until COMMIT
  item: string;                     // backlog id
  itemClass: "bug"|"feature"|"debt"|"infra"|"behavior";
  result: "SHIPPED"|"REVERTED"|"PARKED"|"REVIEWED"|"HALTED";
  cause: CauseCode | null;
  quarantineHash: Sha256 | null;     // required iff cause === "hostile-input"
  recovery: "pending-recovery" | null; // orthogonal to result; set iff runner-recovered
  entryHash: Sha256 | null;          // this LOOP_LOG entry's EntryHash
  finalizesEntryHash: Sha256 | null; // set iff this entry finalizes a PENDING sentinel
  gates: GateEvidenceRef[];
  approvals: ApprovalRef[];
  artifacts: ArtifactRef[];
  budget: BudgetLedger;
  parentCycle: number | null;       // incident-spawned child work
};

type ArtifactRef = {
  type: "diff"|"test_report"|"scan_report"|"eval_verdict"|"trace"|"log_digest"
       |"rollback_proof"|"security_block"|"adr"|"threat_model"|"repro"
       |"approval_token"|"map"|"hostile_input";
  sha256: Sha256;                   // mutation ⇒ hash-check failure ⇒ STALE
  producedBy: { tool: string; version: string };   // a script or scanner — never "the model"
  producedAt: string;               // RFC3339 UTC
  path: string;
  schema: string;                   // e.g. "security-review/Security-block@1"
  trust: "loop"|"human"|"external_quarantined";    // telemetry-sourced text carries the third
};

// Verdicts are NOT re-modeled; the index points at where owners wrote them.
type GateEvidenceRef = {
  gate: "tests"|"lint_typecheck"|"smoke"|"security"|"diff_review"              // VERIFY
      | "evals"|"security_gate"|"rollback_proof"|"blast_class"
      | "freshness"|"rate"|"oversight";                                        // GOVERN
  verdict: string;                  // verbatim from the OWNER'S closed vocabulary — closed per
                                    // owner, open here only because owners differ; a verdict
                                    // absent from the owner's vocabulary is a schema violation
  boundTo: GitOid | BundleId;       // what the verdict cites
  source: ArtifactRef;
};

type ApprovalRef = {                // agent-oversight token machinery
  tokenId: string;
  role: string;                     // from the oversight approval matrix
  payloadHash: GitOid | BundleId;   // what was approved is what activates. Mismatch ⇒ deny. Replay ⇒ deny + event.
  scope: "ga_promotion"|"migration_unpark"|"l3_release"|"risk_acceptance"|"budget_extension";
  singleUse: true;
  consumedAt: string | null;
};

type BudgetLedger = {
  ceiling: { usd: number; tokens: number; wallClockMin: number; cycles: number };
  spent:   { usd: number; tokens: number; wallClockMin: number; cycles: number };
  meteredBy: "runner";              // source: model-gateway per-span cost attribution
  checkpoint: "pre_cycle_admission";// breach parks BEFORE work starts, never mid-gate
  onBreach: { action: "PARK"; needs: "budget_extension" };
  exemptions: ["revert_to_patch","governor_auto_rollback"];  // a reversal in flight always completes
};
```

## Notes for implementers

- `RunRecord`, `ArtifactRef`, `GateEvidenceRef`, `ApprovalRef`, and
  `BudgetLedger` are all **derived** — the `runrecord:emit:` adapter
  (Phase 8) assembles them from LOOP_LOG, verdicts/, GOVERNANCE.md, and the
  oversight store. Never hand-author a RunRecord field that has no source.
- `CauseCode` is closed on purpose. If a new failure mode needs a new code,
  that is a `behavior`-class change: author the enum extension as a
  candidate bundle diff and let it ride agent-release's ladder — never patch
  it in as part of an unrelated cycle.
- `.loop/registry.json` (derived index over tool/model/prompt/skill
  registries + principals) follows the same rule: regenerable
  byte-identical from the four class registries, never authoritative on its
  own.
