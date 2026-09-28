# Executive method and retained data contracts

Read alongside [the current skill](../SKILL.md) and [adaptive review](adaptive-method.md).
`../rules.json` is the current executable rubric. Its D6 evolution gates and
integrity checks supersede older broad future-resilience wording below. Use
[the current runbook](../PIPELINE.md) for command paths and reassessment mechanics.
A valid JSON record is not authenticated evidence or a guarantee of correctness.

# product-diligence

Executive diligence for built AI products, run as a register-first pipeline: sweep once, verdict many, challenge, reconcile, render — then loop on artifact diffs. Verdicts are functions of a cited register, never prose judgment. The scripts check the listed structural contracts; the reviewer still assesses semantic support and completeness. Missing evidence must remain explicit.

## Failure model

Ad-hoc executive review of an AI product fails in these modes. Each maps to the invariant that kills it.

- **F1 Finding sprawl.** The same defect rediscovered and re-worded per review question; dedup-by-instruction fails. → INV-1
- **F2 Vibes verdicts.** Verdict enums with no derivation rule; two runs, two answers. → INV-7
- **F3 Severity inflation.** "Can cause" modality makes every conceivable issue Critical; one-Critical-blocks-all then collapses every verdict to "not ready" and the review stops discriminating. → INV-4
- **F4 Paper overclaim.** Runtime properties (injection resistance, tool abuse) "assessed" from documents; passes issued that only a live probe can issue. → INV-5
- **F5 Fake precision.** Invented owners, dates, dollar figures, page citations, and proof steps. → INV-3, INV-10, INV-11
- **F6 Performative critique.** A self-critique pass that cannot see the evidence and cannot change a verdict. → INV-9
- **F7 Coverage blindness.** Full analysis run on 3 of 21 artifacts, emitting sprawling "evidence missing" prose instead of declining. → INV-8
- **F8 Discovery truncation.** A top-N cap applied at analysis time silently drops finding N+1, possibly Critical. → INV-2
- **F9 One-shot rot.** No finding lifecycle; "temporarily accepted" risks become permanent; every re-review restarts from zero. → INV-12, INV-13
- **F10 Fleet duplication.** Shallow inline re-implementation of red-teaming, moat review, and security scanning the fleet already owns. → Composition

## Pipeline

Phase 0 intake & admission → Phase 1 finding sweep → Phase 2 verdict lenses → Phase 3 adversarial challenge → Phase 4 reconciliation & render. Re-runs enter Phase 0 in diff mode. All state lives under `.diligence/` (Defaults).

### Phase 0 — Intake & admission

1. Catalog supplied artifacts against the checklist below. Assign IDs, sha256-hash each, and record in `.diligence/manifest.json` with per-pass model pins and the supplied optional params: **owner roster**, **release calendar**, **valuation params** — all absent by default. Extra artifacts get free IDs A-22+.

| ID | Artifact | ID | Artifact |
|---|---|---|---|
| A-01 | Product brief / PRD | A-12 | Deployment diagram / IaC |
| A-02 | User journeys & core UX flows | A-13 | CI/CD & build configuration |
| A-03 | Architecture diagram & topology | A-14 | Test suites & coverage reports |
| A-04 | Source code / repository map | A-15 | Model eval results |
| A-05 | API contracts & integrations | A-16 | Observability / logging / audit samples |
| A-06 | AuthN & authZ design | A-17 | Incident response & rollback runbooks |
| A-07 | Tenant isolation / data boundary spec | A-18 | Support & escalation workflows |
| A-08 | Data model & DB schema | A-19 | Cost model / unit economics |
| A-09 | RAG / retrieval architecture | A-20 | Customer proof & feedback logs |
| A-10 | Tool / action / function manifest | A-21 | Regulatory & compliance requirements |
| A-11 | System prompts, guardrails, policy files | | |

2. **Admission.** Per lens, coverage = |present ∩ relevant(D)| / |relevant(D)|. A lens below its floor (Defaults) is skipped and outputs exactly one line: `D<n> skipped: missing <artifact IDs>`. No partial analysis below floor.
3. **Diff mode** (re-run): archive the previous state. Changed or removed artifacts, model/configuration identity, rules or prompts conservatively mark all rows pending reassessment. Explicitly revalidate each stable ID and obtain a fresh challenge receipt before rendering. See the current runbook.

### Phase 1 — Finding sweep

One systematic pass over the full surface. Surface = layers ∪ adversarial vectors ∪ strategic vectors:

**Layers (L01–L20):** L01 product/business workflow · L02 UX/adoption · L03 frontend · L04 API · L05 backend services · L06 data · L07 identity · L08 authorization · L09 tenant isolation · L10 agent orchestration · L11 prompt/policy · L12 tool execution · L13 RAG/retrieval · L14 file ingestion · L15 security · L16 observability · L17 audit/compliance · L18 testing/evaluation · L19 CI/CD & release · L20 operations/support.

**Adversarial vectors (V-01–V-15):** V-01 prompt injection (direct/indirect) · V-02 RAG/retrieval poisoning · V-03 hostile file uploads/ingestion · V-04 tool abuse & privilege escalation · V-05 over-permissioned identities/service accounts · V-06 cross-tenant access · V-07 sensitive data in logs/telemetry · V-08 hallucination-driven unsafe output / over-trusting unverified outputs · V-09 provider/model failure & timeout handling · V-10 admin privilege misuse · V-11 cost runaway / denial-of-wallet · V-12 autonomy control gaps (approval gates, kill switch, loop bounds) · V-13 cross-agent manipulation · V-14 user error paths · V-15 crypto agility / long-lived secret exposure.

**Strategic vectors (S-01–S-11):** S-01 workflow pain severity & measurable business value · S-02 labor replacement vs surface assistance · S-03 agentic depth vs hardcoded prompt chains · S-04 durable data/platform advantage · S-05 workflow lock-in · S-06 trust/compliance advantage · S-07 survival vs hyperscaler native features · S-08 COGS / unit economics · S-09 IP ownership · S-10 enterprise buyer proof · plus S-11 model commoditization / defensibility erosion.

**Mandatory controls** (cited absence of any is Critical-eligible): MC-1 authN on every externally reachable surface · MC-2 tenant predicate on every multi-tenant data/RAG query path · MC-3 authZ check on every tool/action invocation · MC-4 no secrets in code, repo config, or logs · MC-5 approval gate on irreversible or externally visible agent actions · MC-6 audit record on privileged and agent actions · MC-7 kill/stop control and loop bounds for autonomous execution.

Sweep rules:

- **Exhaustive.** Every surface cell is visited; there is no cap on findings. Caps exist only at rendering (D3).
- **Typed rows.** Every finding is `risk | strength | unknown`, appended to `.diligence/register.jsonl` per the row schema below.
- **Dedup at write.** `fingerprint = sha256(primary_surface + impact_class + primary_citation_target)`, normalized. Exact restatements auto-merge (extend the existing row's `surface`/`dimensions`; never a second row). A reworded restatement that shares an impact class and citation target but not a fingerprint is surfaced at ingest as an operator-confirmed merge candidate, not silently merged — auto-merging on citation alone would wrongly collapse distinct issues citing one source. Lenses cross-reference by row ID only.
- **Evidence or unknown.** A risk requires a citation for the exploit path, or for the surveyed absence of a mandatory control (cite the artifact that should contain the control and the location that shows it doesn't). No citation → the cell yields `unknown`, not a risk.
- **Verifiability tag mandatory:** `design | test-report | live-probe-only`. A live-probe-only cell without a supplied test-report artifact emits `unknown` with a delegation note (ai-red-team). Probe results are never simulated or inferred.
- **Depth delegation.** Where AGENT-SECURITY.md, AGENT-DESIGN.md, a moat-reviewer scorecard, security-review blocks, or an ai-red-team suite is supplied, consume it as evidence. Where absent and the layer warrants depth, record `unknown` plus a recommendation to run the owning skill. Never shallow-duplicate the fleet inline.
- **Recall ensemble (off by default).** Optional re-sweeps under red-team and CTO personas; all writes pass through the same fingerprint dedup.

### Severity rubric

Severity = impact class × **evidenced** exploitability. Severity never exceeds what the evidence mode supports.

| Severity | Requires | Impact classes | Release impact |
|---|---|---|---|
| Critical | `cited-exploit` (cited exploit path) OR `cited-absent-control` (cited absence of MC-1..7) | cross-tenant data exposure, unauthorized action execution, legal exposure, total core-workflow failure | Blocks beta and production |
| High | Cited evidence of a customer-visible failure or security weakness with bounded blast radius; OR Critical impact class with plausible-but-uncited path (`asserted` caps here) | as above with bounded radius, major reliability gap, expensive operational risk | Blocks beta unless a **verified** compensating control exists |
| Medium | Cited capability/architecture gap; limited blast radius or cited manual workaround | capability gap | Ships to beta with a documented, cited mitigation plan |
| Low | Cited | polish, minor friction, internal docs | Does not block |

**Verified compensating control** = cited existence in an artifact AND a supplied test result exercising it. Both required. Model-declared controls are unverified and lift nothing.

### Phase 2 — Verdict lenses

Each lens D1–D6 is a function (register rows tagged to its dimension, coverage) → verdict record. Rules evaluate in order; first match wins. The derivation logs rule ID + row IDs; the checker re-derives from the same tables and must match. A lens with `unknown`-majority on its relevant surface, or whose non-`unknown` rows support no rule, emits `Undetermined`.

**D1 — Beta readiness** (over D1-tagged open risk rows)

| # | Condition | Verdict |
|---|---|---|
| 1.1 | any Critical | Not ready for external users |
| 1.2 | any High without verified compensating control | Demo-ready only |
| 1.3 | any High (compensated) or any Medium without a cited mitigation plan | Beta-ready with conditions |
| 1.4 | else | Beta-ready |

**D2 — Enterprise maturity.** Per-layer grade = min(citation-supported grade, cap from worst open risk on the layer): Critical → Broken; High uncompensated → Demo; High compensated or Medium → Beta; clean → Production-eligible. Any grade above Demo requires ≥1 cited `strength` row on that layer, else Evidence-missing. Core layers: {L06, L07, L08, L09, L12}.

| # | Condition | Verdict |
|---|---|---|
| 2.1 | ≥8 layers Evidence-missing | Not enough evidence to determine |
| 2.2 | any layer Broken | Prototype-grade |
| 2.3 | any core layer ≤ Demo | Demo-grade only |
| 2.4 | all 20 layers Production | Enterprise production-grade |
| 2.5 | all core layers ≥ Beta AND ≥15 layers ≥ Beta | Enterprise beta-grade |
| 2.6 | else | Demo-grade only |

**D3 — Red team.** Rendering lens, no verdict enum. Renders the top K=7 **open** risks by (severity, impact class): exploit/failure path, business + customer impact, detection method, prevention method, required proof per the proof taxonomy with a named target artifact. Presentation cap only; the register holds everything.

**D4 — Acquisition diligence.** Two modes. Valuation params absent (default): posture mode, no buy verdicts, no dollar figures anywhere.

| # | Condition | Posture |
|---|---|---|
| 4.1 | any open Critical | diligence-fail |
| 4.2 | any open High uncompensated on L09/L15/V-06 or S-09 | conditional-pass |
| 4.3 | else | diligence-pass |

Valuation params supplied (anchor, revenue/margin/retention data): full enum with caps. Haircut rationale must cite row IDs.

| # | Condition | Verdict |
|---|---|---|
| 4.4 | open Critical on L09 or V-06 (tenant breach) | Do not buy |
| 4.5 | any other open Critical | Buy only for team/IP (hard cap) |
| 4.6 | open High uncompensated on security, S-09 IP, or cited S-08 cost runaway | Buy with major valuation haircut |
| 4.7 | no cited S-03 agentic-depth strength rows (wrapper) | Partner instead of buy |
| 4.8 | else | Buy at full valuation |

**D5 — Category / moat.** Consumes a supplied moat-reviewer scorecard as first-class evidence; else grades from S-tagged rows.

| # | Condition | Verdict |
|---|---|---|
| 5.1 | no cited strength rows on any of S-04/S-05/S-06 | Pure AI wrapper |
| 5.2 | open High+ uncompensated on S-07 or S-11 | High risk of obsolescence |
| 5.3 | no cited strength rows on S-01/S-02 (value/replacement unproven) | Feature-level product |
| 5.4 | else | Category-defining potential |

**D6 — Resilience within evaluated scope**

| Order | Condition | Verdict |
|---|---|---|
| 6.1 / 6.1a | Evidenced autonomy control failure plus obsolescence risk, or High+ S-11 risk | High risk of obsolescence |
| 6.2 / 6.2a | Evidenced control/autonomy failure or High+ evolution E-01..E-08 risk | Needs core adaptation |
| Evolution missing | Required model-evolution evidence absent | Undetermined |
| Evolution invalid | Supplied evidence fails validity or capability requirements | Needs core adaptation; render blocked until evidence repaired |
| 6.3 | Cited MC-5..7/V-12 strengths, qualified evolution evidence and sufficient current coverage | Resilient within evaluated scope |
| Otherwise | No positive rule supported | Undetermined or Needs core adaptation per rules.json |

The machine rules are authoritative. Qualified upgrade capability does not mean
that a new candidate qualifies, that its receipts are authenticated, or that an
upgrade has been deployed. Known blockers are evaluated before positive strengths.

### Phase 3 — Adversarial challenge

Fresh context, de-correlated from the sweep: different model pin preferred; else same model, fresh seed, hostile system role. De-correlation method recorded in the manifest. **Input = artifacts + register + verdict records** — the challenger sees the evidence, not just the conclusions. Output = typed challenges to `.diligence/challenges.jsonl`; free-prose critique is discarded.

Challenge types, each targeting a row ID or lens ID: `unsupported` (verdict/row exceeds its citations) · `excused` (severity or grade downgraded without evidence) · `speculative` (claim with no citation) · `reversing-artifact` (names a missing artifact whose content would flip a verdict) · `missed` (surface cell with available evidence the sweep didn't log).

Generation prompts (the six original critique vectors, retargeted at IDs): least-supported verdict; readiness claim that fails deep enterprise diligence; blocker downgraded too easily; missing artifact that reverses a positive verdict; what a hostile security reviewer flat-out rejects; what a skeptical CFO calls demo theater.

### Phase 4 — Reconciliation & render

1. Every challenge gets a resolution: `upheld` (counter-citation required) · `revised` (row/verdict updated; history appended) · `accepted` (target verdict downgraded one level and/or confidence dropped one band). An unresolved challenge is auto-`accepted` — fail closed.
2. Recompute all lenses (pure functions; cheap).
3. Run `../diligence_check.py`. Red → fix and re-run. **The scorecard must not render on red.**
4. Render the unified scorecard + register view + per-lens sections. Route through stakeholder-brief when available (pointer ledger; acceptance decisions bind to row content hashes). Rendering locally, apply the same discipline: every scorecard cell cites row IDs; every number cites an artifact or a supplied param.

Scorecard columns: Dimension | Verdict | Score | Confidence | Top blocker (row ID). Score is a fixed map from verdict — never independently judged:

| Lens | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| D1 | Not ready | Demo-ready only | — | Beta w/ conditions | Beta-ready |
| D2 | Prototype | Demo | — | Beta | Production |
| D3 (Security & Safety) | open Critical | open High uncomp. | open High comp. | Medium only | clean |
| D4 posture / valuation | fail / Do not buy | — / team-IP | conditional / haircut·partner | — | pass / full |
| D5 | Wrapper | Obsolescence risk | Feature-level | — | Category-defining |
| D6 | Obsolescence risk | — | Needs adaptation | — | Resilient within evaluated scope |

`Undetermined` renders "–", no score. Confidence = coverage band (Defaults), dropped one band if any challenge on that lens resolved `accepted`. Plans render Now / Next / Later unless a release calendar was supplied; dates only from the calendar; owners only from the roster or `Owner unknown`.

### Finding lifecycle & loop semantics

`open → fixed-pending-proof → closed`, or `open → accepted`. This lifecycle is a **risk-row concept**. Strength and unknown rows carry the same `status` field for schema uniformity but are always treated as live evidence — nothing transitions them to `closed`/`accepted`, and no consumer (challenge payload, rederivation, rendering) filters them out regardless of value.

- **closed** requires an executed proof record: probe output (named target artifact + output hash) or a supplied test-report artifact. Critical rows never close on `manual-attestation`.
- **accepted** requires roster owner + expiry + revisit trigger. Any missing → the row stays open; "temporarily accepted" cannot become permanent. Expired acceptance reverts to open at the next run.
- Reruns archive prior state; explicit revalidation preserves the row ID and embeds previous evidence in history. The mutable local JSON files are not an authenticated append-only ledger.
- Re-run = Phase 0 diff mode; scorecard version increments; each manifest records the prior manifest hash (chained).
- Because settlement is risk-scoped and explicit, the challenge phase can safely summarize closed/accepted risk rows by count instead of re-embedding them every cycle — their structural proof was recorded; their semantic validity and acceptance can still be challenged — while every strength, unknown, and still-open risk stays fully visible (../PIPELINE.md has the measured payload-size effect).

## Data contracts

Machine truth is JSONL under `.diligence/`; every `.md` view is rendered from it, never hand-edited.

Register row (`register.jsonl`):

```json
{"id":"R-014","type":"risk","title":"No tenant predicate on vector queries","statement":"...","surface":["L09","V-06"],"dimensions":["D1","D2","D3","D4"],"severity":"critical","impact_class":"data-exposure","evidence_mode":"cited-absent-control","control":"MC-2","citations":["A-04:src/query_vectors.py#L40-L62","A-07:sec-3.2"],"verifiability":"design","compensating_control":null,"mitigation":null,"fingerprint":"sha256:...","status":"open","proof":null,"acceptance":null,"history":[{"run":"run-003","event":"created"}]}
```

Field domains: `type ∈ {risk, strength, unknown}` · `severity ∈ {critical, high, medium, low, null}` · `evidence_mode ∈ {cited-exploit, cited-absent-control, cited-strength, asserted, missing}` · `control ∈ {MC-1..MC-7, null}` (required when `evidence_mode = cited-absent-control`, or on a strength asserting a control is present) · `verifiability ∈ {design, test-report, live-probe-only}` · `status ∈ {open, fixed-pending-proof, closed, accepted}` · `proof.type ∈ {probe, test-report, manual-attestation}` · `compensating_control = {"cited":"A-nn:loc","test":"A-nn:test-name"} | null` · `mitigation = "A-nn:loc" | null` (a cited Medium mitigation plan, read by D1 rule 1.3) · `acceptance = {"owner":"<roster>","expiry":"<date>","revisit_trigger":"..."} | null`.

Verdict record (`verdicts.jsonl`): `{"lens":"D1","verdict":"Demo-ready only","rule":"1.2","rows":["R-014","R-021"],"coverage":0.72,"confidence":"medium","version":3}`

Challenge record (`challenges.jsonl`): `{"id":"C-03","target":"R-014","type":"excused","statement":"...","citation":"A-14:test_tenant_scope","resolution":{"kind":"revised","delta":"severity high→critical"}}`

Manifest (`manifest.json`): artifact IDs → {path, sha256, checklist slot}; supplied params (roster, calendar, valuation); per-pass model pins; prior-manifest hash; run ID.

**Citation schema:** `A-nn:locator` — code `path#Lstart-Lend`; documents `section or page`; reports `test-or-check name`. Absence citations point at the artifact surveyed and the location demonstrating absence.

## Invariants

- **INV-1** One register. Every finding is written once; lenses and rendered sections cross-reference by row ID only. Fingerprint dedup (`impact_class` + primary citation target) auto-merges exact restatements at write time; a reworded restatement that shares an impact class and citation target but not a fingerprint is surfaced at ingest as an operator-confirmed merge candidate rather than silently merged (auto-merging on citation alone would wrongly collapse distinct issues citing one source).
- **INV-2** The sweep is exhaustive over the declared surface. Caps (D3 top-K) apply to presentation only, never discovery.
- **INV-3** Every risk row carries citations for the exploit path or the surveyed absence of a mandatory control. Uncitable → recorded as `unknown`, never as a risk, never as a pass.
- **INV-4** Severity never exceeds evidence: Critical requires `cited-exploit` or `cited-absent-control`; `asserted` caps at High.
- **INV-5** Verifiability tags are mandatory. Live-probe-only cells without supplied test reports emit `unknown` + delegation to ai-red-team. Probe results are never simulated.
- **INV-6** A compensating control lifts a block only when cited AND exercised by a supplied test result.
- **INV-7** Verdicts are derived, not judged: rule tables only; every verdict record logs rule ID + row IDs; the checker re-derives and any mismatch is red.
- **INV-8** No lens runs below its artifact floor; a skipped lens outputs one line naming the missing artifacts. No verdict exceeds what non-`unknown` rows support; `unknown`-majority → `Undetermined`.
- **INV-9** The challenge pass sees artifacts + register + verdicts, is de-correlated from the sweep, and emits typed ID-targeted challenges. Every challenge is resolved; unresolved auto-resolves as `accepted` (downgrade).
- **INV-10** No invented facts: owners ∈ roster ∪ {"Owner unknown"}; dates only from a supplied calendar (else Now/Next/Later); currency, latency, and percentage figures only with a citation or supplied param. Checker-enforced, not prose-enforced.
- **INV-11** Proof taxonomy enforced: probes name their target artifact; Critical rows close only on `probe` or `test-report`.
- **INV-12** Lifecycle is append-only. `closed` requires an executed proof record; `accepted` requires owner + expiry + revisit trigger; expired acceptance reopens.
- **INV-13** Re-runs are artifact diffs: only rows citing changed artifacts, plus affected `unknown` rows, re-enter the sweep; the rest carry forward; scorecards are versioned and manifests chained.
- **INV-14** The scorecard renders only on checker green; every cell traces to row IDs; per-pass model pins are recorded in the manifest.
- **INV-15** Artifacts exceeding the per-artifact size cap are truncated with a disclosed, sized marker stating how much was omitted — never silently — and a total sweep payload over the size threshold is flagged before the sweep runs, with grouped (chunked) sweeps offered as the mitigation. This is a generation-time guarantee, verified by inspecting the payload file the sweep/challenge builders produce; it is not part of the P1–P11 register checker, which has no visibility into transient payload construction and is not claimed to cover it.

## Defaults

| Parameter | Default | Notes |
|---|---|---|
| State directory | `.diligence/` | register.jsonl, verdicts.jsonl, challenges.jsonl, manifest.json + rendered views |
| Owner roster / release calendar / valuation params | absent | Absent → "Owner unknown" / Now-Next-Later / D4 posture mode. Never inferred. |
| D1 floor | {A-02, A-06, A-10, A-16} + (A-07 ∨ A-08) | relevant += {A-01, A-09, A-11, A-14, A-17, A-18} |
| D2 floor | {A-03, A-04, A-06} AND ≥10/21 present | relevant = all 21 |
| D3 floor | {A-06, A-10, A-11} + (A-04 ∨ A-09) | relevant += {A-03, A-07, A-08, A-16, A-19} |
| D4 floor | D2 floor + A-19 | valuation-mode verdicts additionally require valuation params |
| D5 floor | {A-01, A-20} + (A-09 ∨ A-10) | a supplied moat-reviewer scorecard substitutes for the parenthesized pair |
| D6 floor | {A-10, A-11} + (A-06 ∨ A-12) | relevant += {A-09, A-15, A-16, A-17} |
| Confidence bands | High ≥0.80 · Medium 0.50–0.79 · Low <0.50 | −1 band per lens with an `accepted` challenge |
| D2 thresholds | evidence-missing ≥8; beta breadth ≥15; core = {L06,L07,L08,L09,L12} | |
| D3 render cap | 7 | presentation only (INV-2) |
| Recall ensemble | off | on = red-team + CTO persona re-sweeps through the same dedup |
| Challenge budget | ≤12 typed challenges | quality over volume; targets must be IDs |
| Challenge de-correlation | different model pin | fallback: same model, fresh seed, hostile system role; method recorded |
| Proof types | probe · test-report · manual-attestation | manual-attestation invalid for Critical closure |
| Acceptance fields | owner + expiry + revisit trigger, all required | no defaults; missing any → row stays open |
| Model pins | required per pass in manifest | no default |
| Per-artifact size cap | ~10K tokens (`MAX_ARTIFACT_CHARS` 40 000 chars) | exceed → disclosed sized truncation marker (INV-15); pre-excerpt to remove the gap |
| Sweep warn threshold | ~15K tokens (`SWEEP_WARN_CHARS` 60 000 chars) | single-call payload over this → `sweep-payload` warns, points at `sweep-groups` |
| Sweep groups | security_and_data · product_and_strategy · ops_and_release | overlap allowed; ingest dedup handles it. Grouping is a payload-bounding concern, owned by orchestrate.py, not rules.json |
| Challenge payload scope | live rows only; settled risk rows summarized by count | strengths/unknowns always live; measured 66KB→3.5KB on a 120-settled-row register |
| Checker verbosity | terse (failures only, detail capped 200 chars) | `--verbose` → all 11 checks, full detail |
| Token estimate heuristic | ~4 chars/token, always surfaced as "est." | rough planning aid, never presented as an exact count |

## Probes (executed, never declared)

`diligence_check.py` — stdlib-only, deterministic, exit 0 green / 1 red with per-check output. Runs at Phase 4 step 3 and before any scorecard render, with evolution validity as P11; a red result blocks rendering (INV-14). Checks:

- **P1** Schema validity for register/verdicts/challenges/manifest; fingerprint uniqueness across the register.
- **P2** Every citation's artifact ID exists in the manifest; locators non-empty and pattern-valid.
- **P3** Severity–evidence consistency: Critical ⇒ `evidence_mode ∈ {cited-exploit, cited-absent-control}`; `asserted` ⇒ severity ≤ High; `live-probe-only` ⇒ type `unknown` unless a test-report citation is present.
- **P4** Verdict re-derivation: recompute each lens from the rule tables + register; recorded verdict, rule ID, and row set must match exactly.
- **P5** Admission: no verdict record for any lens below floor; skipped lenses have the one-line marker; coverage values recompute from the manifest.
- **P6** Challenge closure: every challenge has a resolution; auto-`accepted` downgrades are reflected in verdict/confidence records.
- **P7** Honesty scan: owner fields ∈ roster ∪ {"Owner unknown"}; date-pattern hits in fix/plan fields fail without a supplied calendar; currency/percent patterns fail without a citation or supplied param.
- **P8** Lifecycle: `closed` ⇒ valid executed proof record (no `manual-attestation` on Critical); `accepted` ⇒ all three acceptance fields; past-expiry ⇒ status `open`.
- **P9** Rendering: D3 section ≤ cap; every scorecard cell carries row IDs; scores match the verdict→score map.
- **P10** Manifest integrity: artifact hashes present; per-pass model pins recorded; re-run manifests chain to the prior manifest hash.

The pipeline states nothing "verified" that a probe did not verify. If the checker cannot run, the run halts before render — never downgrade to a declared pass.

## Running the loop

The pipeline is executable, not just specified. `rules.json` is the authoritative machine source for every verdict table, score, floor, and threshold (the tables in this document are its human mirror; on disagreement `rules.json` wins). `derive.py` computes verdicts and the scorecard as a pure function of the register; `diligence_check.py` is the P1–P11 render gate (terse by default, `--verbose` for full detail) and re-derives through `derive.py`; `orchestrate.py` drives the phases, owns `.diligence/` state, caps and discloses oversized artifacts, chunks large sweeps by surface group, trims the challenge payload to live evidence, and exposes a model-free `status` command for re-entering the loop without conversational memory of which phase ran last; `sweep.md` and `challenge.md` are the two model-stage payloads. The framework is a stdlib script by decision, not a graph/agent runtime — the DAG is linear with one lens fan-out and one fresh-context challenge, and the only non-deterministic steps are the two model calls. Making those two steps genuinely isolated (not just isolated in principle) is an operational choice the runbook covers but code alone can't guarantee — see ../PIPELINE.md's "Running this without context, memory, or token problems" for the full account, including the one recommendation there that's operator guidance rather than a demonstrated result. Read ../PIPELINE.md before running the loop.

## Out of scope

- **Live adversarial probing / penetration testing.** ai-red-team owns it; this skill emits `unknown` + delegation and consumes its suite results as test-report artifacts.
- **Remediation.** Findings export to product-backlog; this skill never builds fixes.
- **Legal or compliance verdicts.** compliance-mapping produces legibility; no output here is a compliance determination.
- **Market sizing.** market-sizing owns it; consumed only if supplied as an artifact.
- **Investment or financial advice.** D4 is engineering-diligence posture over cited evidence, not a valuation opinion.
- **Unbuilt ideas.** No artifacts → idea-reviewer / idea-add-moat, not this skill.
- **Diff-scoped code security mechanics.** security-review owns scanners and per-diff checklists; its outputs are intake evidence here.

## Composition

- **ai-red-team** — owns every `live-probe-only` vector; its regression-suite results re-enter as test-report artifacts that upgrade `unknown` rows and close risk rows.
- **security-review** — secrets/SAST/dependency scanner blocks enter as artifacts; strengthen evidence modes on L15, V-07, MC-4.
- **agent-security / agent-architecture** — AGENT-SECURITY.md and AGENT-DESIGN.md are the preferred evidence for L10–L12, L15, V-04/V-05/V-12; absent → recommend and record `unknown`.
- **moat-reviewer** — D5 consumes its scorecard as floor-substituting evidence; deep defensibility work delegates to it.
- **market-sizing** — never invoked; cited when supplied.
- **stakeholder-brief** — renders the scorecard and decision records with its pointer ledger; risk-acceptance decisions bind to register row content hashes.
- **compliance-mapping** — A-21 obligations cross-reference its register; gap rows flow both directions.
- **product-backlog** — open risk rows export as scored items (impact from severity, evidence carried by citation).
- **product-evals / ai-evals** — A-15 eval artifacts ground the L18 grade; absent evals cap L18 at Evidence-missing.
