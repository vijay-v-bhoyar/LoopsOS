# Assessment framework

Use all six lenses in a comprehensive run. Assess every applicable layer and cross-cutting control, but keep one underlying failure in one stable finding record.

## Six executive lenses

### 1. Beta readiness

Ask whether the application is ready for limited external beta users or only a bounded demonstration. Examine critical journeys, onboarding and recovery, auth and tenancy, privacy, prompt and retrieval safety, tool actions, uploads, observability, provider failure, accessibility, cancellation, support, rollback, and known limitations.

Use one scoped verdict: `Beta-ready`, `Beta-ready with conditions`, `Demo-ready only`, `Not ready for external users`, or `Insufficient evidence`.

`Demo-ready only` requires separate evidence that the demo scope, data, identities, and side effects are safely bounded.

### 2. Enterprise architecture and operations

Ask whether this is an operational enterprise application or a prototype with enterprise styling. Rate each applicable layer as `Production-grade`, `Beta-grade`, `Demo-grade`, `Broken`, `Evidence missing`, or `Not applicable with justification`. Do not average away a broken critical layer.

### 3. Adversarial failure modes

Ask what could break, leak, execute without authority, mislead users, or cause material harm under realistic errors and attacks. For each path record:

```text
entry point -> preconditions -> manipulated input/event -> boundary crossed -> action/output -> affected asset/person -> detection -> prevention/containment -> recovery
```

Distinguish plausible paths from demonstrated exploitability.

### 4. Acquisition and enterprise-value diligence

Separate technical acquisition posture from financial valuation. Examine strategic value, problem urgency, differentiation, architecture, security, scale, operating cost, compliance, integration, code/IP ownership, team dependency, buyer evidence, and commercial metrics.

Without revenue, growth, retention, margins, pipeline, defensible market assumptions, costs, and transaction context, report `Valuation not assessable`. Do not invent valuation or haircut percentages.

### 5. Category strategy and moat

Ask what creates durable customer value beyond a model demo. Compare with manual workflow, deterministic automation, and a general-purpose model with equivalent authorized tools. Map each moat claim as:

```text
advantage -> evidence -> ownership/usage rights -> customer benefit -> replication barrier -> model dependence -> test -> investment decision
```

Treat “10x” and category leadership as hypotheses until measured. Do not label obstructive lock-in as customer value.

### 6. Future resilience and advanced autonomy

Ask whether safety, authority, usefulness, and economics survive changes in models, tools, providers, threats, and user behavior. Exercise bounded scenarios such as model replacement, stronger planning, compromised tool output, poisoned memory, provider outage, schema drift, context pressure, parallel delegation, exhausted budgets, and canceled approval.

Use `Resilient within tested scenarios`, `Needs adaptation`, `High obsolescence/exposure risk`, or `Insufficient evidence`. “AGI readiness” is scenario testing, not certification.

## Twenty architecture layers

| ID | Layer | Examine |
|---|---|---|
| L01 | Product and workflow | Problem, complete journeys, rules, outcomes, exception ownership |
| L02 | UX and adoption | States, onboarding, accessibility, citations, correction, handoff |
| L03 | Frontend | Sessions, rendering, client exposure, error recovery |
| L04 | API | Authentication, object/function authorization, validation, throttling, replay |
| L05 | Backend services | Invariants, state transitions, concurrency, retries, idempotency, partial failure |
| L06 | Data | Integrity, classification, access, retention, deletion, backup, restore, lineage |
| L07 | Identity | User/service/agent identity, sessions, rotation, offboarding |
| L08 | Authorization | Server enforcement, delegated scope, privilege change, deny behavior |
| L09 | Tenant isolation | Databases, retrieval, memory, caches, jobs, storage, exports, logs |
| L10 | Agent orchestration | Goal/plan bounds, checkpoints, retries, cancellation, delegation, recovery |
| L11 | Prompt and policy | Versioning, trusted-policy boundary, conflicts, refusal, escalation |
| L12 | Tool execution | Provenance, schemas, authority, side effects, receipts, approval binding |
| L13 | RAG and retrieval | Source authority, permission awareness, freshness, provenance, poisoning |
| L14 | File ingestion | Type/size controls, parser isolation, malicious content, deletion |
| L15 | Security | Secrets, network/egress, dependencies, abuse, containment |
| L16 | Observability | Correlation, quality, errors, latency, cost, actions, sensitive data |
| L17 | Audit and compliance | Obligations, owners, retention, decisions, approvals |
| L18 | Testing and evaluation | Deterministic, behavioral, adversarial, regression, independence |
| L19 | CI/CD and release | Integrity, approvals, separation, progressive rollout, rollback |
| L20 | Operations and support | Objectives, ownership, alerts, incidents, communication, continuity, restore |

For each weak layer record the weakness, consequence, exact work, change type, release impact, and proof required.

## Cross-cutting agent controls

### Authority and execution integrity

Verify actor identity, delegated scope, tool/resource authority, exact approval binding, expiry, policy version, revocation, replay, queued work, and authorization recheck at execution. Prompt wording alone is not enforcement.

### Semantic and workflow completeness

Check unresolved terms, missing inputs, source conflicts, rule exceptions, partial answers, uncovered subtasks, and the distinction among answer completeness, correctness, and execution completion.

### Memory, retrieval, and context lifecycle

Check source attribution, permissions, write eligibility, conflict handling, retention, expiry, correction, deletion, transient/durable separation, cache behavior, and permission changes after indexing.

### Durable state and partial side effects

Check checkpoint ownership, concurrency, duplicate delivery, retry safety, receipts, cancellation, resume, uncertain outcomes, rollback versus compensation, irreversible effects, recovery ownership, and user notification.

### Bounded execution and safe failure

Check externally enforced limits for steps, retries, parallelism, delegation depth, context, tools, cost, and time. Include child-agent aggregate budgets, queued and in-flight cancellation, credential use, and safe fallback.

### Model and dependency change

Version models, prompts, policies, tools, packages, data transformations, and retrieval configuration. Evaluate behavior, safety, quality, latency, and cost before promotion. Inspect plugin, skill, model-serving, and tool-server provenance.

### Responsible use and human recovery

Check affected people, accessibility, domain harm, relevant fairness, uncertainty disclosure, correction, contestability, human escalation, and whether the fallback has a real responsible recipient.

### Outcome and economic verification

Measure the requested business outcome against a baseline. Include failed attempts, retries, provider and infrastructure usage, human review, and support effort. Cost per successful task requires a stated period, numerator, denominator, and complete cost boundary.

### Monitoring and harness integrity

Correlate request, run, agent, policy, retrieval, tool action, and outcome without retaining unnecessary sensitive content or private reasoning. Test alert delivery, escalation, retention, environment identity, and resistance to instructions that suppress failures.

### Governed learning

Route prompt, policy, tool, memory, threshold, and evaluation changes through approval and regression checks. An agent must not lower thresholds, delete failing cases, or grant itself authority to improve its own score.
