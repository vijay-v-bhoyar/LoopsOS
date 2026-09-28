# Composition map — which skill fires where

Read this when routing an item at PLAN, when refreshing `.loop/SKILLS.md`,
or when diagnosing an `owner-unresolved` park.

**Two-tier readiness rule** (SKILL.md § 0/§13): **core owners** — product-loop,
product-backlog, code-map, product-evals, security-review, release-governor,
deploy-provision, agent-release, agent-oversight, agent-security,
devcontainer-spec, prompt-ops — must ALL resolve to an installed,
content-hashed SKILL.md before any unattended run starts. **Consumer/edge
owners** (everything else in the table below) may be absent; each
unresolved one parks exactly the capability it governs
(`Cause: owner-unresolved`, `needs: install <skill>`) while the loop runs.

| Skill | Fires at | Owns |
|---|---|---|
| product-loop | Every cycle | Phases, gates, authority hierarchy, blocker/halt lists |
| product-backlog | INIT seed; REVIEW GROOM; NO-GO items | Scoring (impact×confidence/effort), decomposition, schema |
| code-map | ORIENT `--if-stale`; structural COMMITs; REVIEW audit | MAP.md format, generator, curated-region rules |
| product-evals | REVIEW; governor gate 1; watch | Manifest, runner, closed verdict vocabulary, loop health |
| security-review | VERIFY gate 4; governor gate 2 | Surface classes, scanners, severity table, Security block |
| test-hardening | REVIEW | Mutation score, property/fuzz scaffolds |
| product-telemetry | REVIEW ingest | Quarantine, redaction, source tags, injection defenses |
| release-governor | Phase 7 | Seven gates, class table, verdict, watch, GOVERNANCE.md |
| deploy-provision | Phase 7 GO | Immutable build, alias flip, smoke probes, rollback.json |
| ship-release | Human path; GO mechanics | Merge/tag/changelog, evidence collector, Blocked walk |
| agent-release | `behavior` items | Bundles, ladder, pointer flip, lifecycle |
| migration-safety | Migration unpark; gate 3 evidence | Executed round-trip, expand/contract, runbook |
| agent-oversight | Continuous | Traces, baselines, approval tokens, audit store (commit hash as span attribute) |
| agent-incident | Sev-high alerts | Kill ladder, authority asymmetry |
| agent-security | Harness config | Allowlists, unbypassable denials, principals, enumerated hook set, STOP denial |
| agent-memory | State register | Typed stores, promotion gates, checkpoint/resume |
| tool-contracts | New/changed surfaces; VERIFY advisory | Contract records, idempotency/retry classes, error taxonomy |
| prompt-ops | Context assembly; pin bumps | Window ledger, slices, upgrade trigger matrix, the loop's own cycle prompt |
| devcontainer-spec | INIT; unattended runs | Pinned verified sandbox |
| loop-fleet | Parallel mode | Partitioner, coordinator, single-writer lock, fleet budget |
| agent-architecture | Items creating/changing an agent | AGENT-DESIGN.md, action tiering |
| model-gateway | Continuous | Routing, clearance, cost attribution feeding the budget ledger |
| retrieval-engineering | Doc/knowledge context | Corpus register, provenance, abstention floor |
| stakeholder-brief / compliance-mapping | Consumers | Read RunRecords and GOVERNANCE.md as indexes, **dereference source evidence when auditing** — they never *author* sources; an index that can't be dereferenced is a broken pointer, not a substitute |

Everything in SKILL.md not attributed elsewhere is product-loop's own law.
