---
name: product-vision
description: Authors a founder's product vision (problem, insight/thesis, why-now, north-star, personas, pillars, roadmap themes, positioning) and assembles it with pressure-tested diligence by orchestrating the market-sizing, moat-reviewer, and idea-reviewer skills into a single dossier. Use when the user wants a product vision, vision doc, north-star narrative, or a complete vision-plus-diligence package for a product or startup idea. Owns the vision layer only and delegates market sizing, competitive/moat analysis, and buildability/risk to the three specialist skills rather than duplicating them. Never fabricates the founder's strategic claims — it flags [founder input needed] instead. For a standalone market size, moat review, or buildability critique, use those skills directly.
---

# Product Vision

## Fleet binding

Read [fleet-binding.md](fleet-binding.md) before carrying assumptions into a parent goal.

Produce a founder's product vision and a pressure-tested dossier around it. This skill owns the vision layer. It delegates the diligence — market sizing, competitive/moat, buildability/risk — to the three specialist skills and assembles everything into one document. It does not re-implement their analysis.

## Anti-fabrication (the core guard)

The vision-core fields are strategic assertions only the founder can truthfully make. Never invent them — an invented thesis is worse than a blank one.

- Never fabricate: **insight/thesis**, **why-now**, **non-goals**, or the **positioning claim**. If the founder didn't supply them and they aren't safely inferable, write `[founder input needed]` and move on.
- Do draft from the idea, marking Unknown where thin: personas, pillars, roadmap themes, and the one-line market thesis.
- Continue independent diligence while strategic inputs remain unknown. Turn each material unknown into an owned question or experiment with affected criterion IDs and a revisit trigger. Ask only the decisions blocking the requested next outcome, directly or through the parent conductor's help route; deliver the proposed dossier with unresolved inputs visible.

## Vision layer (this skill owns it)

**0. Identity** — item type; title; one-line description; intended tech stack (not architecture); external link; cover image URL.

**1. Vision core** — never fabricated (see guard):
- Problem: the specific problem and who feels it acutely.
- Insight / thesis: the one non-obvious truth this is built on.
- Why now: the shift (tech, cost, regulation, behavior) that makes this possible or urgent now.
- Vision statement: one sentence describing the world if this wins.
- Mission: what the product does day to day to get there.
- Non-goals: what it is deliberately not.

**2. Audience map** — for Primary users, Buyers, and Influencers, capture each: persona name · role/title · industry & segment · willingness to pay (and whose budget) · specific pain points · job-to-be-done · trigger moment · current alternatives (incl. "do nothing") · why they'd switch and the switching friction. Mark one persona as the **beachhead candidate** — its validation is idea-reviewer's job.

**3. Strategic pillars (max 6)** — durable themes, not features. Each: name · what it means · why it matters to the vision.

**4. Roadmap themes** — Now / Next / Later at theme level, each mapped to a pillar. Detailed v1 scope and sequencing are idea-reviewer's job.

**5. Positioning claim** — category framing ("the X for Y"); the intended unique advantage as a stated belief; the intended wedge. The pressure-test is moat-reviewer's job.

**6. Metrics** — one north-star metric; 2–4 supporting outcome metrics. Pilot/kill thresholds are idea-reviewer's job.

**7. Market thesis** — one sentence: who, why the spend exists, why it's big enough to matter.

## Orchestration (tight — assemble one dossier)

Read and execute each delegated skill's `SKILL.md`, feeding the vision's own claims in as input so nothing is analyzed twice:

1. Draft the vision layer first.
2. Run the three, in this order, using vision outputs as their inputs:
   - `market-sizing` ← the product restatement, buyer, workflow, and the market-thesis line. (This fires live web research — the dossier build is slow and search-dependent; proceed, but expect it.)
   - `moat-reviewer` ← the idea plus the **positioning claim** as its "claimed moat."
   - `idea-reviewer` ← the idea, the **beachhead persona** as the wedge to validate, and the primary workflow.
3. Each skill owns its section; do not repeat its analysis elsewhere.

Record the material question, selected specialist path/version, input evidence and output before reusing diligence. Reuse only when its subject, evidence age and revisit triggers still match. Re-run the affected specialist when inputs materially change, rather than executing the entire trio twice.

If any delegated skill is unavailable, produce the vision layer and note which diligence section is missing — do not fake it.

## Output — one dossier

Choose the output root supplied by the host or user; otherwise use the current workspace's `output/` directory. Create the directory within authorized writable scope and write `product-vision-<slug>.md` (docx on request). Return a real absolute local file link and verify that the artifact exists and opens. Do not assume a Linux mount on Windows. Sections:

1. **Vision** — the vision layer, with `[founder input needed]` and Unknown marked honestly.
2. **Market sizing** — the `market-sizing` output.
3. **Moat & competitive** — the `moat-reviewer` output.
4. **Buildability, wedge & risk** — the `idea-reviewer` output.
5. **Vision vs diligence** — the synthesis, and the reason this is one dossier rather than four stapled reports: state plainly where the diligence **supports**, **weakens**, or **contradicts** each vision claim (e.g., moat-reviewer rating the positioning claim a fake moat, or market-sizing shrinking the market thesis). Do not paper over contradictions — surfacing them is the point. End with the consolidated `[founder input needed]` list.

The dossier is only as strong as the founder's inputs and the sourced diligence. Say so; never inflate a thin vision into a confident one.

## Owned assumptions and bounded acceptance

Use [references/vision-decisions.md](references/vision-decisions.md) to keep the proposed vision separate from recorded founder acceptance. Give assumptions stable IDs, experiment and decision owners, affected work, evidence dates and revisit triggers. A test can support an assumption; it cannot supply the founder's decision. Acceptance of one wedge unlocks only its dependent criteria. Never turn a proposed non-goal, unanswered willingness-to-pay question, or an unreviewed dossier into build authority.

The portable ledger validates artifact and decision bindings and reports unresolved questions. The host must verify actor identity and actual authority before treating recorded acceptance as permission. The parent conductor retains the complete goal and resumes dependent planning only after that check.
