# Agentic Product Loop Execution Contract

Portable local lane amendment: the guard's default is discovery with exit 2.
Use its explicit adapter/config/hash arguments for actual local admission through
the pinned product-loop implementation. `local-cycle-contract.json` records the
shared contract and reviewed source digests. The same configuration produces the
same machine admission result in wrapper and runner. This covers the local lane,
not every unimplemented v13 invariant below. No local result authorizes release.

This is the compact checklist for `agentic-product-loop`. The canonical source is
`PRODUCT-LOOP-FINAL-v13.md`.

Source document:

- File: `references/PRODUCT-LOOP-FINAL-v13.md`
- SHA-256: `94C691B89E0CC5987D3BBE03DCECAF80F2E62A29E80411E2D8DF90F9A0259AEB`

## Modes

- `init`: create or repair `.loop/` state only after human product vision exists.
- `cycle`: run exactly one admitted loop cycle.
- `review`: run the REVIEW cycle when cadence or debt requires it.
- `incident`: diagnose and respond to alerts, watch failures, regressions, and
  behavior-release failures.
- `doctor`: inspect readiness and report missing prerequisites without mutation.

## Required `.loop/` State

- `.loop/VISION.md`: human-owned product intent. Never invent it.
- `.loop/INBOX.md`: human intent queue.
- `.loop/BACKLOG.md`: scored, decomposed items.
- `.loop/COMMANDS.md`: safe-local and effectful command registry.
- `.loop/MAP.md`: structural project map.
- `.loop/LOOP_LOG.md`: append-only cycle ledger.
- `.loop/DECISIONS.md`: durable decisions.
- `.loop/METRICS.md`: product and loop metrics.
- `.loop/SKILLS.md`: resolved skill/bundle records where implemented.
- `.loop/STOP`: halt switch; if present, do not write repo files.

## Core Owner Skills

Unattended execution requires these core owners to resolve:

- `product-loop`
- `product-backlog`
- `code-map`
- `product-evals`
- `security-review`
- `release-governor`
- `deploy-provision`
- `agent-release`
- `agent-oversight`
- `agent-security`
- `devcontainer-spec`
- `prompt-ops`

Missing core owners block unattended execution. Missing edge or consumer owners park
only their governed capability.

## Evidence Rules

- Every green gate needs executed evidence for the current source hash.
- Missing evidence is a NO-GO or PARK, not a pass.
- Missing commands become backlog work.
- Effectful commands require exact human approval.
- Rollback must be executed or explicitly parked; never merely declared.

## Commit Rule

The v13 loop is "one item, one commit" for admitted cycles, but the active chat
instructions still apply. Commit only when the repo state is safe, user work is not
mixed into the diff, gates are green or legally parked, and commits are allowed by
the current user instruction or repo loop policy.
