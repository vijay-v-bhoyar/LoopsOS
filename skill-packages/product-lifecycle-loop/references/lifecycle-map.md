# Corrected lifecycle and composition map

Read the rows relevant to the requested outcome. Names below are selectors to
resolve against the current host, not a promise of installed or active tools.
The author's full personal/catalog audit is a separate dated report; this map
holds decision-changing routes rather than every installed skill description.

## Phases, owners, and exit evidence

| Stage | Trigger and owners | Useful output / exit evidence |
|---|---|---|
| 0. Discover and validate | `idea-reviewer`, `market-sizing`, `moat-reviewer`, `idea-add-moat`, `product-vision`; active `deep-research` for explicit deep-research intent, or ordinary research/search tools when needed | Customer/problem evidence, a buildable wedge, competitor alternatives, cited market assumptions, falsifiable success criteria, and a chosen direction. TAM alone does not validate demand. |
| 1. Design the product and architecture | `agentic-application-architect` for broader agentic application structure; `agent-architecture` only for agent behavior; `supabase-architect` only for a matching Supabase AI/PWA backend; `tool-contracts`, `model-gateway`, `prompt-ops`, `retrieval-engineering`, `agent-memory`, `mcp-builder` and `agents-sdk` only for affected boundaries | Architecture/UX decisions, API/data contracts, identity/tenant controls, model and operating costs, failure and recovery design, acceptance checks. A non-agentic app does not require an agent stack. |
| 2. Orient and prioritize | Graphify first for repo work, `code-map` for a maintained map, `product-backlog` for prioritization; `spec`, applicable `plan-*` or `autoplan` only when their review scope helps | Verified dependency trace, outcome-linked backlog, selected complete slice, dependencies, explicit non-goals, and a verification plan. |
| 3. Deliver | `codex-product-build-loop` preferred; `product-loop` or `agentic-product-loop` only as an explicitly selected alternative conductor; `mytress-builder` only for MyTress | Real UI/service/storage/provider behavior where required, synchronized contracts, failure handling, and tests. No placeholder is a completed capability. |
| 3b. Apply domain and experience layers | `supabase-dexie-sync` for relevant offline sync; `agent-trust-ux`; `contextual-help` or `react-pwa-help`; `animated-ui-builder`, `glass-ui`, `fluent2-design-tokens` only when they match the desired design | Working reconnect/conflict behavior, accessible interaction and help, loading/empty/error/permission states, rendered responsive evidence. Visual style is a choice, not a universal gate. |
| 4. Secure and make resilient | `agent-security` before agent credentials/tools; `security-review` for app/code boundaries; `ai-guardrails` and `ai-red-team` for relevant AI risks; `agent-oversight`, `resilience`, privacy and compliance owners as needed; `agentic-assurance-loop` for requested broad assurance | Implemented and exercised authorization, isolation, abuse protection, resource bounds, retries/idempotency, visibility and recovery. Begin in design and revisit at changed boundaries. |
| 5. Verify and review | `product-evals`, `security-review`; targeted `test-hardening` when test strength needs measurement; browser `qa`/`qa-only`/`playwright`/computer-use; `review` for code findings; `plain-edit` for copy | Requirement-based positive, negative, boundary, integration, and user-journey evidence; independent review where risk warrants it. Mutation score supplements behavioral tests; it does not establish specification correctness. |
| 6. Prepare, decide, and release | `devcontainer-spec` when an unattended container is needed; `migration-safety` for schema work; `ship-release` or matching Git workflow for merge/tag; `agent-release` for behavior bundles; reviewed `release-governor` for mechanical readiness; `deploy-provision` or active provider workflow for deployment | Separate readiness, authority, release, migration, deployed artifact, authenticated-live, provider, rollback/restore and watch evidence. Apply [release-and-operations.md](release-and-operations.md), including the legacy helper block. |
| 7. Operate and improve | `product-telemetry`, `agent-oversight`, `resilience`; `sre-incident-response` if resolved; `compliance-mapping`, `stakeholder-brief`; `finops-model-economics` for appropriate cost analysis | SLO/error-budget and outcome observations, incident/recovery records, capacity/cost evidence, customer support learnings, renewal/retention and backlog changes. |
| 8. Build the business | Embedded [business playbooks](business-playbooks.md), relevant delivery/research/design/analytics skills, `legal-risk-register` where resolved | Tested entitlements and payment state, verified offer and funnel, consent-aware lifecycle process, fact-based policy drafts and review decisions. Business discovery starts at stage 0; activation is separate. |

## Codex and plugin capability corrections

Use the actual qualified entry from the session catalog. These are capability
substitutions to evaluate, not claims that differently named skills are identical.

| Original map name or assumption | Resolution in Codex |
|---|---|
| `claude-api` as a Codex built-in | Resolve only if working with Anthropic. If absent, use the project's SDK and current official provider documentation through available tools. For OpenAI work, resolve `openai-docs` or relevant `openai-developers:*` skill and tools. Do not import Claude-specific harness commands. |
| `frontend-design` must be enabled | Use a relevant active `product-design:*`, `figma:*`, `design-consultation`, `design-html`, or other verified design skill. Establish a coherent accessible aesthetic with the product owner; no specific style skill is mandatory. |
| `dataviz` | Resolve `build-web-data-visualization:data-visualization` or a matching `data-analytics:*` skill for interactive visuals; use plotting tools for scientific/exportable figures. |
| `web-artifacts-builder`, `artifact-design` | Resolve exact names first. An on-disk prototype skill is not a deployed app. Product-design, creative-production, or ordinary repository delivery may cover the actual task. |
| `canvas-design` as built-in | It may be a personal installation. Resolve it for static visual composition; use image generation through the actual available image tool when appropriate. |
| `verify`, `code-review`, `simplify` | Resolve names before invoking. Current alternatives include the delivery loop's verification, `review`, `qa`/`qa-only`, and normal scoped cleanup. A skill name is not a test command. |
| `docx / pptx / xlsx / pdf` all built-in | Choose the active `documents:documents`, `presentations:Presentations`, spreadsheets skill/tool, `pdf:pdf`, or verified personal equivalent. Google Docs/Slides/Sheets skills are distinct connector workflows. Load bundled workspace runtimes when producing office artifacts. |
| `session-start-hook`, `update-config`, `init` | These are harness-specific or unresolved names. Use inspected Codex repository/configuration mechanisms only when the task requires them. `AGENTS.md` is the repository instruction filename; do not silently create Claude configuration. |
| `loop` for recurring tasks | Use the actual Codex automation capability for an explicit recurrence/monitor request. A skill does not schedule itself. |

## Cross-cutting routing

- **Research and planning:** deep-research, Firecrawl search/research, and relevant
  analytics skills can inform customer, market, pricing, technical, and risk
  questions. Browse current authoritative sources when the facts need it.
- **Design and delivery:** design consultation, Figma, sites, image generation,
  browser tooling, and provider skills apply to their actual requested surfaces.
  They do not require replacing a product's chosen stack or publishing it.
- **Quality and governance:** architecture, contracts, security, privacy,
  accessibility, performance, cost, migration safety, and release proof travel
  with the change from discovery onward.
- **Learning and skill maintenance:** `skill-creator`/`skill-installer` for
  explicitly requested skill changes. Keep self-improvement proposals separate
  from the active run's gates; never weaken the control evaluating your own work.
- **Specialized existing skills:** book/video SEO, hackathon submission,
  Cloudflare, Supabase, Vercel, iOS, and other domain skills stay available through
  discovery. Route them when the product needs them, not because the inventory
  contains them. Keep specialist claims bounded by their own evidence.

## Main corrections to the original sequence

There is one lifecycle owner, multiple conditional specialists, and feedback
between stages. A fixed count of personal skills is not an admission criterion.
Installed skills, active skills, tools, and functioning production integrations
are four different things.

Code mapping precedes repository architecture work. Security, privacy, UX,
accessibility, operations, costs, pricing, and customer discovery begin before
build. Hardening and verification are ongoing disciplines. Commercial readiness
can be a launch prerequisite even when an app already responds to requests.

GO/NO_GO governs a stated readiness question; it cannot remove authorization
boundaries. Automated recovery must be implemented, exercised, and monitored.
An agent writing a plan, an approval token, or a rollback record does not prove
those controls operate outside its own text.
