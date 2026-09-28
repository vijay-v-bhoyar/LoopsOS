# Codex Product Build Loop

`codex-product-build-loop` is a reusable Codex orchestration skill for product implementation, enhancement, bug fixing, refactoring, QA, and evidence-backed handoff.

It keeps the useful principles from the attached Karpathy-inspired skill—think before coding, simplicity, surgical changes, and goal-driven execution—and adds the operating controls that product work needs:

- request versus repository/document instruction boundaries;
- diagnosis, implementation, testing, and release modes;
- repository ground truth and served-app identity checks;
- progressively disclosed Graphify, verification, and release-proof guidance;
- risk-based unit, integration, browser, security, migration, and release verification;
- explicit local, deployment, authenticated-live, and human-approval evidence;
- bounded failure-loop retesting and a durable evidence ledger;
- Codex UI metadata and trigger-boundary evaluations.

## Use it in Codex

Keep this folder under a repository’s `.codex/skills/` directory for repository-local use, or copy the folder to your personal Codex skills directory to make it available across projects. It should trigger when repository-backed product behavior must be built, enhanced, fixed, refactored, or tested. Pure ideation, content work, standalone audits, migration reviews, deployments, and release decisions should route to their specialized skills unless they are part of a combined implementation request.

The included evaluation files cover implementation, audit-only, test-only, migration-sensitive, and production-readiness behavior, plus realistic prompts that should and should not trigger the skill.

## Recommended name

`codex-product-build-loop` is intentionally distinct from the existing `product-loop` and `agentic-product-loop` names. It identifies Codex as the target and covers implementation plus verification without implying unattended production autonomy or replacing specialized security, migration, QA, and release skills.
