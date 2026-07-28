# Agent Context Management Loop

## Loop Identity

- Loop number: 70
- Loop name: Agent Context Management Loop
- Category: 10. Agentic AI Execution and Orchestration
- Skill ID: `loop-070-agent-context-management-loop`
- Version: `1.0`
- Lifecycle status: `DRAFT`
- Effective date: To be assigned by the loop owner
- Change history reference: `LOOP_LOG.md` or the authoritative change record
- Minimum cadence: Every task or reasoning cycle
- Source: `SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md`
- Production-grade standard: `standards/production-grade-continuous-improvement-loop.md`

## Purpose

Outcome to improve: Minimal sufficient context package with source traceability.

Primary measurable outcome: Minimal sufficient context package with source traceability.

Business value: Improves confidence, speed, safety, and accountability for Agent Context Management Loop decisions by tying every action to evidence and proof.

Risk reduced: Reduces the risk that Agent Context Management Loop produces unowned gaps, stale evidence, unproven claims, unsafe actions, repeated failures, or ineffective improvements.

Scope: Agentic AI Execution and Orchestration control point for Agent Context Management Loop.

Exclusions: Responsibilities owned by adjacent loops remain outside this loop unless the trigger, evidence, and authority clearly route them here.

Systems and data covered: Systems, workflows, data, models, agents, controls, evidence, and decisions directly involved in `Agent Context Management Loop`.

Permitted actions:

- Qualify or reject the trigger for this loop
- Collect and reconcile authoritative evidence
- Classify findings, risk tier, proof state, and owner status
- Recommend, execute, or request authorized remediation
- Validate immediate correctness and required proof
- Record evidence, learning, standards updates, and next monitoring action

Prohibited actions:

- Do not claim broad SDLC ownership outside this loop's outcome.
- Do not proceed when authority is unmapped, forked, or conflicted.
- Do not accept declared capability as proof when an executable probe is required.
- Do not treat action completion as outcome effectiveness.
- Do not silently use stale, conflicted, untrusted, or scope-mismatched evidence.

Stakeholders:

- Business owner
- Technical owner
- Policy owner
- Gate owner
- Executor
- Validator
- Risk owner
- Operator
- Escalation authority

Authoritative owner references:

- Policy owner reference: To be assigned
- Gate owner reference: To be assigned
- Executor reference: To be assigned
- Validator reference: To be assigned where required
- Authoritative evidence location: To be assigned

## Standard Loop Sequence

```text
Trigger -> Qualify -> Observe -> Diagnose -> Prioritize -> Plan -> Authorize -> Execute -> Validate -> Prove -> Record -> Learn -> Standardize -> Monitor effectiveness -> Close, repeat, pause, block, roll back, or retire
```

Recovery is available during execution and validation: retry, compensate, roll back, isolate, safe-stop, or escalate.

## Production-Grade Core Principles

- One loop owns one measurable outcome.
- One authoritative owner exists per concern.
- Declared is not proven.
- Action applied is not outcome proven.
- Risk controls the depth of proof.
- Recovery is part of execution.
- Conditional decisions must expire.
- Every successful correction changes the baseline.
- Every loop must detect oscillation.
- Evidence must be scope-bound and current.

## Durable State and Lifecycle Events

Use existing authoritative state artifacts rather than inventing a competing universal state field.

Recommended state artifacts:

- `LOOP_LOG.md`
- `METRICS.md`
- `verdicts/`
- `GOVERNANCE.md`
- Release records
- Evaluation records
- Audit evidence
- Owner-specific state files

Lifecycle event states:

```text
TRIGGERED
QUALIFIED
OBSERVED
DIAGNOSED
PRIORITIZED
PLANNED
AUTHORIZED
ACTION_IN_PROGRESS
ACTION_APPLIED
VALIDATION_PASSED
VALIDATION_FAILED
PROOF_GREEN
PROOF_FAILED
EFFECTIVENESS_PENDING
EFFECTIVENESS_PROVEN
EFFECTIVENESS_FAILED
INSUFFICIENT_EVIDENCE
CONDITIONAL_ACTIVE
CONDITIONAL_EXPIRED
BLOCKED
ROLLED_BACK
PAUSED
RETIRED
```

Critical invariant: `ACTION_APPLIED` is never equivalent to `EFFECTIVENESS_PROVEN`.

Lifecycle status values:

```text
DRAFT
PILOT
ACTIVE
RESTRICTED
PAUSED
DEPRECATED
RETIRED
```

## Proof States and Gate Rules

Proof-state model:

| Proof state | Meaning | Gate eligible |
|---|---|---:|
| `UNMAPPED` | No authoritative owner or evidence source has been identified. | No |
| `DECLARED` | A document, policy, schema, or skill says the capability exists. | No |
| `IMPLEMENTED` | Code, configuration, infrastructure, or workflow appears to implement the capability. | Only when static existence is the complete requirement |
| `EXERCISED` | The required probe or drill executed, regardless of result. | No |
| `PROVEN` | The required probe ran green under the required scope and acceptance criteria. | Yes, while current |
| `SUSTAINED` | The control remained effective across the required observation period or repeated executions. | Yes |
| `FAILED` | The executed probe failed its acceptance criteria. | No |
| `EXPIRED` | Earlier proof is no longer valid for the current time, version, environment, or scope. | No |

Gate rules:

1. No proof, no pass.
2. Expired proof is equivalent to missing proof.
3. Scope-mismatched proof is not reusable.
4. Rollback and containment remain available even when forward progression is blocked.
5. A safety or security failure overrides normal promotion or observation windows.
6. An exception does not erase a failed control. It records an authorized temporary deviation.
7. A conditional verdict cannot auto-renew or silently become a pass.
8. A material owner conflict blocks high-risk progression.
9. A gate must consume evidence from the authoritative owner, not a copied summary.
10. A control that can be executed must not be accepted through declaration alone.

Proof scope must bind to the relevant product, component, workflow, release, build, environment, data class, risk tier, configuration, model, provider, prompt, evaluation version, tool contract, schema, migration, probe version, acceptance threshold, execution date, and evidence retention period.

## Risk-Tiered Applicability

Default risk tier for this loop: `R3`.

Risk tiers:

| Tier | Description |
|---|---|
| `R0: Experimental` | Local, disposable, no production access, no sensitive data, and no persistent external effect. |
| `R1: Low` | Internal, limited impact, reversible, and no consequential production action. |
| `R2: Moderate` | Production or user-facing behavior with reversible effects and controlled blast radius. |
| `R3: High` | Sensitive data, privileged tools, regulated workflow, external communication, material customer impact, or consequential action. |
| `R4: Critical` | Irreversible, safety-critical, legally binding, financially consequential, cross-tenant, infrastructure-wide, or catastrophic-loss potential. |

Effective risk tier uses the highest applicable tier across environment, data sensitivity, user impact, external side effects, regulatory consequence, financial consequence, security privilege, reversibility, blast radius, agent autonomy, and maximum possible loss.

Control inheritance:

| Minimum tier | Default control expectation |
|---|---|
| `R0+` | Identity, purpose, scope, trigger, input, output, owner, basic validation, execution limit, and stop condition |
| `R1+` | Versioning, dependencies, baseline, target, metrics, traceability, idempotency, retry taxonomy, evidence, and regression checks |
| `R2+` | Proven rollback, circuit breaker, non-regression, side-effect analysis, effectiveness window, monitoring, and expiring exceptions |
| `R3+` | Human approval, separation of duties, independent validation, privacy and compliance controls, kill switch, forensic evidence, and adversarial testing |
| `R4` | Dual control, catastrophic containment drill, maximum-loss bound, business continuity, independent authority, and sustained proof |

## Authority and Composition

Authority roles:

| Role | Responsibility |
|---|---|
| Policy owner | Defines the authoritative rule and acceptance criteria |
| Gate owner | Makes or records the progression verdict |
| Executor | Performs the approved action |
| Validator | Independently verifies the required result where needed |
| Business owner | Owns the intended business outcome |
| Technical owner | Owns implementation and operational integrity |
| Risk owner | Accepts residual risk when authorized |
| Operator | Runs the loop or responds to findings |
| Escalation authority | Resolves blocked, conflicting, or critical conditions |

One-authority rule:

- Record one policy owner.
- Record one gate owner.
- Record zero or more executors.
- Record one validator when independent verification is required.
- Record one authoritative evidence location.

Authority conflict states:

```text
UNMAPPED_AUTHORITY
OWNER_CONFLICT
FORKED_AUTHORITY
NON_AUTHORITATIVE_EVIDENCE
THRESHOLD_CONFLICT
```

## Trigger

New task, reasoning step, context-window pressure, or retrieval request.

Trigger types to support:

- Event
- Schedule
- Threshold
- Request
- Incident
- Code or configuration change
- Data or schema change
- Model or prompt change
- Risk change
- Capability increase
- Regulation or policy change
- Evidence expiry

Trigger definition fields:

- Trigger source: To be assigned
- Trigger condition: New task, reasoning step, context-window pressure, or retrieval request.
- Priority: To be calculated from impact, urgency, risk, and confidence
- Deduplication key: `loop-070-agent-context-management-loop:<asset-or-scope>:<trigger-signature>`
- Suppression rules: Suppress duplicates only when an active authoritative owner is already handling the same concern
- Minimum cadence: Every task or reasoning cycle
- Emergency trigger: Safety, security, customer-impacting, regulatory, or irreversible-risk condition
- Trigger evidence: Required before qualification can pass

## Qualification

Before full execution, determine:

- Does the event belong to this loop?
- Is the affected asset in scope?
- Is the input complete and fresh?
- Is the concern already being handled?
- Is another loop the primary owner?
- Does the event meet the required threshold?
- Is the current environment authorized?
- Is the risk tier correctly calculated?
- Is required proof already current?

Qualification outcomes:

- `QUALIFIED`
- `INPUT_INCOMPLETE`
- `INPUT_STALE`
- `INPUT_CONFLICTED`
- `INPUT_UNTRUSTED`
- `INPUT_OUT_OF_SCOPE`
- `DUPLICATE_HANDLING`
- `PRIMARY_OWNER_IS_ADJACENT_LOOP`
- `INSUFFICIENT_EVIDENCE`

## Run

Preserve instruction hierarchy, retrieve authoritative material, separate untrusted content, remove irrelevant information, compress safely, maintain provenance, and enforce token limits.

## Output

Minimal sufficient context package with source traceability.

## Inputs

Required:

- Trigger evidence
- Current state observations
- Relevant standards, policies, thresholds, and acceptance criteria
- Owner and system context
- Model, prompt, tool, retrieval, memory, evaluation, and autonomy evidence

Optional:

- Historical loop records
- Comparable prior incidents, findings, or decisions
- Stakeholder notes, user reports, or operational context
- Benchmark or baseline data

Authoritative sources:

- Product, engineering, security, operations, governance, or support systems of record
- Source-controlled requirements, code, tests, runbooks, policies, and architecture records
- Logs, metrics, traces, reports, approvals, and validated evidence artifacts

Input quality requirements:

- Source priority: Prefer authoritative system of record over copied summaries.
- Data owner: Must be named for every gate-relevant source.
- Freshness requirement: Must be defined per source and risk tier.
- Completeness requirement: Must cover the declared scope, not a convenient subset.
- Accuracy requirement: Must be validated against the source owner or executable check where possible.
- Format and schema: Must be versioned when machine-consumed.
- Authenticity and signature requirements: Required for release, audit, security, supply-chain, model, agent, and regulated evidence.
- Sensitivity classification: Required before evidence is shared or retained.
- Lineage: Must identify origin, transformation, and timestamp.
- Duplicate handling: Must deduplicate without suppressing active material differences.
- Conflict-resolution rule: Apply declared source priority, reconcile through the authoritative owner, reduce confidence, and escalate material disagreement.

Input quality states:

```text
INPUT_VALID
INPUT_INCOMPLETE
INPUT_STALE
INPUT_CONFLICTED
INPUT_UNTRUSTED
INPUT_OUT_OF_SCOPE
```

## Preconditions

Permissions required:

- Read access to the relevant evidence sources
- Write access to the loop record or evidence repository
- Authority to recommend, execute, block, escalate, or request approval according to risk

Minimum data required:

- A qualifying trigger
- Current evidence for the affected system, process, product, model, agent, or control
- A named owner or escalation path
- Validation criteria for the expected result

Dependency checks:

- Confirm related loops that must receive evidence
- Confirm environment, data, tooling, and approval availability
- Confirm whether the action is reversible or requires explicit recovery planning

State-changing action preconditions:

- Required systems are available.
- Required permissions are valid.
- Dependencies are healthy.
- Target environment is correct.
- No conflicting operation is active.
- Backup or checkpoint exists where required.
- Approval is current.
- Data and configuration versions match the plan.
- Resource capacity is sufficient.
- Rollback, compensation, or safe-stop path is available.

Entry criteria decide whether the loop should start. Preconditions decide whether the loop can safely proceed.

## Execution

1. Observe current state.
2. Assess against policy, standards, thresholds, and expected outcomes.
3. Classify findings by severity, urgency, confidence, and ownership.
4. Select action: pass, conditionally pass, remediate, escalate, block, or stop.
5. Execute the authorized fix or recommendation.
6. Validate the result with evidence.
7. Record evidence and decisions.
8. Learn from the result and update tests, standards, runbooks, or controls.

Execution plan requirements:

- Action sequence
- Owner for each action
- Expected state transition
- Preconditions
- Idempotency key or replay control
- Timeout
- Retry and backoff policy
- Resource budget
- Concurrency and conflict policy
- Checkpoint or resume behavior
- Validation method
- Recovery path
- Communication requirement

Runtime controls:

- Idempotency: repeated operation must produce one logical effect.
- Concurrency control: conflicting parallel runs must be prevented, serialized, locked, or reconciled.
- Resource limits: time, money, tokens, compute, calls, records, transactions, concurrency, and human effort must stop or escalate before exceeding bounds.
- Timeout: hung external calls or steps must cancel, isolate, or reach a known state.
- Retry and backoff: transient failures retry within policy; deterministic failures do not loop indefinitely.
- Circuit breaker: repeated failure opens the breaker, cools down, and recovers according to the authoritative contract.
- Durable lifecycle events: pause, resume, failure, and observation-window states must be reconstructable.
- Checkpoints: interruption must resume without duplicate effects when the loop is long-running or multi-step.

## Decisions

Allowed outcomes:

- Pass
- Pass with conditions
- Remediate
- Escalate
- Block
- Stop

Approval authority:

- Loop owner for routine decisions
- Control owner for policy, security, compliance, or risk acceptance
- Product or engineering owner for scope, delivery, or user-impact decisions
- Incident commander, release manager, or accountable executive for high-impact actions

Decision rules:

- Pass only when the expected outcome is proven by evidence.
- Pass with conditions only when residual gaps are explicit, owned, and time-bound.
- Remediate when the gap is confirmed and can be fixed within this loop's authority.
- Escalate when authority, evidence, impact, or ownership is insufficient.
- Block when proceeding would violate policy, safety, security, quality, or release criteria.
- Stop when the trigger is invalid, duplicated, retired, or routed to another loop.

## Outputs

Primary artifact:

- Loop record for `loop-070-agent-context-management-loop`

Machine-readable result:

- Common result envelope using the JSON structure below

Human-readable summary:

- What triggered the loop, what evidence was observed, what decision was made, what changed, and what remains

Downstream events:

- Backlog Refinement Loop
- Risk Management Loop
- Model Evaluation and Benchmarking Loop
- Agent Guardrail Loop

## Quality Controls

Acceptance thresholds:

- Trigger is qualified and assigned.
- Evidence is current, relevant, and traceable.
- Diagnosis names the gap between expected and actual state.
- Fix or decision is authorized at the correct level.
- Validation proves the result or clearly identifies remaining gaps.

Validation checks:

- Re-run the relevant test, scan, review, simulation, deployment, monitoring check, or evidence collection.
- Compare result with the expected outcome and prior baseline.
- Confirm no material regression or new unowned risk was introduced.

Validation dimensions:

- Immediate correctness
- Expected state transition
- Non-regression
- Side effects
- Security
- Privacy
- Compliance
- Accessibility where applicable
- Cost and performance guardrails
- User, customer, or operator impact

Test oracle:

- Define the approved source of truth for expected behavior.
- Compare actual output against the oracle.
- Record oracle version, owner, acceptance threshold, and known limitations.

Independent validation:

- Required for R3 and R4 where executor bias, hidden failure, or consequential impact is possible.
- Validator must be attributable and separate where separation of duties applies.

Proof methods:

- `STATIC`: documented or structural proof.
- `EXECUTED_PROBE`: executable behavior check.
- `DRY_RUN`: non-mutating execution path.
- `REPLAY_PROBE`: repeated operation or historical scenario replay.
- `FAULT_INJECTION`: controlled failure test.
- `ROLLBACK_DRILL`: restore to accepted prior state.
- `FAILOVER_DRILL`: alternate provider, model, tool, system, or mode works within limits.
- `AUTHORIZATION_PROBE`: unauthorized path is denied and authorized path is attributable.
- `BOUNDARY_PROBE`: threshold edge cases produce expected verdicts.
- `REGRESSION_PROBE`: existing required behavior remains green.
- `CONTROL_TEST`: compliance or policy control maps to executed evidence.
- `FORENSIC_DRILL`: independent reviewer can reconstruct execution.
- `SUSTAINED_MONITORING`: target remains met through the required window.

False positive controls:

- Verify findings against authoritative sources before action.
- Deduplicate against active records.
- Require confidence notes for ambiguous evidence.

False negative controls:

- Use multiple evidence sources where available.
- Check adjacent loops for related missed signals.
- Preserve failed validations as future regression cases.

## Conditional Verdict Contract

A conditional verdict is allowed only when the governing authority permits temporary progression with bounded exposure.

Required fields:

- Condition ID
- Reason
- Missing or weak evidence
- Compensating controls
- Owner
- Approver
- Start time
- Expiry time
- Exposure limit
- Monitoring requirement
- Terminal outcomes

Rules:

- A conditional verdict cannot auto-renew.
- Missing evidence at expiry becomes failure, not pass.
- Conditions must be visible to downstream gates.
- Conditional progression must not hide failed controls.

## Oscillation Detection and Stabilization

Purpose: detect repeated reversals of the same decision, verdict, priority, risk tier, owner, or remediation path.

Required controls:

- Decision key
- Reversal counter
- Reversal time window
- Materiality floor
- Hysteresis threshold
- Minimum dwell period
- Escalation rule
- Owner for stabilization

Suggested probes:

- Alternating borderline signals do not cause repeated reversal.
- Genuine high-impact overrides still work.
- Owner conflict produces escalation rather than silent reversal.

Oscillation verdicts:

- `STABLE`
- `OSCILLATION_DETECTED`
- `OSCILLATION_POLICY_CONFLICT`
- `OSCILLATION_OWNER_CONFLICT`

## Baseline, Target, and Measurement

Baseline:

- Current state metric: To be measured for `Agent Context Management Loop`
- Baseline source: Authoritative metrics, logs, records, evaluations, or audit evidence
- Baseline date: To be recorded
- Baseline confidence: To be recorded

Target:

- Metric: Primary measurable outcome for `Agent Context Management Loop`
- Formula: To be defined by the policy owner
- Target value: To be assigned
- Time horizon: To be assigned
- Population or segment: To be assigned
- Confidence requirement: To be assigned by risk tier
- Guardrails: Safety, security, privacy, quality, cost, performance, accessibility, compliance, and user-impact limits
- Owner: Business owner and gate owner
- Source: Authoritative evidence source
- Observation window: Required when outcome effectiveness is not immediately observable

Metric types:

- Leading metric: Indicates whether the loop is moving in the intended direction.
- Lagging metric: Confirms the final outcome after the required observation period.
- Guardrail metric: Ensures the primary improvement does not create unacceptable harm elsewhere.
- Health metric: Measures loop reliability, cost, noise, recurrence, and proof freshness.

Metric definition fields:

- Name
- Purpose
- Formula
- Unit
- Data source
- Owner
- Collection cadence
- Reporting cadence
- Thresholds
- Segment
- Exclusions
- Freshness requirement
- Known limitations

## Observation Window and Causal Confidence

Observation window:

- Start condition: Validation passed or proof green.
- Minimum duration: Defined by risk tier, metric behavior, and control owner.
- Sample-size floor: Required for statistical, traffic-based, model, security, or user-experience evidence.
- Early closure rule: Closure is blocked until the observation requirement is met or an explicit insufficient-evidence state is recorded.

Causal confidence method:

- Use before-and-after comparison, experiment, holdout, canary, cohort analysis, synthetic probe, replay, or expert review where appropriate.
- Record why the selected method is sufficient for the risk tier.
- Separate correlation from demonstrated causation when evidence is weak.

## Decision Design and Prioritization

Assessment rules:

- Classify findings with explicit criteria.
- Use decision tables for representative cases where possible.
- Record confidence, severity, urgency, reversibility, and owner status.

Prioritization factors:

- Value
- Impact
- Urgency
- Probability
- Confidence
- Cost of delay
- Effort
- Dependency complexity
- Blast radius
- Risk tier

Tie rules:

- Safety, security, privacy, compliance, customer harm, and irreversible risk outrank convenience.
- Higher-confidence high-impact findings outrank speculative low-impact findings.
- Owner conflict or missing authority blocks high-risk progression.

## Safety and Governance

Prohibited actions:

- Do not hide, delete, or weaken evidence.
- Do not bypass required approvals.
- Do not expand scope without requalification.
- Do not mark the loop complete without validation evidence.

Data handling rules:

- Use the minimum data required.
- Protect secrets, personal data, regulated data, and proprietary information.
- Preserve audit logs and decision records according to retention rules.

Human approval points:

- High-impact change
- Irreversible action
- Security, privacy, compliance, legal, financial, or customer-impacting exception
- Residual-risk acceptance

Audit requirements:

- Record trigger, evidence, decision, authorization, action, validation, recovery, and final state.
- Keep links to source systems and artifacts.
- Preserve timestamps and responsible owners.

Security controls:

- Apply least privilege.
- Protect secrets and credentials.
- Validate authorization boundaries.
- Preserve tamper-resistant audit evidence for privileged or consequential actions.
- Run threat-appropriate static, dynamic, negative, adversarial, or forensic checks where applicable.

Privacy and data protection:

- Map personal, confidential, regulated, or customer data.
- Minimize data collection and retention.
- Confirm purpose, consent, residency, retention, deletion, and access rules.
- Mask or synthesize data for tests when required.

Legal, regulatory, and policy mapping:

- Identify applicable laws, standards, contracts, policies, and audit controls.
- Map obligations to controls, owners, evidence, and retention.
- Escalate unmapped obligations.

Supply-chain integrity:

- Validate provenance of source, dependencies, models, datasets, tools, plugins, MCP servers, containers, and artifacts where applicable.
- Require signatures, attestations, software bills of materials, or supplier-risk decisions when risk tier requires them.

## Communication and Service Levels

Notification rules:

- Define who must know, who must act, and who must approve.
- Messages must include trigger, scope, impact, owner, decision, action required, deadline, and evidence link.
- Avoid notifying irrelevant parties when evidence is sensitive or action is not required.

Service-level expectations:

- Acknowledgement time
- Qualification time
- Diagnosis time
- Decision time
- Remediation time
- Validation time
- Escalation time
- Effectiveness review time

SLA breaches must become evidence and may trigger escalation, reprioritization, or another loop.

## Learning, Corrective Action, and Standardization

Root-cause analysis:

- Required for material, repeated, systemic, high-risk, or escaped failures.
- Must identify failed controls and contributing factors, not only the visible symptom.

Corrective action:

- Fix the current gap.
- Validate the immediate correction.

Preventive action:

- Add a control, test, monitor, policy, prompt, runbook, default, architecture rule, or backlog item that blocks recurrence.

Learning destination:

- Test
- Evaluation case
- Policy
- Prompt
- Runbook
- Default
- Standard
- Architecture rule
- Backlog item
- Training material

Regression-case creation:

- When a reproducible failure or edge case is found, preserve it as a regression case.
- The regression case should fail before correction and pass after correction when feasible.

Standard or policy update:

- Successful corrections must update the authoritative operating baseline, not remain tribal knowledge.

## Effectiveness Verification

Action completion, immediate validation, control proof, outcome proof, and sustained improvement are separate states.

Effectiveness proof requires:

- Target met.
- Guardrails intact.
- Observation window satisfied.
- Sample-size floor met where applicable.
- Causal-confidence method recorded.
- Residual risk accepted only by the authorized risk owner.

## Drift, Assumptions, Convergence, and Retirement

Assumption monitoring:

- Record material assumptions.
- Test assumptions at cadence.
- Invalid assumptions trigger re-evaluation.

Drift monitoring:

- Monitor inputs, models, policies, configurations, owners, thresholds, evidence, environments, and dependencies.
- Expired proof must be treated as missing proof.

Convergence criteria:

- The loop stops iterating when the target is met, the next action has no value, the risk is accepted, or authority blocks further action.

Stop conditions:

- Unsafe continuation
- Missing authority
- Expired approval
- Resource limit exceeded
- Repeated deterministic failure
- Circuit breaker open
- No-value iteration
- Retirement trigger

Obsolescence and retirement:

- Retire when the loop, product, control, dependency, owner model, or evidence source no longer creates useful signal.
- Retirement must handle triggers, credentials, dependencies, evidence, downstream consumers, and replacement ownership.

Owner succession:

- Define backup owners.
- Prove access and authority transfer where continuity matters.

Loop health and meta-review:

- Review value, noise, cost, recurrence, proof freshness, owner health, drift, duplication, and retirement at cadence.

## Recovery

Retry limit: 1 controlled retry unless a runbook defines a different limit.

Retry conditions:

- Evidence source timeout
- Transient tool or environment failure
- Validation blocked by temporary dependency

Rollback or compensation:

- Revert the change, disable the flag, restore the prior artifact, roll back deployment, restore data, or compensate through an approved runbook.

Escalation path:

- Loop owner -> category owner -> accountable control owner -> executive or incident authority when required

Failure taxonomy:

- Transient dependency failure
- Deterministic validation failure
- Input quality failure
- Authority or approval failure
- Resource-limit failure
- Timeout
- Concurrency conflict
- Security, privacy, or compliance failure
- Rollback, compensation, or failover failure
- Effectiveness failure

Safe failure state:

- No unapproved action continues.
- Partial changes are rolled back, compensated, isolated, or explicitly recorded.
- Evidence is preserved.
- Owners and downstream loops are notified.
- Restart requires current authorization when risk tier requires it.

Rollback and compensation:

- Rollback is required when the action is reversible and changes persistent or production state.
- Compensation is required when direct rollback is impossible or incomplete.
- Recovery validation must independently confirm recovered state, data consistency, and service health.

Manual override and kill switch:

- Manual override is required when automation can make a wrong or unsafe decision.
- Kill switch is required when the loop can cause fast, broad, privileged, high-impact, or hard-to-reverse effects.
- Override and kill-switch use must be attributable, authorized, and audited.

## Metrics

Effectiveness:

- Outcome improvement trend
- Repeat-gap rate
- Validation pass rate

Efficiency:

- Time from trigger to qualification
- Time from diagnosis to validated result
- Rework rate

Risk:

- Open high-severity findings
- Residual-risk acceptances
- Blocked or escalated decisions

Trend:

- Trigger volume over time
- Recurrence by root cause
- Standard adoption and monitor effectiveness

## Evidence

Logs:

- Loop execution log
- Tool, pipeline, runtime, system, model, agent, or process logs relevant to this loop

Reports:

- Evidence summary
- Findings and remediation report
- Validation result

Approvals:

- Review approvals
- Exception or risk acceptance
- Release, security, compliance, product, or operations signoff where applicable

Retention period: Follow the governing policy for the product, system, data class, and regulatory environment.

## Ownership

Business owner: Assigned owner for the product, service, process, or control outcome.

Technical owner: Assigned engineering, platform, data, security, AI, or operations owner.

Control owner: Assigned person accountable for policy, auditability, risk, and evidence quality.

## Cadence

Minimum frequency: Every task or reasoning cycle

Review frequency: Review loop health at least monthly unless the category requires a stricter cadence.

## Reference-Only Loop Descriptor

```yaml
loop_id: "loop-070-agent-context-management-loop"
name: "Agent Context Management Loop"
version: "1.0"
status: "DRAFT | PILOT | ACTIVE | RESTRICTED | PAUSED | DEPRECATED | RETIRED"

purpose_ref: "Purpose section in this file"
scope_ref: "Purpose and boundaries section in this file"
composition_map_ref: ""
state_register_ref: ""
gate_rules_ref: ""

risk:
  default_tier: "R3"
  calculation_ref: "Risk-Tiered Applicability section in this file"

authority_refs:
  policy_owner_ref: ""
  gate_owner_ref: ""
  executor_ref: ""
  validator_ref: ""

evidence_refs:
  authoritative_sources: []
  proof_locations: []
  retention_policy_ref: ""

control_manifest_ref: "Control Coverage Manifest section in this file"
result_envelope_ref: "Standard Result Envelope section in this file"
```

## Control Coverage Manifest

Use one record per applicable control.

```yaml
control_id: LC-000
control_name: ""
requirement: ""

minimum_risk_tier: R0
applies_when: []

authority:
  policy_owner_ref: ""
  gate_owner_ref: ""
  executor_ref: ""
  validator_ref: ""

source_of_truth:
  policy_ref: ""
  implementation_ref: ""
  evidence_ref: ""

proof:
  proof_required: ""
  probe_ref: ""
  acceptance_ref: ""
  last_execution_ref: ""
  proof_state: "UNMAPPED | DECLARED | IMPLEMENTED | EXERCISED | PROVEN | SUSTAINED | FAILED | EXPIRED"
  scope_binding: ""
  freshness_expires_at: ""

decision:
  verdict: "pass | conditional | remediate | escalate | block | failed"
  reason: ""
  residual_risk_ref: ""

exceptions:
  exception_ref: ""
  compensating_controls: []
  expires_at: ""
```

## Recommended Artifact Set

```text
SKILL.md
composition-map.md
CONTROL_CATALOG.yaml
LOOP_DESCRIPTOR.yaml
PROBES/
VERDICTS/
LOOP_LOG.md
METRICS.md
GOVERNANCE.md
RUNBOOK.md
EVIDENCE/
EXCEPTIONS/
CONDITIONALS/
```

Not every loop must own each artifact. The composition map should identify the authoritative location.

## Audit Procedure

1. Identify the loop's single primary outcome.
2. Calculate the effective risk tier.
3. Load the applicable control catalog entries.
4. Resolve one policy owner and one gate owner per control.
5. Mark any unresolved control as `UNMAPPED`.
6. Identify the required proof method for each applicable control.
7. Confirm scope binding and proof freshness.
8. Execute missing or expired probes.
9. Evaluate immediate validation and non-regression.
10. Apply the authoritative gate.
11. Create a bounded conditional contract when explicitly allowed.
12. Record action state separately from outcome effectiveness.
13. Monitor the required observation window.
14. Convert failures into corrective, preventive, and regression actions.
15. Update the operating baseline.
16. Count decision reversals and apply oscillation controls.
17. Close only after all applicable controls reach valid terminal states.

## Loop Completion Rule

Completion claims:

| Claim | Required evidence |
|---|---|
| Defined | Requirement and authority are documented |
| Implemented | The owner skill or system contains the control |
| Action applied | The approved change executed |
| Technically validated | Immediate postconditions passed |
| Control proven | The required probe or drill ran green |
| Outcome pending | The observation period remains open |
| Outcome proven | The target was met with guardrails intact |
| Sustained | The result remained effective for the required period |
| Standardized | Tests, policies, defaults, and baselines were updated |
| Closed | No unresolved condition, expired evidence, unmapped authority, or unowned action remains |

A loop may claim successful closure only when all applicable controls are mapped, required probes are green, proof is current and scope-bound, action state and outcome state are separate, guardrails remain intact, learning has updated a durable artifact, and no unresolved condition remains.

## Loop Record Template

```markdown
## Loop Record

- Loop: Agent Context Management Loop
- Outcome: Minimal sufficient context package with source traceability.
- Trigger: New task, reasoning step, context-window pressure, or retrieval request.
- Qualified:
- Owner:
- Evidence observed:
- Diagnosis:
- Priority:
- Plan:
- Authorization:
- Execution:
- Validation:
- Recovery:
- Learning:
- Standard updated:
- Effectiveness monitor:
- Final state:
```

## Standard Result Envelope

```json
{
  "loop_id": "loop-070-agent-context-management-loop",
  "loop_version": "1.0",
  "execution_id": "unique-execution-id",
  "correlation_id": "cross-loop-correlation-id",
  "risk_tier": "R0 | R1 | R2 | R3 | R4",
  "authority": {
    "composition_map_ref": "",
    "policy_owner_ref": "",
    "gate_owner_ref": "",
    "executor_ref": "",
    "validator_ref": ""
  },
  "trigger": {
    "type": "event | schedule | threshold | request | incident | change | expiry",
    "source": "",
    "deduplication_key": "",
    "evidence_ref": ""
  },
  "scope": {
    "product": "",
    "component": "",
    "environment": "",
    "release": "",
    "data_class": "",
    "model_or_agent": "",
    "configuration": ""
  },
  "input_quality": {
    "state": "INPUT_VALID | INPUT_INCOMPLETE | INPUT_STALE | INPUT_CONFLICTED | INPUT_UNTRUSTED | INPUT_OUT_OF_SCOPE",
    "freshness": "",
    "lineage_ref": "",
    "conflicts": []
  },
  "state": {
    "lifecycle": "TRIGGERED | QUALIFIED | OBSERVED | DIAGNOSED | PRIORITIZED | PLANNED | AUTHORIZED | ACTION_IN_PROGRESS | ACTION_APPLIED | VALIDATION_PASSED | VALIDATION_FAILED | PROOF_GREEN | PROOF_FAILED | EFFECTIVENESS_PENDING | EFFECTIVENESS_PROVEN | EFFECTIVENESS_FAILED | INSUFFICIENT_EVIDENCE | CONDITIONAL_ACTIVE | CONDITIONAL_EXPIRED | BLOCKED | ROLLED_BACK | PAUSED | RETIRED",
    "proof_state": "UNMAPPED | DECLARED | IMPLEMENTED | EXERCISED | PROVEN | SUSTAINED | FAILED | EXPIRED",
    "status": "pass | conditional | remediate | escalate | block | failed"
  },
  "findings": [],
  "actions_taken": [],
  "actions_required": [],
  "validation": {
    "method": "",
    "oracle_ref": "",
    "non_regression": "",
    "side_effects": "",
    "result": ""
  },
  "proof": {
    "probe_ref": "",
    "acceptance_ref": "",
    "scope_binding": "",
    "executed_at": "",
    "expires_at": "",
    "result": ""
  },
  "effectiveness": {
    "baseline_ref": "",
    "target_ref": "",
    "observation_window": "",
    "guardrails": [],
    "causal_confidence": "",
    "result": ""
  },
  "recovery": {
    "safe_failure_state": "",
    "rollback_ref": "",
    "compensation_ref": "",
    "fallback_ref": ""
  },
  "conditional": {
    "condition_id": "",
    "owner": "",
    "expires_at": "",
    "terminal_outcomes": []
  },
  "oscillation": {
    "decision_key": "",
    "reversal_count": 0,
    "verdict": "STABLE | OSCILLATION_DETECTED | OSCILLATION_POLICY_CONFLICT | OSCILLATION_OWNER_CONFLICT"
  },
  "evidence": [],
  "metrics": {},
  "owner": "",
  "next_execution": "",
  "timestamp": ""
}
```

---

# Production-Grade Template Appendix

The following appendix is copied from the production-grade template so this loop file retains the complete checklist, named failure states, definition of done, review questions, implementation sequence, and final operating standard.

# Complete Risk-Tiered Control Checklist

The following catalog is a coverage audit. It is not a single skill schema. Each item must be mapped to its authoritative owner, proof method, evidence location, and gate.

## A. Identity
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-001 | **Loop ID** | R0 | Every loop. | STATIC: unique, stable ID appears in descriptor, logs, evidence, and verdicts. |
| LC-002 | **Loop name** | R0 | Every loop. | STATIC: unique human-readable name matches the canonical catalog. |
| LC-003 | **Category** | R0 | Every loop. | STATIC: category is declared and used consistently in portfolio views. |
| LC-004 | **Version** | R1 | The loop is reused, governed, automated, or deployed. | STATIC plus change test: version changes are recorded and referenced by executions. |
| LC-005 | **Lifecycle status** | R1 | The loop can be piloted, restricted, paused, deprecated, or retired. | STATIC plus transition evidence: status changes follow the authoritative lifecycle rule. |
| LC-006 | **Effective date** | R1 | A version or policy change becomes operational. | STATIC: effective date is recorded and prior proof is invalidated when required. |

## B. Purpose and Boundaries
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-007 | **Purpose** | R0 | Every loop. | STATIC: concise statement explains why the loop exists. |
| LC-008 | **Outcome to improve** | R0 | Every loop. | STATIC plus metric link: one primary measurable outcome is named. |
| LC-009 | **Business value** | R0 | The loop consumes material time, cost, or authority. | STATIC: value or avoided loss is stated and reviewable. |
| LC-010 | **Risk reduced** | R1 | The loop is a control or gate. | STATIC: risk statement maps to the risk register or control objective. |
| LC-011 | **Scope** | R0 | Every loop. | STATIC plus qualification probe: included products, systems, environments, users, and actions are identifiable. |
| LC-012 | **Exclusions** | R0 | Adjacent loops or skills exist. | STATIC plus routing probe: out-of-scope cases are rejected or routed correctly. |
| LC-013 | **Stakeholders** | R1 | The loop affects teams, users, customers, or governance authorities. | STATIC: accountable and informed parties are mapped. |
| LC-014 | **Systems and data covered** | R1 | The loop reads, writes, validates, or governs systems or data. | STATIC plus inventory reconciliation: covered assets match authoritative inventories. |

## C. Trigger and Qualification
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-015 | **Event triggers** | R0 | The loop reacts to events or changes. | INTEGRATION_PROBE: each required event starts one qualified execution. |
| LC-016 | **Scheduled cadence** | R0 | The loop has periodic obligations. | SCHEDULE_PROBE: scheduled execution occurs within the permitted window. |
| LC-017 | **Threshold triggers** | R1 | Metrics or risk thresholds start the loop. | BOUNDARY_PROBE: below-threshold events do not start it and above-threshold events do. |
| LC-018 | **Emergency trigger** | R2 | Delay could materially increase loss, outage, or harm. | NEGATIVE_PROBE or drill: emergency conditions bypass normal cadence and invoke the correct authority. |
| LC-019 | **Applicability rules** | R0 | Every loop. | DECISION_PROBE: in-scope and out-of-scope examples are classified correctly. |
| LC-020 | **Deduplication rules** | R1 | The same event can arrive more than once. | REPLAY_PROBE: duplicate triggers create one logical execution or return the prior result. |
| LC-021 | **Entry criteria** | R0 | Every loop. | BOUNDARY_PROBE: the loop starts only when minimum conditions are met. |
| LC-022 | **Preconditions** | R1 | The loop performs state-changing or dependency-sensitive work. | NEGATIVE_PROBE: missing permission, backup, dependency, or environment blocks execution safely. |

## D. Inputs and Dependencies
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-023 | **Required inputs** | R0 | Every loop. | SCHEMA_PROBE: missing or malformed required input is rejected with a named failure. |
| LC-024 | **Optional inputs** | R0 | Optional context can improve the decision. | UNIT_PROBE: absence does not break the loop and presence is handled predictably. |
| LC-025 | **Authoritative sources** | R1 | More than one source or system can supply evidence. | SOURCE-PRIORITY_PROBE: authoritative source wins or material conflict escalates. |
| LC-026 | **Input-quality checks** | R1 | Decisions depend on external, user, model, or operational data. | NEGATIVE_PROBE: incomplete, stale, corrupted, or untrusted input is detected. |
| LC-027 | **Freshness requirements** | R1 | Input can become stale. | TIME-BOUNDARY_PROBE: current input passes and expired input is rejected or escalated. |
| LC-028 | **Data lineage** | R2 | Data influences production, regulated, financial, AI, or audit decisions. | REPRODUCTION_RUN: source, transformations, versions, and consumers can be traced. |
| LC-029 | **Upstream dependencies** | R1 | Other skills, services, approvals, or data feeds are required. | FAULT_INJECTION: unavailable or delayed upstream dependencies trigger the approved fallback or block. |
| LC-030 | **Downstream consumers** | R1 | Other loops or systems consume the output. | CONTRACT_PROBE: downstream receives the expected schema, status, and evidence reference. |
| LC-031 | **Interface contracts** | R1 | The loop exchanges machine-readable data or tool calls. | INTEGRATION_PROBE: valid contracts pass and incompatible versions fail safely. |

## E. Outcome and Measurement
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-032 | **Baseline** | R1 | The loop claims improvement. | STATIC plus reproducibility: the starting metric and source can be recalculated. |
| LC-033 | **Target** | R1 | The loop claims success or readiness. | STATIC: target, time horizon, population, and owner are explicit. |
| LC-034 | **Leading metrics** | R1 | Early process signals are useful. | METRIC_RECALCULATION: formula and source reproduce the reported value. |
| LC-035 | **Lagging metrics** | R1 | The final outcome can be measured. | SUSTAINED_MONITORING: outcome is measured over the required period. |
| LC-036 | **Guardrail metrics** | R2 | Improving one outcome could harm another. | CANARY or regression proof: primary improvement does not breach guardrails. |
| LC-037 | **Metric formulas** | R1 | A metric is used by a gate, target, or report. | RECALCULATION_PROBE: independent calculation matches within tolerance. |
| LC-038 | **Observation window** | R2 | The outcome is not immediately observable. | TIME-WINDOW_PROBE: early closure is blocked and the final review occurs by deadline. |
| LC-039 | **Minimum sample size** | R2 | Statistical or traffic-based evidence is required. | STATISTICAL_OBSERVATION: pass is withheld until the floor is met or an explicit insufficient-evidence state occurs. |
| LC-040 | **Quality thresholds** | R1 | The loop makes pass, block, or remediation decisions. | BOUNDARY_PROBE: values around each threshold produce the expected verdict. |

## F. Decision Design
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-041 | **Assessment rules** | R1 | The loop classifies findings or evidence. | DECISION_TABLE_PROBE: representative cases produce expected classifications. |
| LC-042 | **Risk classification** | R1 | Control depth changes with execution risk. | SCENARIO_PROBE: changes in data, privilege, reversibility, or blast radius raise the tier correctly. |
| LC-043 | **Prioritization method** | R1 | Multiple findings compete for action. | RECALCULATION_PROBE: ranking is reproducible and tie rules are applied. |
| LC-044 | **Confidence threshold** | R2 | Uncertain evidence could cause a consequential decision. | BOUNDARY_PROBE: low confidence defers or escalates and sufficient confidence permits the defined action. |
| LC-045 | **Allowed decisions** | R1 | The loop returns a verdict or action status. | SCHEMA_PROBE: only controlled outcomes are emitted. |
| LC-046 | **Decision authority** | R2 | The loop can approve, block, promote, accept risk, or change production. | AUTHORIZATION_PROBE: unauthorized actors cannot issue the verdict and authorized decisions are attributable. |
| LC-047 | **Exception process** | R2 | A required control can be temporarily unmet. | EXPIRY_PROBE: exception requires authority, compensating controls, and a hard expiry. |
| LC-048 | **Residual-risk acceptance** | R3 | Material risk remains after remediation. | AUTHORIZATION_PROBE: only the named risk owner can accept it and the acceptance expires or is reviewed. |

## G. Execution
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-049 | **Execution plan** | R1 | The loop performs more than one step or changes state. | STATIC plus dry run: sequence, owners, expected states, validation, and recovery are complete. |
| LC-050 | **Actions permitted** | R0 | Every action-capable loop. | ALLOWLIST_PROBE: approved actions succeed within scope. |
| LC-051 | **Actions prohibited** | R0 | Every action-capable loop. | NEGATIVE_PROBE: prohibited actions are blocked and audited. |
| LC-052 | **Required permissions** | R1 | The loop accesses systems, data, models, or tools. | AUTHORIZATION_PROBE: least privilege is sufficient and excess or missing authority is detected. |
| LC-053 | **Durable lifecycle events** | R1 | Execution can pause, resume, fail, or span an observation period. | RECOVERY_PROBE: state can be reconstructed and resumed without false completion. |
| LC-054 | **Checkpoints** | R1 | Execution is long-running, multi-step, or partially reversible. | FAULT_INJECTION: interruption resumes from the correct checkpoint without duplicate effects. |
| LC-055 | **Idempotency** | R1 | Actions can be retried, replayed, or duplicated. | REPLAY_PROBE: repeated operation produces one logical effect. |
| LC-056 | **Concurrency control** | R2 | Parallel executions can touch shared state or conflicting resources. | CONCURRENCY_PROBE: races, deadlocks, and conflicting writes are prevented or resolved. |
| LC-057 | **Resource budget** | R1 | The loop consumes time, money, tokens, compute, calls, records, or human effort. | LIMIT_PROBE: the loop stops or escalates before exceeding each bound. |
| LC-058 | **Timeouts** | R1 | External calls or steps can hang. | FAULT_INJECTION: timeout cancels or isolates the step and preserves known state. |
| LC-059 | **Retry and backoff** | R1 | Transient failures are possible. | FAULT_INJECTION: transient errors retry within policy and deterministic errors do not. |
| LC-060 | **Circuit breaker** | R2 | Repeated failure could amplify harm or load. | FAULT_INJECTION: breaker opens, cools down, and recovers according to the authoritative contract. |

## H. Human Control
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-061 | **Human approval points** | R3 | The action is consequential, privileged, regulated, externally visible, or hard to reverse. | AUTHORIZATION_PROBE: action cannot proceed without current approval. |
| LC-062 | **Separation of duties** | R3 | One actor should not propose, approve, execute, validate, and accept risk. | ROLE-CONFLICT_PROBE: prohibited role combinations are blocked. |
| LC-063 | **Manual override** | R2 | Automation can make a wrong or unsafe decision. | OVERRIDE_DRILL: an authorized operator can pause or redirect the loop and the action is audited. |
| LC-064 | **Kill switch** | R3 | The loop can cause fast, broad, or high-impact effects. | KILL_SWITCH_DRILL: active execution stops, credentials are revoked where required, and restart needs approval. |
| LC-065 | **Escalation path** | R1 | The loop can block, fail, conflict, or exceed limits. | ROUTING_PROBE: each failure class reaches the correct authority within SLA. |
| LC-066 | **Backup approver** | R2 | Approval delay could create operational or safety risk. | AVAILABILITY_DRILL: backup authority can act without violating separation of duties. |

## I. Recovery
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-067 | **Failure taxonomy** | R1 | The loop can fail in more than one way. | CLASSIFICATION_PROBE: representative failures map to named states and responses. |
| LC-068 | **Safe failure state** | R2 | Failure could leave an unsafe, inconsistent, or externally harmful state. | FAULT_INJECTION: the loop reaches the defined safe state. |
| LC-069 | **Rollback** | R2 | The action is reversible and changes persistent or production state. | ROLLBACK_DRILL: exact release or operation returns to an accepted prior state. |
| LC-070 | **Compensation** | R2 | Direct rollback is impossible or incomplete. | COMPENSATION_DRILL: corrective action restores the business invariant and records residual impact. |
| LC-071 | **Fallback mode** | R2 | The preferred provider, model, tool, system, or data source can be unavailable. | FAILOVER_DRILL: alternate or reduced mode works within declared limits. |
| LC-072 | **Recovery validation** | R2 | Rollback, compensation, or failover can itself be incomplete. | INDEPENDENT_PROBE: recovered state, data consistency, and service health meet acceptance criteria. |

## J. Validation and Assurance
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-073 | **Validation method** | R0 | Every loop. | EXECUTED_PROBE: actual result is compared with explicit acceptance criteria. |
| LC-074 | **Independent validator** | R3 | The executor could bias or conceal a consequential result. | INDEPENDENT_REVIEW: validator is separate and evidence is attributable. |
| LC-075 | **Test oracle** | R1 | Correctness is not self-evident. | ORACLE_PROBE: actual output is compared against the approved source of truth. |
| LC-076 | **Evaluation dataset** | R1 | AI, data, security, classification, or quality behavior is evaluated. | DATASET_AUDIT plus execution: version, labels, coverage, and expected results are verified. |
| LC-077 | **False-positive controls** | R2 | The loop can block legitimate work or create alert fatigue. | LABELED-SAMPLE_EVAL: precision or false-positive rate meets threshold. |
| LC-078 | **False-negative controls** | R2 | The loop can miss real failures or threats. | LABELED-SAMPLE_EVAL: recall or miss rate meets threshold. |
| LC-079 | **Non-regression checks** | R1 | A change could break existing behavior. | REGRESSION_PROBE: required existing behavior remains green. |
| LC-080 | **Side-effect checks** | R2 | The action can affect downstream systems, users, cost, security, privacy, or accessibility. | IMPACT_PROBE or canary: unintended effects stay within guardrails. |
| LC-081 | **Security checks** | R1 | The loop handles code, infrastructure, identities, tools, models, external input, or secrets. | STATIC and NEGATIVE_PROBES appropriate to the threat model. |
| LC-082 | **Privacy checks** | R2 | Personal, confidential, or regulated data is processed. | PRIVACY_PROBE: minimization, purpose, access, retention, and deletion controls hold. |
| LC-083 | **Compliance checks** | R2 | Law, policy, contract, standard, or audit control applies. | CONTROL_TEST: applicable obligation maps to current executed evidence. |

## K. Evidence and Communication
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-084 | **Required evidence** | R1 | The result is governed, reusable, or gate-relevant. | EVIDENCE_AUDIT: required artifacts exist, are complete, integrity-protected, and scope-bound. |
| LC-085 | **Traceability** | R1 | The loop makes decisions or changes state. | TRACE_PROBE: trigger, input, finding, decision, action, proof, outcome, and learning can be followed end to end. |
| LC-086 | **Reproducibility** | R2 | The result affects a release, model, regulated outcome, audit, or disputed decision. | REPRODUCTION_RUN: exact versions and inputs reproduce within tolerance. |
| LC-087 | **Audit logs** | R2 | Actions are privileged, consequential, regulated, or security relevant. | FORENSIC_DRILL: an independent reviewer can reconstruct a sampled execution. |
| LC-088 | **Retention period** | R1 | Evidence has legal, operational, security, or learning value. | EXPIRY and retrieval probe: evidence is retained and disposed according to policy. |
| LC-089 | **Evidence access control** | R2 | Evidence contains sensitive data, secrets, privileged decisions, or customer information. | AUTHORIZATION_PROBE: unauthorized access is denied and authorized access is logged. |
| LC-090 | **Notification rules** | R1 | A result requires action, awareness, or escalation. | ROUTING_PROBE: the right recipients receive actionable content and irrelevant parties do not. |
| LC-091 | **Service-level expectations** | R1 | Delay changes impact or risk. | SLA_MONITORING: acknowledgement, decision, remediation, and escalation times are measured. |

## L. Learning and Improvement
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-092 | **Root-cause analysis** | R1 | A failure is material, repeated, or systemic. | REVIEW_PROOF: analysis identifies more than the visible symptom and names failed controls. |
| LC-093 | **Corrective action** | R0 | A current gap or failure exists. | VALIDATION_PROBE: the immediate issue is corrected. |
| LC-094 | **Preventive action** | R1 | Recurrence is plausible or costly. | REGRESSION or control probe: the preventive control blocks the known failure pattern. |
| LC-095 | **Learning destination** | R1 | The loop claims to learn. | ARTIFACT_PROBE: learning updates a test, policy, prompt, runbook, default, standard, or backlog item. |
| LC-096 | **Effectiveness verification** | R2 | The action's intended outcome needs post-change observation. | SUSTAINED_MONITORING: target is met through the required window with guardrails intact. |
| LC-097 | **Causal-confidence method** | R2 | The loop attributes outcome change to its action. | EXPERIMENT or comparison evidence: the selected method supports the stated confidence. |
| LC-098 | **Regression-case creation** | R1 | A reproducible failure or edge case was found. | TEST-SUITE_PROBE: the new case fails before correction and passes after correction. |
| LC-099 | **Standard or policy update** | R1 | The correction should become normal behavior. | BASELINE_AUDIT: authoritative default, standard, policy, or operating baseline is updated. |

## M. Lifecycle and Meta-Governance
| ID | Control | Minimum tier | Applies when | Minimum proof |
|---:|---|:---:|---|---|
| LC-100 | **Drift monitoring** | R2 | Inputs, models, policies, configurations, owners, or evidence can change over time. | MONITORING_PROBE: defined drift produces an alert and the correct response. |
| LC-101 | **Assumption monitoring** | R2 | The loop depends on material environmental or behavioral assumptions. | REVIEW_PROOF: assumptions are tested at cadence and invalid assumptions trigger re-evaluation. |
| LC-102 | **Convergence criteria** | R1 | The loop can run repeatedly. | BOUNDARY_PROBE: the loop stops iterating when improvement or no-value conditions are met. |
| LC-103 | **Stop conditions** | R1 | Continued execution can waste resources or increase risk. | NEGATIVE_PROBE: unsafe, blocked, budget-exceeded, or no-value conditions stop the loop. |
| LC-104 | **Oscillation detection** | R2 | The loop can reverse prior decisions. | OSCILLATION_PROBE: small alternating signals do not cause repeated reversal and genuine overrides still work. |
| LC-105 | **Portability** | R2 | Vendor, model, framework, platform, or tool concentration creates continuity risk. | FAILOVER or migration drill: an alternate implementation works within declared loss. |
| LC-106 | **Owner succession** | R1 | The loop must outlive an individual owner. | SUCCESSION_DRILL or access review: backup ownership and authority transfer are operable. |
| LC-107 | **Deprecation and retirement** | R1 | The loop, product, control, or dependency can become obsolete. | RETIREMENT_DRILL or checklist: triggers, credentials, dependencies, and evidence are handled safely. |
| LC-108 | **Loop-health metrics** | R1 | The loop is active beyond a one-time execution. | METRIC_RECALCULATION: coverage, success, noise, cost, recurrence, and proof freshness are measurable. |
| LC-109 | **Meta-review frequency** | R1 | The loop remains active or governed. | SCHEDULE and review evidence: the loop is assessed for value, noise, gaps, duplication, and retirement at cadence. |


---

## 36. Common Named Failure States

Use stable failure states so gates, dashboards, and downstream loops can respond consistently.

```text
UNMAPPED_AUTHORITY
OWNER_CONFLICT
FORKED_AUTHORITY
NON_AUTHORITATIVE_EVIDENCE
THRESHOLD_CONFLICT
INPUT_INCOMPLETE
INPUT_STALE
INPUT_CONFLICTED
INPUT_UNTRUSTED
SCOPE_MISMATCH
MISSING_PROOF
EXPIRED_PROOF
PROBE_FAILED
ROLLBACK_UNPROVEN
ROLLBACK_FAILED
FAILOVER_FAILED
KILL_SWITCH_FAILED
NON_REGRESSION_FAILED
SIDE_EFFECT_GUARDRAIL_FAILED
INSUFFICIENT_EVIDENCE
INSUFFICIENT_TRAFFIC
CONDITIONAL_EXPIRED
OSCILLATION_DETECTED
OSCILLATION_POLICY_CONFLICT
OSCILLATION_OWNER_CONFLICT
RESOURCE_LIMIT_EXCEEDED
CIRCUIT_OPEN
RECOVERY_FAILED
EFFECTIVENESS_FAILED
EVIDENCE_INCOMPLETE
REPRODUCIBILITY_FAILED
```

Each named state must map to:

- Owning authority
- Required response
- Escalation path
- Evidence location
- Retry eligibility
- Recovery eligibility
- Terminal or non-terminal status

---

## 37. Definition of Done for a Loop Skill

A loop skill is ready for production only when:

1. Its primary outcome is measurable.
2. Its scope and exclusions are explicit.
3. Its effective risk tier can be calculated.
4. Its controls reference the canonical catalog.
5. Every applicable control has one authoritative owner.
6. No forked authority remains.
7. Inputs and outputs have versioned contracts.
8. State-changing operations are idempotent.
9. Timeouts, retries, backoff, and circuit breaking are owned and proven.
10. Safe failure, rollback, compensation, or fallback is defined where applicable.
11. Required probes run green for the intended scope.
12. Proof is current and stored in an authoritative location.
13. Human approvals and separation of duties are enforced where required.
14. Conditional progression is bounded and expires.
15. Action state and outcome effectiveness are recorded separately.
16. Non-regression and side-effect checks pass.
17. Learning updates a durable artifact.
18. Oscillation controls are proven when reversal is possible.
19. Loop-health metrics are observable.
20. Retirement and owner succession are defined.

---

## 38. Minimal Skill Review Questions

Before approving a loop skill, ask:

1. What single outcome does this loop own?
2. Which risk tier applies to this execution?
3. Which controls are applicable?
4. Who is the authoritative owner of each concern?
5. Is any concern owned twice?
6. Which claims are declared only?
7. Which required probes have actually run?
8. Is the proof current and scope-matched?
9. What happens during timeout, replay, partial execution, and dependency failure?
10. What is the safe failure state?
11. Can the action be rolled back or compensated?
12. What makes a conditional verdict close?
13. What happens when its deadline expires?
14. How is sustained effectiveness proven?
15. Where does the learning go?
16. Can the loop reverse the same decision repeatedly?
17. What hysteresis or dwell rule prevents that?
18. What evidence lets an independent reviewer reconstruct the execution?
19. What invalidates earlier proof?
20. When should this loop be paused or retired?

---

## 39. Recommended Implementation Sequence

### Phase 1: Establish authority and traceability

- Create or validate the composition map.
- Assign one owner per control concern.
- Create stable loop and control IDs.
- Establish the canonical control catalog.
- Identify evidence sources and gate consumers.
- Mark unresolved ownership as `UNMAPPED`.

### Phase 2: Establish risk and proof

- Define the risk-tier calculation.
- Tag each control with minimum tier and applicability.
- Classify proof as static, executable, observational, or sustained.
- Build probes for rollback, idempotency, retry, failover, authorization, and recovery.
- Add proof freshness and scope binding.

### Phase 3: Establish execution safety

- Enforce permissions and action allowlists.
- Add checkpoints, idempotency, timeouts, and budgets.
- Implement inline retry, compensation, rollback, and containment.
- Add manual override and kill switch where required.
- Exercise safe-failure behavior.

### Phase 4: Establish outcome assurance

- Separate action completion from outcome proof.
- Define baselines, targets, guardrails, sample floors, and observation windows.
- Add independent validation for high-risk loops.
- Add non-regression and side-effect checks.
- Implement conditional verdict expiry.

### Phase 5: Establish learning and anti-drift

- Convert failures into regression and evaluation cases.
- Update defaults, standards, prompts, policies, and runbooks.
- Monitor assumptions, drift, proof expiry, and owner changes.
- Add oscillation detection and stabilization.
- Measure loop health and run periodic meta-reviews.

---

## 40. Final Operating Standard

> A production-grade continuous improvement loop is complete for its declared scope and risk tier only when every applicable concern is mapped to one authoritative owner, every executable claim is supported by current scope-bound proof, and the authoritative gate consumes that proof directly. The loop must execute within bounded authority, recover during execution, fail safely, preserve traceable evidence, and keep action completion separate from outcome effectiveness. Conditional progression must be evidence-bounded and time-bounded. Repeated decision reversals must be controlled through hysteresis, materiality thresholds, minimum dwell periods, and escalation. The loop may close only after required probes are green, guardrails remain intact, the intended outcome is sustained, learning has changed the operating baseline, and no unmapped authority, expired proof, unresolved condition, or unowned action remains.
