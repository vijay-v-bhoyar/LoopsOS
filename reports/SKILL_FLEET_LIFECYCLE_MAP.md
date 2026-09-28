# Skill Fleet Lifecycle Map

Registry-backed map of all **119 active personal skill identities**. Generated from `skill-fleet/registry.json` by `skill-fleet/generate_lifecycle_map.py`.

This is a routing map. It does **not** instruct a run to invoke every skill. The lifecycle conductor admits only the skills relevant to the product goal, risk, and evidence gap.

| Marker | Meaning |
| --- | --- |
| ◆ | Coordinating loop. Its receipt and state contracts bind work across phases. |
| ● | Canonical personal skill. Invoke when its trigger applies. |
| ⚠ | `manual-required` skill. Safe-local validation may run; its external/live prerequisite remains fail-closed. |

## Non-negotiable loop topology

1. `product-lifecycle-loop` is the single lifecycle conductor.
2. Choose **one** delivery engine for a run: `codex-product-build-loop`, `product-loop`, `agentic-product-loop`.
3. Use `loop-fleet` only after the selected solo engine has proven admission, budget, cancellation, and acceptance behavior.
4. `agentic-assurance-loop` independently closes findings. `release-governor` decides from evidence; `deploy-provision` acts only after GO and live authority exist.

## Mandatory lifecycle steps

Every lifecycle run records the applicable steps below. A step becomes a gate when its `applies_when` condition is true; it does not force unrelated skills into the run.

| Mandatory step | Applies when | Route through | Required evidence |
| --- | --- | --- | --- |

| `registry-admission` | Before every lifecycle run, resumption, schedule registration, or skill distribution change. | `product-lifecycle-loop`, `skill-creator` | Current registry digest, valid source/install inventory, and declared test class for every active skill. |
| `graph-orientation` | Before planning, implementing, debugging, enhancing, or testing repository behavior. | `graphify`, `code-map` | Current code-graph or recorded source-and-test trace; refresh changed surfaces after meaningful edits. |
| `goal-and-requirement-admission` | Before admitting a material product goal or selecting a delivery slice. | `product-vision`, `product-backlog`, `requirements-traceability`, `domain-workflow-validation` | Accepted goal, material assumptions/experiments, mapped requirements, acceptance criteria, and selected admissible work. |
| `delivery-engine-selection` | Before implementation starts or a run resumes implementation. | `product-lifecycle-loop`, `codex-product-build-loop`, `product-loop`, `agentic-product-loop` | One selected delivery engine, run identity, budget, admission decision, and parent-goal acceptance criteria. |
| `specialist-and-risk-routing` | Whenever architecture, tools, data, models, security, privacy, resilience, or user trust are materially affected. | `tool-contracts`, `agent-security`, `ai-guardrails`, `resilience`, `security-review` | Applicable specialist contracts, risk decisions, owners, and verification boundaries linked to the run identity. |
| `recover-park-and-resume` | Whenever a material check fails, work is blocked, help is required, or a run is restarted. | `product-lifecycle-loop`, `codex-product-build-loop`, `product-loop`, `agentic-product-loop` | Failure reproduction, attempted repair history, budget state, targeted help packet or park condition, and verified wake condition. |
| `independent-verification-and-closure` | Before a delivery slice or parent goal is reported complete. | `agentic-assurance-loop`, `product-evals`, `test-hardening`, `security-review` | Finding-to-reproduction-to-repair-to-retest chain, independent closure, and current parent-goal acceptance evidence. |
| `enterprise-ai-assurance` | Enterprise AI assurance is requested or required by the product risk profile, including enterprise readiness and material model/autonomy changes. | `enterprise-ai-assurance-loop`, `enterprise-ai-discovery`, `enterprise-ai-quality`, `enterprise-llm-assurance`, `enterprise-agentic-assurance`, `enterprise-frontier-assurance`, `enterprise-ai-threat-modeling`, `enterprise-quantum-safe-assurance`, `enterprise-advanced-capability-assurance`, `enterprise-ai-regulatory-assurance`, `enterprise-ai-data-lifecycle`, `enterprise-ai-independent-challenge`, `enterprise-ai-vendor-assurance`, `enterprise-human-ai-operations` | One subject/profile/verifier-bound run; thirteen applicability dispositions; raw signed owner evidence; persistent known-unaddressed risks; authenticated independent challenge; scoped current decision; one delivery engine; no implicit deployment authority. |
| `governed-release` | Before a release decision, deployment, migration, agent promotion, or other live external effect. | `release-governor`, `deploy-provision`, `migration-safety`, `ship-release`, `agent-release` | Named GO/NO_GO/ESCALATE decision, target identity, authority, fresh live evidence, and verified rollback or compensation path. |
| `operate-and-learn` | After a live product capability is released or material user feedback is received. | `product-telemetry`, `feedback-learning-governance`, `stakeholder-brief` | Observed signal, interpretation, owner, backlog consequence, and stakeholder communication where required. |
| `fleet-change-quality` | Whenever a personal skill, loop package, alias, mirror, or lifecycle policy changes. | `skill-creator`, `product-lifecycle-loop` | Regenerated lifecycle map, UTF-8 fleet validation, declared test result, reviewed distribution diff, and updated registry hashes. |

## Phase 0 — Validate the opportunity

Evidence before implementation: decide whether the problem, market, moat, and model assumptions warrant a product goal.

| Skill | Type | Fires when |
| --- | --- | --- |
| `idea-reviewer` | ● | Raw idea → defined problem, user, and buildable wedge |
| `idea-add-moat` | ● | A promising concept needs a concrete defensibility mechanism |
| `market-sizing` | ● | TAM/SAM/SOM or demand sizing needs cited assumptions |
| `moat-reviewer` | ● | Assess whether the proposed advantage can persist |
| `product-vision` | ◆ | Assemble the vision dossier; turn material unknowns into owned experiments and decisions |
| `product-diligence` | ◆ | Challenge the product across executive lenses and keep AI/model evidence current |
| `last30days` | ● | Recent market, competitor, or model change could invalidate an assumption |
| `open-access-article-finder` | ● | A research-backed product decision needs accessible primary literature |

## Phase 1 — Architect and govern

Define contracts, data boundaries, model behavior, economics, and accountable decisions before implementation commits to them.

| Skill | Type | Fires when |
| --- | --- | --- |
| `agent-architecture` | ● | An agentic feature needs roles, tools, autonomy, and escalation boundaries |
| `agentic-application-architect` | ● | A broader agentic application needs system-level architecture |
| `agent-memory` | ● | Cross-session or durable agent state needs lifecycle and retention rules |
| `agent-oversight` | ● | Agent actions require traceability, baselines, and human intervention points |
| `agent-security` | ● | Agent tools, credentials, and delegated authority need least-privilege controls |
| `ai-governance-board` | ● | A material AI decision needs accountable governance review |
| `ai-guardrails` | ● | LLM input, output, tool-use, and policy controls need a RAI design |
| `ai-validation-management` | ● | High-impact AI behavior needs validation scope, evidence, and change control |
| `architecture-decision-records` | ● | A consequential technical choice needs a durable decision record |
| `context-architecture` | ● | Long-running agents need explicit context sources, budgets, and boundaries |
| `crypto-agility-pqc` | ● | Cryptographic choices need rotation and post-quantum migration planning |
| `data-governance-architecture` | ● | Data domains, lineage, quality, and access policies need architecture |
| `enterprise-capability-map` | ● | An enterprise product needs capability coverage and ownership |
| `enterprise-governance-raci` | ● | Cross-team decisions need responsible and accountable owners |
| `enterprise-operating-model` | ● | The product changes how a team operates and needs an operating model |
| `finops-model-economics` | ● | Model routing, token use, and infrastructure spend need economic guardrails |
| `identity-access-governance` | ● | Identity, authorization, access review, or privileged roles are in scope |
| `legal-risk-register` | ● | Material legal, regulatory, contract, or IP uncertainty must be owned |
| `model-gateway` | ● | Multiple models or providers require routing, fallback, and cost controls |
| `privacy-data-governance` | ● | Personal, sensitive, or regulated data is collected or processed |
| `prompt-ops` | ● | Prompts require versioning, evaluation, context budgets, and rollback |
| `responsible-ai-impact-assessment` | ● | AI can materially affect people, rights, access, or outcomes |
| `retrieval-engineering` | ● | RAG, semantic search, grounding, or document ingestion is required |
| `supabase-architect` | ⚠ | ⚠ Supabase schema, RLS, pgvector, or Edge Functions are in scope |
| `tool-contracts` | ● | Any tool, API, endpoint, or external action needs an executable contract |

## Phase 2 — Orient, select, and admit work

Establish a graph-backed understanding, traceable requirements, an accountable goal, and a single admitted delivery path.

| Skill | Type | Fires when |
| --- | --- | --- |
| `product-lifecycle-loop` | ◆ | Lifecycle conductor from discovery through operations; binds schedules, help, budgets, migration, and immutable receipts |
| `graphify` | ● | Refresh the repository code graph before planning, changing, or reviewing |
| `code-map` | ● | Orient an unfamiliar codebase and maintain a usable implementation map |
| `product-backlog` | ● | Score and select the next valuable, feasible, evidence-backed work item |
| `intent-router` | ● | Classify a request and route it to the right capability and guardrail |
| `requirements-traceability` | ● | Link goal → requirement → implementation → test → acceptance evidence |
| `domain-workflow-validation` | ● | Validate end-to-end domain workflows and business rules before admitting work |

## Phase 3 — Build the product

Choose exactly one delivery engine per run. The fleet may parallelize only after a solo path is proven and bounded.

| Skill | Type | Fires when |
| --- | --- | --- |
| `codex-product-build-loop` | ◆ | Preferred scoped delivery engine: diagnosis → repair → verification → parent-goal acceptance |
| `product-loop` | ◆ | Bounded product improvement cycle with admission, reservations, parked work, and release handoff |
| `agentic-product-loop` | ◆ | Use when wrapper, runner, guards, artifacts, and receipt must share one immutable identity |
| `loop-fleet` | ◆ | Parallelize independent, admitted work only after the solo delivery engine is proven |
| `agents-sdk` | ● | Build an application using the OpenAI Agents SDK |
| `mcp-builder` | ⚠ | ⚠ Build or evolve an MCP server and safe tool surface |
| `supabase-dexie-sync` | ● | Implement offline-first local storage and Supabase synchronization |
| `mytress-builder` | ● | Build a MyTress-specific capability |
| `cloudflare` | ⚠ | ⚠ Use Cloudflare platform services in an approved environment |
| `durable-objects` | ● | Coordinate durable state, concurrency, or real-time collaboration on Cloudflare |
| `workers-best-practices` | ● | Implement a production-quality Cloudflare Worker |
| `wrangler` | ● | Configure, test, and operate Cloudflare Workers tooling |
| `cloudflare-one` | ● | Apply Cloudflare Zero Trust controls to product access paths |
| `cloudflare-one-migrations` | ● | Migrate Cloudflare One controls with a rollback-aware plan |
| `cloudflare-email-service` | ● | Add a Cloudflare email service integration |
| `sandbox-stable` | ● | Use the stable sandbox path for controlled runtime work |
| `sandbox-next` | ● | Evaluate the next-generation sandbox path in a bounded environment |
| `sandbox-migrate-to-next` | ● | Migrate a proven sandbox workload to the next runtime |

## Phase 3b — Product interface, trust, and performance

Apply only the UI, help, and interaction skills that the selected product experience actually needs.

| Skill | Type | Fires when |
| --- | --- | --- |
| `agent-trust-ux` | ● | Expose agent capability, limits, status, and intervention choices to users |
| `contextual-help` | ● | Add contextual in-product help for a specific user task |
| `react-pwa-help` | ● | Build help flows for a React PWA |
| `animated-ui-builder` | ● | Implement motion-rich interaction when motion supports comprehension |
| `fluent2-design-tokens` | ● | Apply a coherent Fluent 2 token system |
| `glass-ui` | ● | Apply glass UI treatment where it supports the intended product surface |
| `web-artifacts-builder` | ● | Build a substantial web artifact or React prototype |
| `canvas-design` | ● | Create a static visual or canvas-based design asset |
| `playwright` | ● | Exercise rendered browser behavior at the relevant viewport |
| `web-perf` | ● | Measure and improve web performance against a defined budget |
| `turnstile-spin` | ⚠ | ⚠ Add or change bot-protection flow with live-provider prerequisites declared |

## Phase 4 — Harden security, resilience, and operations

Threaten the product deliberately and make failure recovery, supply chain integrity, and incident response testable.

| Skill | Type | Fires when |
| --- | --- | --- |
| `agentic-production-readiness` | ◆ | Sequence twelve readiness gates through one approved, verified remediation slice at a time |
| `abuse-fraud-defense` | ● | An adversary can exploit the product, incentives, accounts, or transactions |
| `ai-red-team` | ● | Probe AI features for prompt injection, misuse, data leakage, and unsafe behavior |
| `security-review` | ● | Review the working change and deployment boundary for security defects |
| `resilience` | ● | Add retries, idempotency, timeouts, circuit breakers, and recovery behavior |
| `supply-chain-security` | ● | Dependencies, build provenance, CI, or artifact integrity are material |
| `data-stewardship-operations` | ● | Data quality, retention, remediation, or stewardship needs an operating loop |
| `compliance-mapping` | ● | Map obligations and evidence for audit, regulator, or customer review |
| `sre-incident-response` | ● | Define detection, triage, escalation, learning, and recovery for incidents |

## Phase 5 — Verify and independently close

Prove the stated result, link failures to reproductions and repairs, and keep user-facing language clear.

| Skill | Type | Fires when |
| --- | --- | --- |
| `agentic-assurance-loop` | ◆ | Bind every finding to reproduction, repair, retest evidence, and independent closure |
| `product-evals` | ● | Evaluate product and model behavior against defined metrics and acceptance cases |
| `test-hardening` | ● | Improve test strength and detect weak assertions or missing failure coverage |
| `plain-edit` | ● | Review user-facing product copy for plain, accurate language |
| `stop-slop` | ● | Remove vague, inflated, or unsupported language from deliverables |

## Phase 6 — Govern release and deployment

The release path is fail-closed: a local pass is not a production authorization or live evidence receipt.

| Skill | Type | Fires when |
| --- | --- | --- |
| `devcontainer-spec` | ⚠ | ⚠ Harden the development container for repeatable, unattended execution |
| `migration-safety` | ⚠ | ⚠ Unpark a schema or data migration only with reversible, reviewed evidence |
| `ship-release` | ⚠ | ⚠ Prepare and execute a governed merge/tag release |
| `agent-release` | ⚠ | ⚠ Promote agent behavior through canary and GA evidence |
| `release-governor` | ● | Decide GO, NO-GO, or ESCALATE from evidence and declared policy |
| `deploy-provision` | ⚠ | ⚠ Execute an approved live deployment, smoke check, and rollback path |

## Phase 7 — Operate, learn, and report

Turn real product signals and governed feedback into owned corrective work and decision-ready communication.

| Skill | Type | Fires when |
| --- | --- | --- |
| `product-telemetry` | ● | Collect product signals and convert observed behavior into backlog evidence |
| `feedback-learning-governance` | ● | Route feedback into accountable learning, decisions, and follow-up |
| `stakeholder-brief` | ● | Prepare concise executive, legal, customer, or board communication |

## Phase 8 — Business reach and content products

Use the current content-distribution skills where relevant; revenue, general GTM, and legal-document automation remain explicit fleet gaps.

| Skill | Type | Fires when |
| --- | --- | --- |
| `book-seo-metadata` | ● | Create searchable, accurate metadata for a book product |
| `state-book-research` | ● | Research a state-focused book or content product |
| `video-seo-metadata` | ● | Create searchable, accurate metadata for a video product |

## Enterprise AI assurance — 13 accountable owners

Run applicable owner disciplines through one protected assurance run; preserve unresolved risks and independent challenge.

| Skill | Type | Fires when |
| --- | --- | --- |
| `enterprise-ai-assurance-loop` | ◆ | Coordinate enterprise evidence, risk, repair, challenge and scoped release decisions |
| `enterprise-ai-discovery` | ● | Owner 0: Identify hidden AI dependencies and composed autonomy before enterprise assurance admission. |
| `enterprise-ai-quality` | ● | Owner 1: Assess complete business outcomes, cumulative harm, selective deferral and subgroup quality. |
| `enterprise-llm-assurance` | ● | Owner 2: Challenge prompt injection, provenance laundering, cumulative disclosure and model fallback behavior. |
| `enterprise-agentic-assurance` | ● | Owner 3: Verify tool authority, persistent memory, delegation, aggregate exposure and stop semantics. |
| `enterprise-frontier-assurance` | ● | Owner 4: Assess capability changes, long-horizon behavior, evaluation sensitivity and impossible authorized goals. |
| `enterprise-ai-threat-modeling` | ● | Owner 5: Model combined attack paths, shared control failures and aggregate enterprise exposure. |
| `enterprise-quantum-safe-assurance` | ● | Owner 6: Assess cryptographic paths, long-lived confidentiality, signer trust, revocation and downgrade resistance. |
| `enterprise-advanced-capability-assurance` | ● | Owner 7: Evaluate specification gaming, concealed omissions, coordination and correction behavior within bounded claims. |
| `enterprise-ai-regulatory-assurance` | ● | Owner 8: Map effective-dated obligations to actual decision lineage and whole enterprise workflows. |
| `enterprise-ai-data-lifecycle` | ● | Owner 9: Verify data derivatives, memory provenance, deletion and restore behavior, evidence privacy and holdout integrity. |
| `enterprise-ai-independent-challenge` | ● | Owner 10: Independently challenge evidence, experiment completeness, evaluator integrity and enterprise decision authority. |
| `enterprise-ai-vendor-assurance` | ● | Owner 11: Assess provider route identity, dependency concentration, signed tools, fallbacks and deprecation exposure. |
| `enterprise-human-ai-operations` | ● | Owner 12: Test human approval integrity, reviewer workload, incident containment and customer recovery. |

## Cross-cutting toolbelt

Use these throughout the lifecycle when their stated need occurs. They are supporting skills, not competing delivery engines.

| Skill | Type | Fires when |
| --- | --- | --- |
| `gstack` | ● | Use the bundled engineering workflow toolkit when its task-specific skills apply |
| `find-skills` | ● | Discover an installed capability before creating an overlapping one |
| `skill-creator` | ● | Create, repair, test, and evolve a reusable skill |
| `consolidate-memory` | ● | Consolidate durable task knowledge without treating stale memory as current proof |
| `schedule` | ● | Define or inspect recurring work with budgeted, observable execution |
| `setup-cowork` | ● | Configure collaborative workspace and agent workflow support |
| `docx` | ● | Create or edit a Word deliverable |
| `pptx` | ● | Create or edit a slide deliverable |
| `pdf` | ● | Create, inspect, or package a PDF deliverable |
| `xlsx` | ● | Create or analyze a spreadsheet deliverable |

## Directly relevant Codex support (outside this personal-skill registry)

Use these platform skills when needed: `openai-docs` for current official OpenAI guidance, `imagegen` for image generation/editing, `plugin-creator` and `skill-installer` for packaged capability work, and the built-in document, PDF, presentation, spreadsheet, and computer-use skills for their respective artifacts. Connector-specific skills remain optional integrations, not lifecycle requirements.

## Explicit gaps to build or source

The active fleet does not yet provide dedicated personal skills for general billing/subscriptions/entitlements, full-funnel growth and lifecycle marketing, legal-document authoring (Terms and Privacy Policy), or a named deep-research skill. The map keeps these visible rather than implying the existing engineering skills cover them. Add them through `skill-creator`, register their sources and test declarations, and route them through the lifecycle conductor before relying on them.

## Verification contract

Run the map generator, then fleet validation. Map generation fails if a registered skill is omitted, duplicated, or unknown; fleet validation fails if policy, metadata, source/install parity, links, aliases, or declared test classes are invalid.
