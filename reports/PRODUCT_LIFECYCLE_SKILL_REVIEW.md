# Product lifecycle skill review

Audit date: 2026-09-12. Scope: local Codex and .agents skill roots, the LoopsOS workspace skill root, and the Codex plugin cache. This is a routing and source review, not certification of any skill's runtime guarantees.

Inventory counts below are the snapshot taken before installing the new
`product-lifecycle-loop` skill created in this task.

Words are Spells: distinguish a skill that exists, a workflow that is configured, an action that is authorized, and a result that was verified.

## Verified inventory

The proposed map is useful, but the current installation inventory extends well beyond the 41 selected personal skills. The scan found **310 local entrypoint paths representing 166 distinct declared names**, plus **380 plugin-cache entrypoint paths representing 240 distinct declared names**. Across all four roots: **690 paths and 398 distinct declared names**. There were no missing frontmatter names. These are disk counts, not a count of currently callable tools or independently implemented capabilities.

| Provenance category | Entrypoint paths | Distinct declared names |
|---|---:|---:|
| Personal installation directories, excluding gstack and .system | 184 | 102 |
| gstack third-party suite within those directories | 118 | 59 |
| Codex .system skill directory | 6 | 6 |
| Workspace .codex/skills | 2 | 2 |
| Plugin cache, including older versions and unlisted packages | 380 | 240 |

Root totals are 140 under `.agents/skills`, 168 under `.codex/skills` (166 names), and 2 under workspace `.codex/skills`. Category name counts overlap; do not sum them to infer a global unique count.

The [full inventory](C:/Users/vijay/OneDrive/Documents/LoopsOS/output/product-lifecycle-skill-inventory.json) records every absolute path, declared name, SHA256, frontmatter, short description, category, supplied-catalog status, and duplicate group. The `available` label below means an exact-name entrypoint was listed in the active catalog supplied to this task. `on-disk-only` means it exists but was not listed. Neither label proves required tools, credentials, scripts, or host capabilities work.

## Corrections that change the design

1. **Keep one lifecycle conductor and one selected delivery engine.** The existing `product-loop`, `agentic-product-loop`, and `codex-product-build-loop` overlap but have different state, authority, and cadence contracts. Route work to an explicitly selected owner. Do not nest competing cycle definitions or create a second authoritative backlog, approval store, or release verdict.
2. **Resolve conflicting release instructions before enabling unattended execution.** [release-governor](C:/Users/vijay/.codex/skills/release-governor/SKILL.md:9) claims to replace human release tokens; [ship-release](C:/Users/vijay/.codex/skills/ship-release/SKILL.md:12) and [migration-safety](C:/Users/vijay/.codex/skills/migration-safety/SKILL.md:9) require attended execution; [agent-release](C:/Users/vijay/.codex/skills/agent-release/SKILL.md:151) requires approval bound to the bundle for GA. The legacy [product-loop](C:/Users/vijay/.codex/skills/product-loop/SKILL.md:13) itself says cited owners win a conflict. A new conductor cannot infer production authority from a GO file, a skill description, or an elapsed veto window. Existing user authorization and higher-priority host rules still govern; do authorized preparation without repeated permission requests.
3. **Forward promotion does not prove rollback.** [deploy-provision](C:/Users/vijay/.codex/skills/deploy-provision/SKILL.md:28) labels reversal proven by the forward alias flip. An actual reversal drill, compatible data state, restored target health, and recorded result are needed before describing rollback as executed. A deployment pointer cannot undo sent messages, completed charges, destructive data changes, or incompatible writes.
4. **Presence of scripts is not enforcement evidence.** The [model-gateway](C:/Users/vijay/.codex/skills/model-gateway/SKILL.md:38) explicitly separates registry design from requested enforcement code. Release evidence adapters, trusted evaluator identity, evidence integrity, target identity, idempotency, oversights, locks, and kill controls need verification in the target runtime. This inventory did not test them.
5. **Security, privacy, legal applicability, verification, and business design begin before launch.** They are recurring conditions on affected work. [product-telemetry](C:/Users/vijay/.codex/skills/product-telemetry/SKILL.md:80) places its collection contract before launch. Revenue model, billing authority, refunds, entitlements, consent, acquisition measurement, and owner responsibilities belong in early scope; real-user telemetry and business experiments depend on real evidence later.
6. **Route specialist skills conditionally.** Supabase and Dexie require that actual stack. MyTress rules are product-specific. Fluent 2 requires that design-system choice; glass and motion are optional treatments. MCP building is for MCP surfaces; tool-contracts owns transport-independent contracts. `test-hardening` is expensive review-cadence work after eval baselines, not an every-edit requirement. `deep-research` is a plugin skill restricted to explicit deep-research intent; it is not an automatic phase-0 tax.
7. **Keep provenance explicit.** `.system` is Codex's system skill directory. gstack is a third-party suite. Personal installation does not prove user authorship. Document, research, visual, Cloudflare, and design workflows may come from plugins. `mcp-builder`, `canvas-design`, `docx`, `pptx`, `xlsx`, and `web-artifacts-builder` on this machine are personal installations, not automatically Codex built-ins. Harness operations and automation tools are capabilities, not invented skill aliases.
8. **Business capabilities are partially covered, not complete or empty.** Cached `vercel:payments` covers Stripe setup, checkout, subscriptions, webhooks, and SDK use, but is not listed in this task's catalog and does not prove billing/entitlement behavior in a product. `finops-model-economics` overlaps `model-gateway`; its statement that no other skill centralizes spend is stale. `legal-risk-register`, `compliance-mapping`, and `stakeholder-brief` organize risk/evidence and counsel review; they do not establish legal adequacy of ToS or privacy policies. Creative and analytics plugins support growth work but are not a complete acquisition/sales/lifecycle system.

## Duplicate and host drift

Of 59 gstack names, 54 have different file hashes across `.agents` and `.codex`; 5 have identical copies. Outside gstack, these 15 name groups have differing content: `agent-memory`, `agent-release`, `agent-security`, `canvas-design`, `docx`, `find-skills`, `graphify`, `last30days`, `migration-safety`, `model-gateway`, `product-loop`, `schedule`, `ship-release`, `skill-creator`, `web-artifacts-builder`. This is **69 local name groups with byte-level SHA256 drift**, excluding the identical workspace duplicates. The five identical gstack groups are `gstack-openclaw-ceo-review`, `gstack-openclaw-investigate`, `gstack-openclaw-office-hours`, `gstack-openclaw-retro`, and `hackernews-frontpage`.

Sampled diffs show broad Claude-to-Codex substitutions, including `Codex -p`, `Codex.ai`, AGENTS/CLAUDE names, hook terminology, and paths. These substitutions do not validate a Codex command or host control. Graphify has a more substantive divergence in its subagent workflow and result collection. Resolve the exact intended path at invocation, read its current instructions, and adapt to tools actually exposed by the host. A matching name is not enough to choose among variants. The two workspace skill copies matched their personal equivalents at the snapshot time. Generic plugin names such as `index`, `market-sizing`, and `agents-sdk` may represent different owners and must be qualified by package.

## Corrected requested-name map

The user's table contains **64 individual named entries/capabilities** after splitting slash-separated names: **43 available**, **7 on-disk-only**, and **14 missing exact names**. The table below preserves each requested name. Alternatives in the following section are related routes, never silent aliases.

| Phase | Requested name | Snapshot state | Verified source |
|---|---|---|---|
| 0 | `idea-reviewer` | available | [SKILL.md](C:/Users/vijay/.agents/skills/idea-reviewer/SKILL.md) |
| 0 | `market-sizing` | available | [SKILL.md](C:/Users/vijay/.agents/skills/market-sizing/SKILL.md) |
| 0 | `moat-reviewer` | available | [SKILL.md](C:/Users/vijay/.agents/skills/moat-reviewer/SKILL.md) |
| 0 | `product-vision` | available | [SKILL.md](C:/Users/vijay/.agents/skills/product-vision/SKILL.md) |
| 0 | `deep-research` | available | [SKILL.md](C:/Users/vijay/.codex/plugins/cache/openai-curated-remote/deep-research-work/0.1.15/skills/deep-research/SKILL.md) |
| 1 | `agent-architecture` | available | [SKILL.md](C:/Users/vijay/.agents/skills/agent-architecture/SKILL.md) |
| 1 | `supabase-architect` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/supabase-architect/SKILL.md) |
| 1 | `tool-contracts` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/tool-contracts/SKILL.md) |
| 1 | `model-gateway` | available | [SKILL.md](C:/Users/vijay/.agents/skills/model-gateway/SKILL.md) |
| 1 | `prompt-ops` | available | [SKILL.md](C:/Users/vijay/.agents/skills/prompt-ops/SKILL.md) |
| 1 | `retrieval-engineering` | available | [SKILL.md](C:/Users/vijay/.agents/skills/retrieval-engineering/SKILL.md) |
| 1 | `agent-memory` | available | [SKILL.md](C:/Users/vijay/.agents/skills/agent-memory/SKILL.md) |
| 1 | `mcp-builder` | available | [SKILL.md](C:/Users/vijay/.agents/skills/mcp-builder/SKILL.md) |
| 1 | `claude-api` | missing | No exact entrypoint in scope |
| 2 | `code-map` | available | [SKILL.md](C:/Users/vijay/.agents/skills/code-map/SKILL.md) |
| 2 | `product-backlog` | available | [SKILL.md](C:/Users/vijay/.agents/skills/product-backlog/SKILL.md) |
| 3 | `product-loop` | available | [SKILL.md](C:/Users/vijay/.agents/skills/product-loop/SKILL.md) |
| 3 | `loop-fleet` | available | [SKILL.md](C:/Users/vijay/.agents/skills/loop-fleet/SKILL.md) |
| 3 | `mytress-builder` | available | [SKILL.md](C:/Users/vijay/.agents/skills/mytress-builder/SKILL.md) |
| 3b | `supabase-dexie-sync` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/supabase-dexie-sync/SKILL.md) |
| 3b | `agent-trust-ux` | available | [SKILL.md](C:/Users/vijay/.agents/skills/agent-trust-ux/SKILL.md) |
| 3b | `contextual-help` | available | [SKILL.md](C:/Users/vijay/.agents/skills/contextual-help/SKILL.md) |
| 3b | `react-pwa-help` | available | [SKILL.md](C:/Users/vijay/.agents/skills/react-pwa-help/SKILL.md) |
| 3b | `animated-ui-builder` | available | [SKILL.md](C:/Users/vijay/.agents/skills/animated-ui-builder/SKILL.md) |
| 3b | `glass-ui` | available | [SKILL.md](C:/Users/vijay/.agents/skills/glass-ui/SKILL.md) |
| 3b | `fluent2-design-tokens` | available | [SKILL.md](C:/Users/vijay/.agents/skills/fluent2-design-tokens/SKILL.md) |
| 3b | `frontend-design` | missing | No exact entrypoint in scope |
| 3b | `dataviz` | missing | No exact entrypoint in scope |
| 3b | `web-artifacts-builder` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/web-artifacts-builder/SKILL.md) |
| 3b | `artifact-design` | missing | No exact entrypoint in scope |
| 3b | `canvas-design` | available | [SKILL.md](C:/Users/vijay/.agents/skills/canvas-design/SKILL.md) |
| 4 | `agent-security` | available | [SKILL.md](C:/Users/vijay/.agents/skills/agent-security/SKILL.md) |
| 4 | `ai-guardrails` | available | [SKILL.md](C:/Users/vijay/.agents/skills/ai-guardrails/SKILL.md) |
| 4 | `agent-oversight` | available | [SKILL.md](C:/Users/vijay/.agents/skills/agent-oversight/SKILL.md) |
| 4 | `resilience` | available | [SKILL.md](C:/Users/vijay/.agents/skills/resilience/SKILL.md) |
| 5 | `security-review` | available | [SKILL.md](C:/Users/vijay/.agents/skills/security-review/SKILL.md) |
| 5 | `product-evals` | available | [SKILL.md](C:/Users/vijay/.agents/skills/product-evals/SKILL.md) |
| 5 | `test-hardening` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/test-hardening/SKILL.md) |
| 5 | `ai-red-team` | available | [SKILL.md](C:/Users/vijay/.agents/skills/ai-red-team/SKILL.md) |
| 5 | `plain-edit` | available | [SKILL.md](C:/Users/vijay/.agents/skills/plain-edit/SKILL.md) |
| 5 | `verify` | missing | No exact entrypoint in scope |
| 5 | `code-review` | missing | No exact entrypoint in scope |
| 5 | `simplify` | missing | No exact entrypoint in scope |
| 6 | `devcontainer-spec` | available | [SKILL.md](C:/Users/vijay/.agents/skills/devcontainer-spec/SKILL.md) |
| 6 | `migration-safety` | available | [SKILL.md](C:/Users/vijay/.agents/skills/migration-safety/SKILL.md) |
| 6 | `ship-release` | available | [SKILL.md](C:/Users/vijay/.agents/skills/ship-release/SKILL.md) |
| 6 | `agent-release` | available | [SKILL.md](C:/Users/vijay/.agents/skills/agent-release/SKILL.md) |
| 6 | `release-governor` | available | [SKILL.md](C:/Users/vijay/.agents/skills/release-governor/SKILL.md) |
| 6 | `deploy-provision` | available | [SKILL.md](C:/Users/vijay/.agents/skills/deploy-provision/SKILL.md) |
| 7 | `product-telemetry` | available | [SKILL.md](C:/Users/vijay/.agents/skills/product-telemetry/SKILL.md) |
| 7 | `compliance-mapping` | available | [SKILL.md](C:/Users/vijay/.agents/skills/compliance-mapping/SKILL.md) |
| 7 | `stakeholder-brief` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/stakeholder-brief/SKILL.md) |
| 7 | `docx` | available | [SKILL.md](C:/Users/vijay/.agents/skills/docx/SKILL.md) |
| 7 | `pptx` | available | [SKILL.md](C:/Users/vijay/.agents/skills/pptx/SKILL.md) |
| 7 | `xlsx` | on-disk-only | [SKILL.md](C:/Users/vijay/.agents/skills/xlsx/SKILL.md) |
| 7 | `pdf` | available | [SKILL.md](C:/Users/vijay/.agents/skills/pdf/SKILL.md) |
| 8 | `monetization` | missing | No exact entrypoint in scope |
| 8 | `growth-gtm` | missing | No exact entrypoint in scope |
| 8 | `legal-doc` | missing | No exact entrypoint in scope |
| cross-cutting | `skill-creator` | available | [SKILL.md](C:/Users/vijay/.codex/skills/.system/skill-creator/SKILL.md) |
| cross-cutting | `session-start-hook` | missing | No exact entrypoint in scope |
| cross-cutting | `update-config` | missing | No exact entrypoint in scope |
| cross-cutting | `init` | missing | No exact entrypoint in scope |
| cross-cutting | `loop` | missing | No exact entrypoint in scope |

## Missing names and related routes
- **claude-api**: No Anthropic-specific skill verified; use current Anthropic primary documentation if that provider is selected. OpenAI and Cloudflare agent skills are provider-specific alternatives, not aliases.
- **frontend-design**: design-consultation (gstack, listed): aesthetic/system planning; product-design:ideate (plugin, listed): image-based alternatives; product-design:url-to-code (plugin, listed): website reconstruction.
- **dataviz**: build-web-data-visualization:data-visualization (plugin, listed); data-analytics:visualize-data (plugin, listed); data-analytics:build-dashboard (plugin, listed).
- **artifact-design**: product-design workflows and document/presentation/PDF artifact skills; no general artifact-design entrypoint verified.
- **verify**: codex-product-build-loop (workspace and personal, listed): risk-based change verification; qa or qa-only (gstack, listed): browser QA; vercel:verification (cached, not listed): full-flow verification; not a verified active alias.
- **code-review**: review (gstack, listed); review-agent (.system, on disk but not listed); superpowers:requesting-code-review (cached, not listed).
- **simplify**: No exact skill; scoped cleanup through codex-product-build-loop plus review, without adopting a guessed slash command.
- **xlsx**: Spreadsheets runtime skill exists in plugin cache but is not listed in the supplied catalog; use declared artifact runtime after discovery; google-drive:google-sheets (listed) for connected Google Sheets, a different surface.
- **monetization**: vercel:payments (cached, not listed): Stripe checkout, subscriptions, SDK and webhooks; model-gateway and finops-model-economics: cost evidence, not billing/entitlement implementation.
- **growth-gtm**: product-vision and market-sizing: strategy/evidence; creative-production:intake and produce (listed): creative deliverables; data-analytics:design-kpis and product-business-analysis (listed): business measurement; book-seo-metadata/video-seo-metadata: content-specific SEO, not generic SaaS growth.
- **legal-doc**: legal-risk-register (on disk, not listed): legal risk ownership; compliance-mapping (listed): cited obligation/control/evidence mapping; stakeholder-brief (on disk, not listed): counsel pre-read; documents/docx (listed): file rendering, not legal adequacy.
- **session-start-hook**: Codex harness configuration/extension capability, not a verified skill; use openai-docs for current supported setup.
- **update-config**: Codex settings capability, not a verified skill; use openai-docs for current supported configuration.
- **init**: Initialization behavior belongs to the selected conductor; no exact init SKILL.md verified; AGENTS.md is repo guidance.
- **loop**: Codex automation_update tool for authorized recurring work; not a loop skill or Claude slash command; product-loop/agentic-product-loop are different existing conductor skills, not scheduler aliases.

The seven on-disk-only exact names are `supabase-architect`, `supabase-dexie-sync`, `tool-contracts`, `test-hardening`, `stakeholder-brief`, `xlsx`, and `web-artifacts-builder`. Their full paths are preserved above and in the inventory. Discover/read the selected entrypoint before use; do not label them missing or assume all their dependencies are active.

## Recommended routing contract

The reusable conductor should first resolve product scope, repository/branch/graph, current lifecycle state, installed/exposed capability inventory, user authority, and evidence freshness. Each dispatch names the owning skill and exact path, bounded objective, inputs, expected artifacts, acceptance criteria, allowed effects, evidence requirements, and terminal outcome. Read the selected skill on demand. An unresolved optional capability blocks that capability, not unrelated authorized work.

Use one complete slice per build cycle. Keep independent research, inspection, and narrowly scoped verification parallel where useful; serialize shared state and external mutations. Use `codex-product-build-loop` for scoped implementation and `agentic-assurance-loop` for broader assurance when warranted. Route code releases, behavior promotion, database migration, provider deployment, and business actions to their different owners. Keep `READY_FOR_REVIEW`, `LOCAL_VERIFIED`, `HOSTED_VERIFIED`, `LIVE`, and business-outcome claims distinguishable in evidence. A green local test or a prepared launch plan does not prove any later state.

For recurring work, use the Codex automation tool only when the user requests scheduled/continued work. A reusable skill alone is not a persistent runner. Use bounded budgets, stop conditions, recoverable checkpoints, explicit escalation, and quiet monitoring when nothing actionable changed. Feedback can create proposed backlog changes; it does not silently rewrite the active skills, prompts, permissions, or release policy.

## Review limits

All 690 entrypoint files were read by the metadata parser and hashed. Every frontmatter was extracted into the inventory. Semantic review sampled skill bodies for lifecycle routing, release and authority contradictions, portability, cadence, and business adjacency. Some bulk terminal output was truncated; machine counts and exact-name queries were checked separately. This is not a complete security audit of 690 skill packages, their scripts, their references, their versions, or their runtime integrations.

No `.claude` paths were scanned. Plugin cache contents include older versions and packages that may not be active; installation state was not queried. Session-catalog mapping is manually transcribed from the supplied catalog, not a runtime tool-availability probe. No skill was installed, no existing skill was modified by this audit, no deployment or payment occurred, and no provider was contacted. The reusable conductor package is separate work by the parent task.
