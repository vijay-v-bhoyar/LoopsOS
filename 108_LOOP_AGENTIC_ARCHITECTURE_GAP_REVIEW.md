# 108-Loop Agentic Architecture Gap Review

## Engagement Summary

### Objective

Review the current 108-loop Markdown corpus as an agentic application architecture and identify gaps plus concrete suggestions to improve it.

### Recommended Mode

Application build mode.

The current artifact is not only documentation. It is becoming a control architecture for SDLC, AI, GenAI, and agentic systems. The review therefore treats the 108 loop files as future skills, workflow nodes, gates, monitors, evaluators, and human-approval surfaces.

### Current Evidence

- Current loop files: 108.
- Current category folders: 13.
- Category distribution matches the taxonomy: 5, 9, 6, 5, 10, 5, 8, 8, 9, 11, 14, 8, 10.
- Source names and generated file headings match: 108 of 108.
- Total generated loop corpus size: 7,063,093 bytes.
- Total generated loop corpus length: 165,980 lines.
- Average loop file length: 1,535.9 lines.
- Production-grade appendix occurrences: 108.
- Placeholder count for `To be assigned`: 1,188.
- Files with loop-specific tool contract sections: 0.
- Files with explicit golden tasks: 0.
- Files with machine-readable YAML, JSON, or CSV loop manifests outside Markdown: 0.
- Every loop file includes the real control checklist `LC-001` through `LC-109`, plus one `LC-000` placeholder in the manifest example.

## Executive Verdict

The 108-loop corpus is strong as a documentation expansion, but not yet strong as an executable agentic operating system.

The main gap is not missing prose. The main gap is missing structure that agents, validators, dashboards, and governance gates can execute reliably.

Right now each loop file contains:

- Good taxonomy identity.
- Good generic production-grade control language.
- Full checklist coverage.
- A broad result envelope.

But each loop file does not yet contain enough loop-specific architecture to decide:

- What exact evidence this loop consumes.
- Which controls apply to this loop versus merely appear in the global appendix.
- Which tools it may call.
- Which probes prove it.
- Which adjacent loops it triggers.
- Which owner is authoritative.
- Which failure modes must be tested.
- Which golden tasks prove the loop works.
- Which state transitions are legal.
- Which risk-tier escalation rules apply in practice.

The next improvement should turn the corpus from "expanded Markdown" into a layered agentic control system.

## Highest-Impact Gaps

### 1. The Corpus Is Too Expanded For Agent Runtime Use

Evidence:

- 108 files.
- 165,980 total lines.
- Average 1,535.9 lines per loop file.
- The full production-grade appendix is repeated in all 108 files.

Why it matters:

An agent or orchestrator should load the smallest useful context first, then progressively load deeper details only when needed. Repeating the full checklist in every file increases context cost, search noise, diff noise, and drift risk.

Suggestion:

Keep two artifact modes:

- `expanded/`: human-readable complete files for offline reference.
- `runtime/`: compact loop descriptors that reference shared standards and control catalogs.

Recommended structure:

```text
loops/
  README.md
  expanded/
    01-product-strategy-discovery-and-lifecycle/
  runtime/
    loop-descriptors/
    loop-profiles/
    loop-graph.yaml
standards/
  production-grade-loop-standard.md
  CONTROL_CATALOG.yaml
schemas/
  loop-descriptor.schema.json
  result-envelope.schema.json
  control-coverage.schema.json
```

### 2. The Full Checklist Is Present But Not Mapped

Evidence:

- Every loop includes `LC-001` through `LC-109`.
- No separate control applicability matrix exists.

Why it matters:

Checklist presence is not control coverage. A loop needs to say which controls apply, which are inherited, which are delegated, which are not applicable, and which are blocked because ownership or proof is missing.

Suggestion:

Create a sparse control applicability matrix:

```yaml
loop_id: loop-069-tool-execution-validation-loop
controls:
  LC-001:
    applicability: applicable
    owner_ref: loop-identity-owner
    proof_required: STATIC
  LC-055:
    applicability: applicable
    owner_ref: agent-state-consistency-and-idempotency-loop
    proof_required: REPLAY_PROBE
  LC-061:
    applicability: conditional
    applies_when:
      - tool action is consequential
      - tool action is privileged
      - tool action is externally visible
```

This becomes the bridge between the 109-control standard and the 108 loops.

### 3. Placeholders Block Production Readiness

Evidence:

- `To be assigned` appears 1,188 times.
- Owner references, evidence locations, targets, formulas, and effective dates are mostly unresolved.

Why it matters:

The production-grade standard says unmapped authority blocks high-risk progression. A loop file with unresolved owners can be a draft, but it cannot be treated as a deployable skill or gate.

Suggestion:

Add a validation rule:

- Draft files may contain placeholders.
- Pilot files may contain limited placeholders with owner and deadline.
- Active files must contain zero unowned placeholders for authority, evidence, and gate fields.

Create:

```text
owners/
  OWNER_REGISTRY.yaml
evidence/
  EVIDENCE_LOCATION_REGISTRY.yaml
scripts/
  validate_loop_corpus.py
```

### 4. Loop-Specific Tool Contracts Are Missing

Evidence:

- `Tool Contracts=0` across the 108 files, apart from generic mentions of tool contracts in proof scope.

Why it matters:

Agentic systems fail when tools are available but not contractually bounded. Each loop that observes, executes, validates, records, or escalates needs explicit tool contracts.

Suggestion:

Add a `Tool Contracts` section to every runtime loop profile:

| Tool | Purpose | Required inputs | Expected output | Failure modes | Timeout | Retry | Verification before use | Fallback |
|---|---|---|---|---|---|---|---|---|
| evidence_reader | Fetch authoritative evidence | source_ref, scope | evidence_bundle | stale, denied, missing | 30s | no for denied | freshness and lineage check | escalate |
| verdict_writer | Record gate verdict | loop_id, execution_id, verdict | durable record | conflict, write failure | 15s | idempotent retry | read-after-write | block |

### 5. Golden Tasks And Evals Are Missing

Evidence:

- `Golden Tasks=0`.
- No loop-specific eval files were found.

Why it matters:

The files describe proof, but do not define concrete test cases that prove each loop behaves correctly.

Suggestion:

Add at least three golden tasks per loop:

- Happy path: sufficient evidence, correct owner, proven result.
- Failure path: missing proof, stale input, unsafe action, or owner conflict.
- Conditional path: temporary progression with expiry and compensating control.

For high-risk loops, add:

- Adversarial case.
- Replay case.
- Authorization-denied case.
- Recovery or rollback drill.

### 6. Risk Tiering Is Heuristic, Not Evidence-Based

Evidence:

- Current generated default tiers: R1=38, R2=32, R3=37, R4=1.
- The generator infers tiers from category and name keywords.

Why it matters:

Risk tier is execution-dependent. The same loop can be R1 in a sandbox and R4 when it can delete production data, change access, move money, affect regulated users, or trigger autonomous external actions.

Suggestion:

Replace `default_tier` with:

```yaml
risk:
  baseline_tier: R1
  escalation_dimensions:
    environment: []
    data_sensitivity: []
    external_effect: []
    reversibility: []
    blast_radius: []
    autonomy: []
    security_privilege: []
    regulatory_impact: []
    maximum_loss: []
  effective_tier_rule: highest_applicable_dimension
```

The file may still carry a suggested default, but gates should use effective risk.

### 7. Loop-To-Loop Handoffs Are Too Generic

Evidence:

- The generator defaults downstream events to `Backlog Refinement Loop` and `Risk Management Loop`, with a few keyword additions.
- No explicit graph file exists.

Why it matters:

The user asked for smaller connected loops. Connection should not be implied by prose. It should be explicit enough for orchestration, routing, dashboards, and loop-storm prevention.

Suggestion:

Create `loop_graph.yaml`:

```yaml
edges:
  - from: loop-069-tool-execution-validation-loop
    to: loop-073-agent-state-consistency-and-idempotency-loop
    event: partial_effect_detected
    evidence: tool_execution_record
    priority: high
  - from: loop-074-agent-failure-recovery-loop
    to: loop-092-model-portability-and-exit-loop
    event: repeated_provider_failure
    evidence: failure_recovery_trend
    priority: medium
```

Add cycle control:

- Maximum loop fan-out.
- Correlation ID.
- Duplicate suppression.
- Loop storm breaker.
- Escalation when the same event bounces between loops.

### 8. Agent Topology Is Not Defined

Why it matters:

There should not be 108 free-form autonomous agents. That would create coordination burden, authority conflicts, and hard-to-debug behavior.

Recommended orchestration shape:

Use a supervisor graph with specialized deterministic gates.

```text
Trigger Router
  -> Qualification Gate
  -> Evidence Collector
  -> Diagnosis Planner
  -> Control Applicability Mapper
  -> Action Planner
  -> Authority Gate
  -> Executor
  -> Validator
  -> Proof Runner
  -> Recorder
  -> Learning and Standardization Node
  -> Effectiveness Monitor
```

Each of the 108 loops should become a configuration profile for this graph, not necessarily a separate agent.

### 9. Memory Model Is Not Concrete

Why it matters:

The loop system needs memory, but unmanaged memory can create stale proof, privacy exposure, and bad recurrence logic.

Suggestion:

Use three memory layers:

- Working memory: current execution state, evidence bundle, decisions, temporary reasoning.
- Episodic memory: prior loop runs, repeated failures, reversals, lessons, postmortems.
- Long-lived reference memory: standards, control catalog, policies, schemas, approved probes, owner registry.

Rules:

- Proof records expire.
- Sensitive data is minimized.
- Lessons must have a destination.
- Memory writes require classification and retention.
- Agent memory must route through Agent Memory Loop and Privacy Engineering and Data Protection Loop where applicable.

### 10. State Machine Is Listed But Not Enforced

Evidence:

- Durable states are listed in every file.
- No state-transition schema or validator exists.

Why it matters:

A state list does not prevent illegal transitions. For example, a loop should not jump from `ACTION_APPLIED` to `CLOSED` without validation, proof, effectiveness handling, and evidence record.

Suggestion:

Create `state_machine.yaml`:

```yaml
allowed_transitions:
  TRIGGERED:
    - QUALIFIED
    - INPUT_INCOMPLETE
    - BLOCKED
  ACTION_APPLIED:
    - VALIDATION_PASSED
    - VALIDATION_FAILED
    - ROLLED_BACK
  VALIDATION_PASSED:
    - PROOF_GREEN
    - PROOF_FAILED
    - EFFECTIVENESS_PENDING
```

Add a validator that rejects illegal transitions.

### 11. Evidence And Probe References Are Not Executable

Why it matters:

The files name proof methods, but do not define runnable probes, acceptance criteria, or evidence freshness checks.

Suggestion:

Create a probe registry:

```yaml
probe_id: replay-tool-idempotency-v1
loop_ids:
  - loop-069-tool-execution-validation-loop
  - loop-073-agent-state-consistency-and-idempotency-loop
method: REPLAY_PROBE
inputs:
  - operation_id
  - tool_call_record
acceptance:
  - repeated operation produces one logical effect
  - duplicate side effects are absent
evidence_output: idempotency_verdict.json
```

### 12. Metrics Are Generic Instead Of Loop-Specific

Why it matters:

Every loop says it needs baseline, target, guardrails, and health metrics. But the formulas are not specialized per loop.

Suggestion:

Create per-loop metric packs.

Example:

```yaml
loop_id: loop-061-hallucination-reduction-loop
primary_metric:
  name: unsupported_answer_rate
  formula: unsupported_answers / evaluated_answers
guardrails:
  - citation_precision
  - abstention_rate
  - answer_latency_p95
  - user_resolution_rate
```

### 13. Vendored Standard Source

Evidence:

- `standards/production-grade-continuous-improvement-loop.md` is the vendored production-grade loop standard.
- `standards/STANDARD_SOURCE.yaml` records the source path, vendored path, SHA-256 hash, review date, and status.
- `scripts/generate_runtime_backbone.py` can refresh from the original source when present, but can regenerate from the vendored standard when the original source is absent.

Why it matters:

The generation must remain reproducible from the repo. The vendored standard and hash now give the system a stable source of truth.

Operational rule:

Treat changes to the vendored standard as controlled changes. Regenerate the runtime backbone and rerun `python scripts\validate_loop_corpus.py` after any update.

### 14. No Corpus Validator Exists Yet

Why it matters:

This corpus needs a test suite just like code.

Suggestion:

Add `scripts/validate_loop_corpus.py` to check:

- Exactly 108 loop files.
- Exactly 13 categories.
- Category counts match taxonomy.
- Unique stable loop IDs.
- All source taxonomy rows map to files.
- No duplicate headings.
- No active loop contains unresolved authority placeholders.
- `LC-001` through `LC-109` present in standard catalog.
- Each loop has a runtime descriptor.
- Each loop has control applicability mapping.
- Each loop has at least one happy-path, failure-path, and conditional-path golden task.
- State transitions are legal.
- Loop graph has no unbounded cycles.

## Application Build Blueprint

### Goal And Risk Profile

Goal: Convert the 108-loop taxonomy into a governed, evidence-producing agentic control system.

Risk profile: R2 by default, R3 or R4 when loops can touch production, sensitive data, privileged tools, external communications, compliance controls, autonomous agents, or irreversible actions.

### Recommended Orchestration Shape

Use a supervisor graph with deterministic gates and loop-specific profiles.

Avoid making every loop a full autonomous agent. Use each loop as a skill/profile that configures shared nodes.

### Node Or Agent Responsibilities

| Node | Owns | Reasoning pattern |
|---|---|---|
| Trigger Router | Event classification, dedupe, initial routing | ReAct for fresh signals |
| Qualification Gate | Scope, owner, input sufficiency, risk tier | Chain of Verification |
| Evidence Collector | Authoritative source gathering and lineage | ReWOO for tool-efficient collection |
| Diagnosis Planner | Gap and cause analysis | Chain of Thought, Graph of Thoughts |
| Control Applicability Mapper | Which LC controls apply | LLM-as-Judge with rules |
| Action Planner | Remediation, sequence, recovery plan | Plan-and-Execute |
| Authority Gate | Approval, policy, separation of duties | Guardrail layers |
| Executor | Bounded action execution | ReWOO or deterministic workflow |
| Validator | Immediate correctness and non-regression | Chain of Verification |
| Proof Runner | Probe, drill, replay, canary, sustained proof | Tool-driven verification |
| Recorder | Evidence, result envelope, state events | Deterministic write path |
| Learning Node | Regression cases, standards, backlog, memory | Reflexion with governed memory |
| Effectiveness Monitor | Observation window and drift | Scheduled monitor |

### State And Memory Model

| Memory type | Use | Guardrail |
|---|---|---|
| Working memory | Active loop run, evidence bundle, decisions | Clear after run or persist only approved summary |
| Episodic memory | Prior incidents, repeated failures, reversals | Retention and privacy classification |
| Long-lived reference memory | Control catalog, standards, owner registry, probes | Versioned and source-controlled |

### Tool Contracts

Minimum tool contracts needed:

- Evidence reader.
- Source freshness checker.
- Owner registry lookup.
- Risk-tier calculator.
- Control applicability resolver.
- Probe runner.
- State transition writer.
- Result envelope writer.
- Verdict writer.
- Notification router.
- Memory writer.
- Corpus validator.

### Verification, Guardrails, And Human Handoffs

Use three layers:

- Reasoning quality checks: branch comparison, diagnosis challenge, judge review.
- Policy and safety checks: authority, approval, access, compliance, privacy, residual risk.
- Operational safety checks: idempotency, timeout, retry, rollback, circuit breaker, loop storm prevention.

Human handoff is required for:

- R3 or R4 action.
- Residual-risk acceptance.
- Owner conflict.
- Unmapped authority.
- Irreversible action.
- Production or customer-impacting exception.
- Repeated oscillation.

### Evals And Observability

Eval categories:

- Correct routing.
- Correct loop selection.
- Correct control applicability.
- Correct proof-state classification.
- Correct tool choice.
- Correct refusal or escalation.
- Correct conditional verdict expiry.
- Correct state transition.
- Correct loop-to-loop handoff.
- Correct learning destination.

Observability signals:

- Trigger source.
- Loop ID.
- Correlation ID.
- Risk tier.
- Authority resolution.
- Evidence freshness.
- Tools called.
- Probes run or skipped.
- Proof state.
- State transition.
- Human approvals.
- Failure state.
- Latency.
- Cost.
- Token use.
- Loop fan-out.
- Reversal count.

## Cognitive Demands Table

| Task step | Cue or signal | Hidden assumption | Judgment or decision | Preferred strategy | Common error or failure mode | Verification pattern | Agent design implication | Evidence source |
|---|---|---|---|---|---|---|---|---|
| Route trigger to loop | Event, schedule, threshold, request, incident, change, expiry | The event has one best primary owner | Which loop owns the concern first | ReAct plus classifier | Duplicate handling or wrong loop ownership | Routing eval and dedupe probe | Trigger Router with loop graph | Trigger record, loop graph |
| Qualify ownership | Scope, asset, source freshness, active duplicate, current proof | The loop has authority to proceed | Qualify, reject, delegate, or block | Chain of Verification | Unmapped authority treated as pass | Authority probe | Qualification Gate | Owner registry, evidence source |
| Calculate risk tier | Data class, environment, autonomy, reversibility, blast radius | Static default tier is enough | Effective tier for this execution | Rule engine plus judge for ambiguous cases | Keyword tiering misses high-risk context | Scenario probe | Risk-tier calculator | Risk dimensions record |
| Collect evidence | Logs, metrics, docs, tests, approvals, runtime data | Copied summaries are equivalent to authoritative sources | Which evidence is current and trusted | ReWOO | Stale or conflicted evidence used silently | Freshness and lineage check | Evidence Collector | Source systems, evidence registry |
| Map controls | LC-001 through LC-109, loop purpose, risk tier | Every listed control applies equally | Applicable, delegated, conditional, not applicable, blocked | LLM-as-Judge with rules | Checklist presence mistaken for coverage | Control coverage audit | Control Applicability Mapper | Control catalog, loop profile |
| Diagnose gap | Symptoms, failed controls, repeated patterns | Symptom equals root cause | Immediate, contributing, and systemic cause | Chain of Thought, Graph of Thoughts | Fixing symptom without failed control | RCA review | Diagnosis Planner | Evidence bundle, prior runs |
| Plan action | Gap, priority, owner, recovery, validation | A good fix is safe to execute | Smallest authorized action and proof path | Plan-and-Execute | Broad remediation without recovery | Plan review and dry run | Action Planner | Remediation plan |
| Authorize | Risk tier, policy owner, gate owner, approval state | Operator can approve own risky action | Approve, condition, block, or escalate | Guardrail layers | Separation of duties bypassed | Authorization probe | Authority Gate | Owner registry, approval record |
| Execute | Tool call, state change, deployment, policy update | Successful action means outcome improvement | Execute within bounded authority | ReWOO or deterministic workflow | Non-idempotent retry causes duplicate effects | Replay and timeout probes | Executor with idempotency | Tool logs, operation IDs |
| Validate | Postconditions, regression checks, side effects | Local success means system success | Immediate correctness and non-regression | Chain of Verification | Validation skips side effects | Regression and impact probes | Validator node | Test results, health checks |
| Prove control | Probe, drill, replay, canary, observation | Declared control is enough | Proof state and gate eligibility | Tool-driven verification | Implemented but unexercised control passes | Executed probe | Proof Runner | Probe output |
| Record state | Result envelope, lifecycle event, evidence link | Markdown record is enough | Durable, queryable record shape | Deterministic write path | State cannot be reconstructed | Read-after-write and schema validation | Recorder | State register, verdict store |
| Learn and standardize | Repeated failure, escaped defect, reversal | Learning can stay in prose | Update durable artifact | Reflexion with governed memory | Lesson does not change baseline | Artifact probe | Learning Node | Test, policy, runbook, backlog |
| Monitor effectiveness | Observation window, guardrails, recurrence | Immediate validation proves outcome | Sustained improvement or failure | Scheduled monitor | Early closure before sample floor | Sustained monitoring | Effectiveness Monitor | Metrics and drift monitors |
| Retire or continue | Low value, duplicate loop, obsolete control | Active loops always add value | Repeat, pause, block, roll back, or retire | Graph of Thoughts | Loop keeps running despite no signal | Meta-review | Loop health governor | Metrics, owner review |

## Prioritized Improvement Plan

### Phase 1: Normalize The Source Of Truth

1. Move the production-grade standard into `standards/`.
2. Create `CONTROL_CATALOG.yaml` from `LC-001` through `LC-109`.
3. Create `loops.catalog.yaml` with all 108 loop IDs, names, categories, trigger, run, output, cadence, and default risk profile.
4. Modify the generator to produce Markdown from these machine-readable sources.

### Phase 2: Add Runtime Descriptors

1. Create one compact runtime descriptor per loop.
2. Add control applicability mapping.
3. Add loop-to-loop graph edges.
4. Add state machine transitions.
5. Add owner and evidence registries.

### Phase 3: Add Executable Proof

1. Create probe registry.
2. Add golden tasks per loop.
3. Add corpus validator.
4. Add result-envelope JSON schema.
5. Add proof freshness and scope-binding checks.

### Phase 4: Add Agentic Orchestration

1. Implement Trigger Router.
2. Implement Qualification Gate.
3. Implement Evidence Collector.
4. Implement Control Applicability Mapper.
5. Implement Proof Runner.
6. Implement Recorder and Learning Node.

### Phase 5: Add Governance And Meta-Review

1. Add owner succession checks.
2. Add loop health dashboard data.
3. Add oscillation and loop-storm detection.
4. Add retirement review.
5. Add release gates for activating loops from DRAFT to PILOT to ACTIVE.

## Recommended Next Concrete Files

Create these next:

```text
standards/production-grade-continuous-improvement-loop.md
controls/CONTROL_CATALOG.yaml
schemas/loop-descriptor.schema.json
schemas/result-envelope.schema.json
schemas/control-coverage.schema.json
runtime/loops.catalog.yaml
runtime/control-applicability.yaml
runtime/loop_graph.yaml
runtime/state_machine.yaml
owners/OWNER_REGISTRY.yaml
evidence/EVIDENCE_LOCATION_REGISTRY.yaml
probes/PROBE_REGISTRY.yaml
evals/GOLDEN_TASKS.yaml
scripts/validate_loop_corpus.py
```

## Open Risks And Expert Questions Still Needed

1. Which loops are intended to become executable skills first?
2. Which loops are documentation-only, gates, scheduled monitors, event-driven agents, or human procedures?
3. Who are the real policy owners and gate owners?
4. What systems of record should evidence come from?
5. What runtime will orchestrate the loops: Codex skills, MCP tools, LangGraph, CI/CD, scheduled jobs, or a custom service?
6. Should every loop remain fully expanded, or should the repo support both expanded human docs and compact runtime descriptors?
7. What is the first high-value pilot loop to harden end to end?

## Bottom Line

The corpus has enough language to describe a production-grade loop. The next gap is execution discipline.

The most valuable improvement is to create a machine-readable backbone: catalog, control applicability matrix, loop graph, state machine, schemas, owner registry, evidence registry, probe registry, golden tasks, and corpus validator.

Once those exist, the 108 Markdown files become useful views over a real agentic control system instead of being the system themselves.
