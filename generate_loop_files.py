import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md"
OUT_DIR = ROOT / "loops"
TEMPLATE_SOURCE = ROOT / "standards" / "production-grade-continuous-improvement-loop.md"


CATEGORY_RE = re.compile(r"^# (\d+)\. (.+)$")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
FIELD_RE = re.compile(
    r"\*\*Trigger:\*\*\s*(.*?)\s*\*\*Run:\*\*\s*(.*?)\s*\*\*Output:\*\*\s*(.*)",
    re.DOTALL,
)
_TEMPLATE_APPENDIX: str | None = None


def slugify(value: str) -> str:
    value = value.lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def clean_cell(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_definition(value: str) -> dict[str, str]:
    match = FIELD_RE.search(value)
    if not match:
        return {
            "trigger": "",
            "run": value,
            "output": "",
        }
    return {
        "trigger": clean_cell(match.group(1)),
        "run": clean_cell(match.group(2)),
        "output": clean_cell(match.group(3)),
    }


def parse_loops() -> list[dict[str, str | int]]:
    loops: list[dict[str, str | int]] = []
    category_number = None
    category_name = None

    for raw_line in SOURCE.read_text(encoding="utf-8").splitlines():
        category_match = CATEGORY_RE.match(raw_line.strip())
        if category_match:
            category_number = int(category_match.group(1))
            category_name = clean_cell(category_match.group(2))
            continue

        row_match = ROW_RE.match(raw_line.strip())
        if not row_match or category_number is None or category_name is None:
            continue

        loop_number = int(row_match.group(1))
        loop_name = clean_cell(row_match.group(2))
        definition = clean_cell(row_match.group(3))
        cadence = clean_cell(row_match.group(4))
        parts = split_definition(definition)

        loops.append(
            {
                "number": loop_number,
                "name": loop_name,
                "category_number": category_number,
                "category_name": category_name,
                "trigger": parts["trigger"],
                "run": parts["run"],
                "output": parts["output"],
                "cadence": cadence,
            }
        )

    return loops


def infer_skill_id(loop: dict[str, str | int]) -> str:
    return f"loop-{int(loop['number']):03d}-{slugify(str(loop['name']))}"


def infer_scope(loop: dict[str, str | int]) -> str:
    return f"{loop['category_name']} control point for {loop['name']}."


def infer_default_risk_tier(loop: dict[str, str | int]) -> str:
    category = str(loop["category_name"]).lower()
    name = str(loop["name"]).lower()
    high_terms = [
        "security",
        "privacy",
        "compliance",
        "agent",
        "autonomy",
        "credential",
        "access",
        "forensic",
        "catastrophic",
        "cryptography",
        "quantum",
        "supply-chain",
        "supply chain",
    ]
    if "catastrophic" in name or "critical" in name:
        return "R4"
    if any(term in category or term in name for term in high_terms):
        return "R3"
    if any(term in category or term in name for term in ["release", "deployment", "operations", "reliability", "data", "database", "ai"]):
        return "R2"
    return "R1"


def infer_business_value(loop: dict[str, str | int]) -> str:
    return f"Improves confidence, speed, safety, and accountability for {loop['name']} decisions by tying every action to evidence and proof."


def infer_risk_reduced(loop: dict[str, str | int]) -> str:
    return f"Reduces the risk that {loop['name']} produces unowned gaps, stale evidence, unproven claims, unsafe actions, repeated failures, or ineffective improvements."


def infer_permitted_actions(loop: dict[str, str | int]) -> list[str]:
    return [
        "Qualify or reject the trigger for this loop",
        "Collect and reconcile authoritative evidence",
        "Classify findings, risk tier, proof state, and owner status",
        "Recommend, execute, or request authorized remediation",
        "Validate immediate correctness and required proof",
        "Record evidence, learning, standards updates, and next monitoring action",
    ]


def infer_inputs(loop: dict[str, str | int]) -> list[str]:
    base = [
        "Trigger evidence",
        "Current state observations",
        "Relevant standards, policies, thresholds, and acceptance criteria",
        "Owner and system context",
    ]
    category = str(loop["category_name"]).lower()
    if "security" in category or "privacy" in category:
        base.append("Security, privacy, access, vulnerability, or audit evidence")
    if "testing" in category:
        base.append("Test cases, test data, execution results, and defect records")
    if "operations" in category or "devops" in category:
        base.append("Deployment, environment, runtime, observability, and recovery records")
    if "ai" in category or "agent" in category or "frontier" in category:
        base.append("Model, prompt, tool, retrieval, memory, evaluation, and autonomy evidence")
    return base


def infer_downstream(loop: dict[str, str | int]) -> list[str]:
    name = str(loop["name"]).lower()
    category = str(loop["category_name"]).lower()
    downstream = ["Backlog Refinement Loop", "Risk Management Loop"]
    if "release" in name or "deployment" in name or "devops" in category:
        downstream.extend(["Deployment Validation Loop", "Production Health Loop"])
    if "incident" in name or "recovery" in name or "operations" in category:
        downstream.extend(["Incident Management Loop", "Problem Management Loop"])
    if "security" in category or "privacy" in category or "compliance" in name:
        downstream.extend(["Secure SDLC Loop", "Compliance Evidence Loop"])
    if "ai" in category or "agent" in category:
        downstream.extend(["Model Evaluation and Benchmarking Loop", "Agent Guardrail Loop"])

    seen = set()
    unique = []
    for item in downstream:
        if item not in seen and item != loop["name"]:
            unique.append(item)
            seen.add(item)
    return unique


def bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def production_grade_appendix() -> str:
    global _TEMPLATE_APPENDIX
    if _TEMPLATE_APPENDIX is not None:
        return _TEMPLATE_APPENDIX

    if not TEMPLATE_SOURCE.exists():
        _TEMPLATE_APPENDIX = (
            "Production-grade checklist source not found at "
            f"`{TEMPLATE_SOURCE}`. Re-run the generator after restoring the template."
        )
        return _TEMPLATE_APPENDIX

    text = TEMPLATE_SOURCE.read_text(encoding="utf-8")
    start = text.find("# Complete Risk-Tiered Control Checklist")
    end = text.find("## 40. Final Operating Standard")
    if start == -1 or end == -1:
        _TEMPLATE_APPENDIX = (
            "Production-grade checklist could not be extracted from "
            f"`{TEMPLATE_SOURCE}` because the expected headings were not found."
        )
        return _TEMPLATE_APPENDIX

    final_standard = text[end:].strip()
    checklist = text[start:end].strip()
    _TEMPLATE_APPENDIX = (
        "The following appendix is copied from the production-grade template so this loop file "
        "retains the complete checklist, named failure states, definition of done, review questions, "
        "implementation sequence, and final operating standard.\n\n"
        f"{checklist}\n\n{final_standard}"
    )
    return _TEMPLATE_APPENDIX


def render_loop(loop: dict[str, str | int]) -> str:
    skill_id = infer_skill_id(loop)
    downstream = infer_downstream(loop)
    inputs = infer_inputs(loop)
    default_risk_tier = infer_default_risk_tier(loop)

    return f"""# {loop['name']}

## Loop Identity

- Loop number: {loop['number']}
- Loop name: {loop['name']}
- Category: {loop['category_number']}. {loop['category_name']}
- Skill ID: `{skill_id}`
- Version: `1.0`
- Lifecycle status: `DRAFT`
- Effective date: To be assigned by the loop owner
- Change history reference: `LOOP_LOG.md` or the authoritative change record
- Minimum cadence: {loop['cadence']}
- Source: `SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md`
- Production-grade standard: `standards/production-grade-continuous-improvement-loop.md`

## Purpose

Outcome to improve: {loop['output']}

Primary measurable outcome: {loop['output']}

Business value: {infer_business_value(loop)}

Risk reduced: {infer_risk_reduced(loop)}

Scope: {infer_scope(loop)}

Exclusions: Responsibilities owned by adjacent loops remain outside this loop unless the trigger, evidence, and authority clearly route them here.

Systems and data covered: Systems, workflows, data, models, agents, controls, evidence, and decisions directly involved in `{loop['name']}`.

Permitted actions:

{bullet(infer_permitted_actions(loop))}

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

Default risk tier for this loop: `{default_risk_tier}`.

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

{loop['trigger']}

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
- Trigger condition: {loop['trigger']}
- Priority: To be calculated from impact, urgency, risk, and confidence
- Deduplication key: `{skill_id}:<asset-or-scope>:<trigger-signature>`
- Suppression rules: Suppress duplicates only when an active authoritative owner is already handling the same concern
- Minimum cadence: {loop['cadence']}
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

{loop['run']}

## Output

{loop['output']}

## Inputs

Required:

{bullet(inputs)}

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

- Loop record for `{skill_id}`

Machine-readable result:

- Common result envelope using the JSON structure below

Human-readable summary:

- What triggered the loop, what evidence was observed, what decision was made, what changed, and what remains

Downstream events:

{bullet(downstream)}

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

- Current state metric: To be measured for `{loop['name']}`
- Baseline source: Authoritative metrics, logs, records, evaluations, or audit evidence
- Baseline date: To be recorded
- Baseline confidence: To be recorded

Target:

- Metric: Primary measurable outcome for `{loop['name']}`
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

Minimum frequency: {loop['cadence']}

Review frequency: Review loop health at least monthly unless the category requires a stricter cadence.

## Reference-Only Loop Descriptor

```yaml
loop_id: "{skill_id}"
name: "{loop['name']}"
version: "1.0"
status: "DRAFT | PILOT | ACTIVE | RESTRICTED | PAUSED | DEPRECATED | RETIRED"

purpose_ref: "Purpose section in this file"
scope_ref: "Purpose and boundaries section in this file"
composition_map_ref: ""
state_register_ref: ""
gate_rules_ref: ""

risk:
  default_tier: "{default_risk_tier}"
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

- Loop: {loop['name']}
- Outcome: {loop['output']}
- Trigger: {loop['trigger']}
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
{{
  "loop_id": "{skill_id}",
  "loop_version": "1.0",
  "execution_id": "unique-execution-id",
  "correlation_id": "cross-loop-correlation-id",
  "risk_tier": "R0 | R1 | R2 | R3 | R4",
  "authority": {{
    "composition_map_ref": "",
    "policy_owner_ref": "",
    "gate_owner_ref": "",
    "executor_ref": "",
    "validator_ref": ""
  }},
  "trigger": {{
    "type": "event | schedule | threshold | request | incident | change | expiry",
    "source": "",
    "deduplication_key": "",
    "evidence_ref": ""
  }},
  "scope": {{
    "product": "",
    "component": "",
    "environment": "",
    "release": "",
    "data_class": "",
    "model_or_agent": "",
    "configuration": ""
  }},
  "input_quality": {{
    "state": "INPUT_VALID | INPUT_INCOMPLETE | INPUT_STALE | INPUT_CONFLICTED | INPUT_UNTRUSTED | INPUT_OUT_OF_SCOPE",
    "freshness": "",
    "lineage_ref": "",
    "conflicts": []
  }},
  "state": {{
    "lifecycle": "TRIGGERED | QUALIFIED | OBSERVED | DIAGNOSED | PRIORITIZED | PLANNED | AUTHORIZED | ACTION_IN_PROGRESS | ACTION_APPLIED | VALIDATION_PASSED | VALIDATION_FAILED | PROOF_GREEN | PROOF_FAILED | EFFECTIVENESS_PENDING | EFFECTIVENESS_PROVEN | EFFECTIVENESS_FAILED | INSUFFICIENT_EVIDENCE | CONDITIONAL_ACTIVE | CONDITIONAL_EXPIRED | BLOCKED | ROLLED_BACK | PAUSED | RETIRED",
    "proof_state": "UNMAPPED | DECLARED | IMPLEMENTED | EXERCISED | PROVEN | SUSTAINED | FAILED | EXPIRED",
    "status": "pass | conditional | remediate | escalate | block | failed"
  }},
  "findings": [],
  "actions_taken": [],
  "actions_required": [],
  "validation": {{
    "method": "",
    "oracle_ref": "",
    "non_regression": "",
    "side_effects": "",
    "result": ""
  }},
  "proof": {{
    "probe_ref": "",
    "acceptance_ref": "",
    "scope_binding": "",
    "executed_at": "",
    "expires_at": "",
    "result": ""
  }},
  "effectiveness": {{
    "baseline_ref": "",
    "target_ref": "",
    "observation_window": "",
    "guardrails": [],
    "causal_confidence": "",
    "result": ""
  }},
  "recovery": {{
    "safe_failure_state": "",
    "rollback_ref": "",
    "compensation_ref": "",
    "fallback_ref": ""
  }},
  "conditional": {{
    "condition_id": "",
    "owner": "",
    "expires_at": "",
    "terminal_outcomes": []
  }},
  "oscillation": {{
    "decision_key": "",
    "reversal_count": 0,
    "verdict": "STABLE | OSCILLATION_DETECTED | OSCILLATION_POLICY_CONFLICT | OSCILLATION_OWNER_CONFLICT"
  }},
  "evidence": [],
  "metrics": {{}},
  "owner": "",
  "next_execution": "",
  "timestamp": ""
}}
```

---

# Production-Grade Template Appendix

{production_grade_appendix()}
"""


def render_category_index(category: dict[str, str | int], loops: list[dict[str, str | int]]) -> str:
    rows = []
    for loop in loops:
        file_name = f"{int(loop['number']):03d}-{slugify(str(loop['name']))}.md"
        rows.append(f"- [{loop['number']}. {loop['name']}]({file_name})")
    return f"""# {category['number']}. {category['name']}

This folder contains one loop file for each loop in this category.

## Loops

{chr(10).join(rows)}
"""


def render_root_index(loops: list[dict[str, str | int]]) -> str:
    by_category: dict[int, dict[str, object]] = {}
    for loop in loops:
        key = int(loop["category_number"])
        by_category.setdefault(
            key,
            {
                "name": loop["category_name"],
                "loops": [],
            },
        )
        by_category[key]["loops"].append(loop)

    lines = [
        "# SDLC Loop Files Index",
        "",
        "This directory contains 108 loop Markdown files generated from `SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md`.",
        "",
        "Each file follows the standard loop contract: trigger, qualification, observation, diagnosis, prioritization, planning, authorization, execution, validation, recovery, record, learning, standardization, effectiveness monitoring, and repeat, pause, or retire decision.",
        "",
        "## Categories",
        "",
    ]

    for number in sorted(by_category):
        category = by_category[number]
        folder = f"{number:02d}-{slugify(str(category['name']))}"
        count = len(category["loops"])
        lines.append(f"- [{number}. {category['name']}]({folder}/README.md): {count} loops")

    lines.extend(["", "## Verification", "", f"- Total loop files expected: {len(loops)}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    loops = parse_loops()
    if len(loops) != 108:
        raise SystemExit(f"Expected 108 loops, parsed {len(loops)}")

    OUT_DIR.mkdir(exist_ok=True)

    by_category: dict[int, dict[str, object]] = {}
    for loop in loops:
        category_number = int(loop["category_number"])
        category_name = str(loop["category_name"])
        by_category.setdefault(
            category_number,
            {
                "number": category_number,
                "name": category_name,
                "loops": [],
            },
        )
        by_category[category_number]["loops"].append(loop)

    for category_number, category in sorted(by_category.items()):
        category_dir = OUT_DIR / f"{category_number:02d}-{slugify(str(category['name']))}"
        category_dir.mkdir(parents=True, exist_ok=True)
        category_loops = category["loops"]
        for loop in category_loops:
            file_name = f"{int(loop['number']):03d}-{slugify(str(loop['name']))}.md"
            (category_dir / file_name).write_text(render_loop(loop), encoding="utf-8", newline="\n")
        (category_dir / "README.md").write_text(
            render_category_index(category, category_loops),
            encoding="utf-8",
            newline="\n",
        )

    (OUT_DIR / "README.md").write_text(render_root_index(loops), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
