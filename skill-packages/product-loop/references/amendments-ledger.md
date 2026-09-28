# Amendments ledger — what changed, and why

This records the amendments folded into product-loop's SKILL.md by the
"Product Loop — Final Composed Specification" pass, so a future audit of the
loop's own history doesn't have to re-derive the reasoning. Everything not
listed here was already law before this pass; the owning skill is cited in
SKILL.md and the composition map.

Ship order for a repo enabling these for the first time: **G1 (bundle zero
resolution) → G2 (kill ladder) → G3 (cycle-prompt budget)** — blocking, in
that order, because an unverified control plane invalidates every other
guarantee — then D3, D4, G4, G5, G6, D2, G7, D1, G8; G9 waits until
production data exists.

| # | Amendment | Lands in | Blocking? |
|---|---|---|---|
| G1 | Bundle zero GA'd; ORIENT hash-verifies the installed control plane; mismatch ⇒ HALT | agent-release + ORIENT (§6 Phase 1) | **Yes** — first unattended run |
| G2 | Loop kill ladder harness-enforced: STOP PreToolUse denial + runner pre-check, wall-clock SIGTERM, container kill, credential revocation; asymmetric resurrection | AGENT-SECURITY.md hooks + runner | **Yes** |
| G3 | Cycle prompt is a prompt-ops asset: slices, budgets, degradation order; overflow ⇒ PARK, never silent truncation | prompt-ops registry + runner | **Yes** |
| D3 | Failing-repro-first for `bug` items; the repro becomes the permanent regression test | PLAN + VERIFY gate 1 | No |
| D4 | Budget ledger + pre-cycle admission; runner-metered from model-gateway attribution; breach parks; reversals exempt | Runner + `.loop/budget.json` | No |
| G4 | Hook set enumerated in AGENT-SECURITY.md; every hook a bundle member | agent-security + bundle manifest | No (folds into G1/G2) |
| G5 | Mechanical self-improvement intake (≥3 same `Cause:` per REVIEW window ⇒ `behavior` item) + loop-bundle shadow/canary semantics | REVIEW + agent-release | No |
| G6 | Deterministic impact check at COMMIT: diff vs declared set + MAP import-graph hop | COMMIT (`impact:check:`) + code-map | No |
| D2 | Code-deploy commit hash as an oversight span attribute (parity with `bundle_id`) | Oversight span schema + deploy-provision post-promote | No |
| G7 | `Prev:` hash chains on LOOP_LOG + GOVERNANCE rows, anchored into the oversight store | Log writers + `chain:verify:` | No |
| D1 | RunRecord derived index emitted in REFLECT, after the LOOP_LOG entry exists; regeneration must be byte-identical or the index is wrong | `runrecord:emit:` + REFLECT (§6 Phase 8) | No |
| G8 | `.loop/registry.json` derived index over tool/model/prompt/skill registries + principals; never authoritative | Adapter script | No |
| G9 | Production-data restore drill as a gate-3 evidence class — deferred until prod data exists | migration-safety evidence schema | Deferred |
| D5 | "PKG" free-text context pointer deleted: structural context is MAP.md; knowledge context is the retrieval-engineering corpus register | Contracts (§4) | Done |

## Why the LOOP_LOG entry grew fields

The entry format in `assets/LOOP_LOG.template.md` gained `Quarantine:`,
`Recovery:`, `Finalizes:`, `Prev:`, and `EntryHash:` across several rounds of
adversarial review of this spec. The pattern worth remembering for future
amendments: **each new mechanism implied a schema consequence that wasn't
propagated everywhere it needed to land** — a halt path that quarantines
raw text needs a field to point at it (`Quarantine:`) so `Cause` can stay a
pure closed enum; a sentinel that can never be edited in place needs a
separate finalizing entry (`Finalizes:`) rather than a mutated row; a crash
that recovers a cycle needs a field orthogonal to `Result` (`Recovery:`),
because `Cause` is failed-terminals-only and a recovered successful deploy
is still `Result: SHIPPED`. **When extending this skill's machinery, grep
every changed term and every field the new machinery implies across the
whole SKILL.md and its references before closing the edit** — that's a
consistency check, not a judgment call, and skipping it is exactly the
defect class this ledger exists to prevent from recurring.

## What was rejected

- Quarantine-*instead of*-halt for gate-targeting imperatives: those still
  halt, with the raw text quarantined (§2). Telemetry text is
  quarantine-and-continue; the difference is targeting, not the presence of
  suspicious language.
- Control-plane scope expansion beyond what bundle zero (G1) actually needs
  to verify.
