"""Generate the complete, checked lifecycle map for the active personal skill fleet.

The grouping is deliberately a routing guide, not an instruction to invoke every
skill in every run.  Each registered identity must occur exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "skill-fleet" / "registry.json"
OUTPUT_PATH = ROOT / "reports" / "SKILL_FLEET_LIFECYCLE_MAP.md"

LOOPS = {
    "agentic-assurance-loop",
    "agentic-production-readiness",
    "agentic-product-loop",
    "codex-product-build-loop",
    "loop-fleet",
    "product-diligence",
    "product-lifecycle-loop",
    "product-loop",
    "product-vision",
    "enterprise-ai-assurance-loop",
}
MANUAL_REQUIRED = {
    "agent-release",
    "cloudflare",
    "deploy-provision",
    "devcontainer-spec",
    "mcp-builder",
    "migration-safety",
    "ship-release",
    "supabase-architect",
    "turnstile-spin",
}

PHASES: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "Phase 0 — Validate the opportunity",
        "Evidence before implementation: decide whether the problem, market, moat, and model assumptions warrant a product goal.",
        [
            ("idea-reviewer", "Raw idea → defined problem, user, and buildable wedge"),
            ("idea-add-moat", "A promising concept needs a concrete defensibility mechanism"),
            ("market-sizing", "TAM/SAM/SOM or demand sizing needs cited assumptions"),
            ("moat-reviewer", "Assess whether the proposed advantage can persist"),
            ("product-vision", "Assemble the vision dossier; turn material unknowns into owned experiments and decisions"),
            ("product-diligence", "Challenge the product across executive lenses and keep AI/model evidence current"),
            ("last30days", "Recent market, competitor, or model change could invalidate an assumption"),
            ("open-access-article-finder", "A research-backed product decision needs accessible primary literature"),
        ],
    ),
    (
        "Phase 1 — Architect and govern",
        "Define contracts, data boundaries, model behavior, economics, and accountable decisions before implementation commits to them.",
        [
            ("agent-architecture", "An agentic feature needs roles, tools, autonomy, and escalation boundaries"),
            ("agentic-application-architect", "A broader agentic application needs system-level architecture"),
            ("agent-memory", "Cross-session or durable agent state needs lifecycle and retention rules"),
            ("agent-oversight", "Agent actions require traceability, baselines, and human intervention points"),
            ("agent-security", "Agent tools, credentials, and delegated authority need least-privilege controls"),
            ("ai-governance-board", "A material AI decision needs accountable governance review"),
            ("ai-guardrails", "LLM input, output, tool-use, and policy controls need a RAI design"),
            ("ai-validation-management", "High-impact AI behavior needs validation scope, evidence, and change control"),
            ("architecture-decision-records", "A consequential technical choice needs a durable decision record"),
            ("context-architecture", "Long-running agents need explicit context sources, budgets, and boundaries"),
            ("crypto-agility-pqc", "Cryptographic choices need rotation and post-quantum migration planning"),
            ("data-governance-architecture", "Data domains, lineage, quality, and access policies need architecture"),
            ("enterprise-capability-map", "An enterprise product needs capability coverage and ownership"),
            ("enterprise-governance-raci", "Cross-team decisions need responsible and accountable owners"),
            ("enterprise-operating-model", "The product changes how a team operates and needs an operating model"),
            ("finops-model-economics", "Model routing, token use, and infrastructure spend need economic guardrails"),
            ("identity-access-governance", "Identity, authorization, access review, or privileged roles are in scope"),
            ("legal-risk-register", "Material legal, regulatory, contract, or IP uncertainty must be owned"),
            ("model-gateway", "Multiple models or providers require routing, fallback, and cost controls"),
            ("privacy-data-governance", "Personal, sensitive, or regulated data is collected or processed"),
            ("prompt-ops", "Prompts require versioning, evaluation, context budgets, and rollback"),
            ("responsible-ai-impact-assessment", "AI can materially affect people, rights, access, or outcomes"),
            ("retrieval-engineering", "RAG, semantic search, grounding, or document ingestion is required"),
            ("supabase-architect", "⚠ Supabase schema, RLS, pgvector, or Edge Functions are in scope"),
            ("tool-contracts", "Any tool, API, endpoint, or external action needs an executable contract"),
        ],
    ),
    (
        "Phase 2 — Orient, select, and admit work",
        "Establish a graph-backed understanding, traceable requirements, an accountable goal, and a single admitted delivery path.",
        [
            ("product-lifecycle-loop", "Lifecycle conductor from discovery through operations; binds schedules, help, budgets, migration, and immutable receipts"),
            ("graphify", "Refresh the repository code graph before planning, changing, or reviewing"),
            ("code-map", "Orient an unfamiliar codebase and maintain a usable implementation map"),
            ("product-backlog", "Score and select the next valuable, feasible, evidence-backed work item"),
            ("intent-router", "Classify a request and route it to the right capability and guardrail"),
            ("requirements-traceability", "Link goal → requirement → implementation → test → acceptance evidence"),
            ("domain-workflow-validation", "Validate end-to-end domain workflows and business rules before admitting work"),
        ],
    ),
    (
        "Phase 3 — Build the product",
        "Choose exactly one delivery engine per run. The fleet may parallelize only after a solo path is proven and bounded.",
        [
            ("codex-product-build-loop", "Preferred scoped delivery engine: diagnosis → repair → verification → parent-goal acceptance"),
            ("product-loop", "Bounded product improvement cycle with admission, reservations, parked work, and release handoff"),
            ("agentic-product-loop", "Use when wrapper, runner, guards, artifacts, and receipt must share one immutable identity"),
            ("loop-fleet", "Parallelize independent, admitted work only after the solo delivery engine is proven"),
            ("agents-sdk", "Build an application using the OpenAI Agents SDK"),
            ("mcp-builder", "⚠ Build or evolve an MCP server and safe tool surface"),
            ("supabase-dexie-sync", "Implement offline-first local storage and Supabase synchronization"),
            ("mytress-builder", "Build a MyTress-specific capability"),
            ("cloudflare", "⚠ Use Cloudflare platform services in an approved environment"),
            ("durable-objects", "Coordinate durable state, concurrency, or real-time collaboration on Cloudflare"),
            ("workers-best-practices", "Implement a production-quality Cloudflare Worker"),
            ("wrangler", "Configure, test, and operate Cloudflare Workers tooling"),
            ("cloudflare-one", "Apply Cloudflare Zero Trust controls to product access paths"),
            ("cloudflare-one-migrations", "Migrate Cloudflare One controls with a rollback-aware plan"),
            ("cloudflare-email-service", "Add a Cloudflare email service integration"),
            ("sandbox-stable", "Use the stable sandbox path for controlled runtime work"),
            ("sandbox-next", "Evaluate the next-generation sandbox path in a bounded environment"),
            ("sandbox-migrate-to-next", "Migrate a proven sandbox workload to the next runtime"),
        ],
    ),
    (
        "Phase 3b — Product interface, trust, and performance",
        "Apply only the UI, help, and interaction skills that the selected product experience actually needs.",
        [
            ("agent-trust-ux", "Expose agent capability, limits, status, and intervention choices to users"),
            ("contextual-help", "Add contextual in-product help for a specific user task"),
            ("react-pwa-help", "Build help flows for a React PWA"),
            ("animated-ui-builder", "Implement motion-rich interaction when motion supports comprehension"),
            ("fluent2-design-tokens", "Apply a coherent Fluent 2 token system"),
            ("glass-ui", "Apply glass UI treatment where it supports the intended product surface"),
            ("web-artifacts-builder", "Build a substantial web artifact or React prototype"),
            ("canvas-design", "Create a static visual or canvas-based design asset"),
            ("playwright", "Exercise rendered browser behavior at the relevant viewport"),
            ("web-perf", "Measure and improve web performance against a defined budget"),
            ("turnstile-spin", "⚠ Add or change bot-protection flow with live-provider prerequisites declared"),
        ],
    ),
    (
        "Phase 4 — Harden security, resilience, and operations",
        "Threaten the product deliberately and make failure recovery, supply chain integrity, and incident response testable.",
        [
            ("agentic-production-readiness", "Sequence twelve readiness gates through one approved, verified remediation slice at a time"),
            ("abuse-fraud-defense", "An adversary can exploit the product, incentives, accounts, or transactions"),
            ("ai-red-team", "Probe AI features for prompt injection, misuse, data leakage, and unsafe behavior"),
            ("security-review", "Review the working change and deployment boundary for security defects"),
            ("resilience", "Add retries, idempotency, timeouts, circuit breakers, and recovery behavior"),
            ("supply-chain-security", "Dependencies, build provenance, CI, or artifact integrity are material"),
            ("data-stewardship-operations", "Data quality, retention, remediation, or stewardship needs an operating loop"),
            ("compliance-mapping", "Map obligations and evidence for audit, regulator, or customer review"),
            ("sre-incident-response", "Define detection, triage, escalation, learning, and recovery for incidents"),
        ],
    ),
    (
        "Phase 5 — Verify and independently close",
        "Prove the stated result, link failures to reproductions and repairs, and keep user-facing language clear.",
        [
            ("agentic-assurance-loop", "Bind every finding to reproduction, repair, retest evidence, and independent closure"),
            ("product-evals", "Evaluate product and model behavior against defined metrics and acceptance cases"),
            ("test-hardening", "Improve test strength and detect weak assertions or missing failure coverage"),
            ("plain-edit", "Review user-facing product copy for plain, accurate language"),
            ("stop-slop", "Remove vague, inflated, or unsupported language from deliverables"),
        ],
    ),
    (
        "Phase 6 — Govern release and deployment",
        "The release path is fail-closed: a local pass is not a production authorization or live evidence receipt.",
        [
            ("devcontainer-spec", "⚠ Harden the development container for repeatable, unattended execution"),
            ("migration-safety", "⚠ Unpark a schema or data migration only with reversible, reviewed evidence"),
            ("ship-release", "⚠ Prepare and execute a governed merge/tag release"),
            ("agent-release", "⚠ Promote agent behavior through canary and GA evidence"),
            ("release-governor", "Decide GO, NO-GO, or ESCALATE from evidence and declared policy"),
            ("deploy-provision", "⚠ Execute an approved live deployment, smoke check, and rollback path"),
        ],
    ),
    (
        "Phase 7 — Operate, learn, and report",
        "Turn real product signals and governed feedback into owned corrective work and decision-ready communication.",
        [
            ("product-telemetry", "Collect product signals and convert observed behavior into backlog evidence"),
            ("feedback-learning-governance", "Route feedback into accountable learning, decisions, and follow-up"),
            ("stakeholder-brief", "Prepare concise executive, legal, customer, or board communication"),
        ],
    ),
    (
        "Phase 8 — Business reach and content products",
        "Use the current content-distribution skills where relevant; revenue, general GTM, and legal-document automation remain explicit fleet gaps.",
        [
            ("book-seo-metadata", "Create searchable, accurate metadata for a book product"),
            ("state-book-research", "Research a state-focused book or content product"),
            ("video-seo-metadata", "Create searchable, accurate metadata for a video product"),
        ],
    ),
    (
        "Cross-cutting toolbelt",
        "Use these throughout the lifecycle when their stated need occurs. They are supporting skills, not competing delivery engines.",
        [
            ("gstack", "Use the bundled engineering workflow toolkit when its task-specific skills apply"),
            ("find-skills", "Discover an installed capability before creating an overlapping one"),
            ("skill-creator", "Create, repair, test, and evolve a reusable skill"),
            ("consolidate-memory", "Consolidate durable task knowledge without treating stale memory as current proof"),
            ("schedule", "Define or inspect recurring work with budgeted, observable execution"),
            ("setup-cowork", "Configure collaborative workspace and agent workflow support"),
            ("docx", "Create or edit a Word deliverable"),
            ("pptx", "Create or edit a slide deliverable"),
            ("pdf", "Create, inspect, or package a PDF deliverable"),
            ("xlsx", "Create or analyze a spreadsheet deliverable"),
        ],
    ),
]


def marker(skill_id: str) -> str:
    if skill_id in LOOPS:
        return "◆"
    if skill_id in MANUAL_REQUIRED:
        return "⚠"
    return "●"


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registered = {skill["id"] for skill in registry["skills"]}
    enterprise_catalog = ROOT / "skill-packages" / "enterprise-ai-assurance-loop" / "catalog" / "owners.json"
    phases = list(PHASES)
    if "enterprise-ai-assurance-loop" in registered:
        owners = json.loads(enterprise_catalog.read_text(encoding="utf-8"))
        phases.insert(-1, ("Enterprise AI assurance — 13 accountable owners",
            "Run applicable owner disciplines through one protected assurance run; preserve unresolved risks and independent challenge.",
            [("enterprise-ai-assurance-loop", "Coordinate enterprise evidence, risk, repair, challenge and scoped release decisions")]
            + [(o["skill"], f"Owner {o['owner']}: {o['description']}") for o in owners]))
    policy = registry.get("lifecycle_policy")
    if not isinstance(policy, dict):
        raise SystemExit("Registry must declare lifecycle_policy before generating the lifecycle map.")
    topology = policy.get("topology")
    mandatory_steps = policy.get("mandatory_steps")
    if not isinstance(topology, dict) or not isinstance(mandatory_steps, list):
        raise SystemExit("Registry lifecycle_policy must declare topology and mandatory_steps.")
    assigned = [skill_id for _, _, items in phases for skill_id, _ in items]
    duplicate_ids = sorted({skill_id for skill_id in assigned if assigned.count(skill_id) > 1})
    unknown_ids = sorted(set(assigned) - registered)
    missing_ids = sorted(registered - set(assigned))
    if duplicate_ids or unknown_ids or missing_ids:
        raise SystemExit(
            "Lifecycle map assignment invalid: "
            f"duplicate={duplicate_ids}, unknown={unknown_ids}, missing={missing_ids}"
        )

    lines = [
        "# Skill Fleet Lifecycle Map",
        "",
        f"Registry-backed map of all **{len(registered)} active personal skill identities**. Generated from `skill-fleet/registry.json` by `skill-fleet/generate_lifecycle_map.py`.",
        "",
        "This is a routing map. It does **not** instruct a run to invoke every skill. The lifecycle conductor admits only the skills relevant to the product goal, risk, and evidence gap.",
        "",
        "| Marker | Meaning |",
        "| --- | --- |",
        "| ◆ | Coordinating loop. Its receipt and state contracts bind work across phases. |",
        "| ● | Canonical personal skill. Invoke when its trigger applies. |",
        "| ⚠ | `manual-required` skill. Safe-local validation may run; its external/live prerequisite remains fail-closed. |",
        "",
        "## Non-negotiable loop topology",
        "",
        f"1. `{topology['conductor']}` is the single lifecycle conductor.",
        "2. Choose **one** delivery engine for a run: " + ", ".join(f"`{engine}`" for engine in topology["delivery_engines"]) + ".",
        f"3. Use `{topology['parallelizer']}` only after the selected solo engine has proven admission, budget, cancellation, and acceptance behavior.",
        f"4. `{topology['assurance']}` independently closes findings. `{topology['release_decider']}` decides from evidence; `{topology['deployment_executor']}` acts only after GO and live authority exist.",
        "",
        "## Mandatory lifecycle steps",
        "",
        "Every lifecycle run records the applicable steps below. A step becomes a gate when its `applies_when` condition is true; it does not force unrelated skills into the run.",
        "",
        "| Mandatory step | Applies when | Route through | Required evidence |",
        "| --- | --- | --- | --- |",
        "",
    ]
    for step in mandatory_steps:
        skills = ", ".join(f"`{skill}`" for skill in step["required_skills"])
        lines.append(
            f"| `{step['id']}` | {step['applies_when']} | {skills} | {step['required_evidence']} |"
        )
    lines.append("")
    for heading, intent, items in phases:
        lines.extend([f"## {heading}", "", intent, "", "| Skill | Type | Fires when |", "| --- | --- | --- |"])
        lines.extend(f"| `{skill_id}` | {marker(skill_id)} | {trigger} |" for skill_id, trigger in items)
        lines.append("")

    lines.extend(
        [
            "## Directly relevant Codex support (outside this personal-skill registry)",
            "",
            "Use these platform skills when needed: `openai-docs` for current official OpenAI guidance, `imagegen` for image generation/editing, `plugin-creator` and `skill-installer` for packaged capability work, and the built-in document, PDF, presentation, spreadsheet, and computer-use skills for their respective artifacts. Connector-specific skills remain optional integrations, not lifecycle requirements.",
            "",
            "## Explicit gaps to build or source",
            "",
            "The active fleet does not yet provide dedicated personal skills for general billing/subscriptions/entitlements, full-funnel growth and lifecycle marketing, legal-document authoring (Terms and Privacy Policy), or a named deep-research skill. The map keeps these visible rather than implying the existing engineering skills cover them. Add them through `skill-creator`, register their sources and test declarations, and route them through the lifecycle conductor before relying on them.",
            "",
            "## Verification contract",
            "",
            "Run the map generator, then fleet validation. Map generation fails if a registered skill is omitted, duplicated, or unknown; fleet validation fails if policy, metadata, source/install parity, links, aliases, or declared test classes are invalid.",
            "",
        ]
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(registered)} assigned skills.")


if __name__ == "__main__":
    main()
