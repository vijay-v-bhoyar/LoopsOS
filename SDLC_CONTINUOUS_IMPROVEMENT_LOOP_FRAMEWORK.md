# SDLC Continuous Improvement Loop Framework

## Purpose

This framework defines a connected system of small SDLC improvement loops. It does not treat the software lifecycle as one large loop. Instead, each loop owns one outcome, produces evidence, identifies gaps, applies fixes, and retests the result.

The goal is to make improvement observable, repeatable, and safe. Every loop should leave behind proof of what changed, why it changed, and whether the change worked.

## Core Principle

Each loop must own a specific outcome.

Good loop outcomes are narrow enough to validate directly:

- Requirements are clear enough for engineering to implement.
- Designs are usable before development starts.
- Code changes meet maintainability and security expectations.
- Automated tests detect the intended risks.
- Releases are deployable with rollback confidence.
- Production behavior matches the expected service level.
- Incidents produce durable prevention work.

Avoid broad loop outcomes such as "improve the SDLC" or "make delivery better." Those are portfolios, not loops.

## Standard Loop Pattern

Every loop follows the same production-grade sequence:

```text
Trigger -> Qualify -> Observe -> Diagnose -> Prioritize -> Plan -> Authorize -> Execute -> Validate -> Recover if needed -> Record -> Learn -> Standardize -> Monitor effectiveness -> Repeat, pause, or retire
```

## Loop Stage Definitions

### 1. Trigger

Define what starts the loop.

Examples:

- A failed build.
- A production incident.
- A support escalation.
- A security finding.
- A missed sprint commitment.
- A defect escaping to production.
- A deployment taking longer than the target threshold.

The trigger should be specific enough that the team knows when the loop must run.

### 2. Qualify

Decide whether the trigger belongs in this loop.

Qualification should answer:

- Is this the right loop owner?
- Is the issue real and current?
- Is there enough evidence to continue?
- Is this urgent, routine, or noise?
- Should another loop handle it instead?

If the trigger does not qualify, record the reason and route it appropriately.

### 3. Observe

Collect evidence before forming conclusions.

Evidence may include:

- Logs.
- Metrics.
- Traces.
- Test output.
- Pull request history.
- User reports.
- Incident timelines.
- Build and deployment records.
- Screenshots or session recordings.

Observation must separate facts from interpretation.

### 4. Diagnose

Identify the gap between expected and actual behavior.

Diagnosis should produce:

- A clear problem statement.
- Suspected contributing factors.
- Known unknowns.
- Impacted users, systems, or workflows.
- The evidence supporting the diagnosis.

Avoid jumping directly from symptom to fix.

### 5. Prioritize

Rank the gap against other work.

Prioritization inputs:

- User impact.
- Business impact.
- Security or compliance risk.
- Frequency.
- Severity.
- Cost of delay.
- Effort and reversibility.
- Whether the issue blocks another loop.

The output should be a decision: act now, schedule, monitor, delegate, or close.

### 6. Plan

Define the smallest credible fix and how it will be tested.

The plan should include:

- Target outcome.
- Change scope.
- Owner.
- Validation method.
- Rollback or recovery path.
- Dependencies.
- Expected evidence.

Plans should prefer small, reversible changes.

### 7. Authorize

Confirm that the planned action is allowed to proceed.

Authorization may come from:

- Code review approval.
- Release manager approval.
- Security approval.
- Product owner approval.
- Automated policy gates.
- Predefined operational runbooks.

The higher the risk, the more explicit authorization should be.

### 8. Execute

Apply the planned fix.

Execution should be traceable:

- Link commits, tickets, pull requests, deployments, or runbook actions.
- Keep scope aligned with the authorized plan.
- Avoid unrelated cleanup unless it is required for the fix.

### 9. Validate

Retest the outcome using the planned validation method.

Validation should answer:

- Did the fix resolve the gap?
- Did it introduce regressions?
- Did the expected evidence appear?
- Is the result observable in the target environment?

Validation is not complete until there is evidence.

### 10. Recover If Needed

If validation fails or the fix causes harm, recover quickly.

Recovery options:

- Roll back.
- Disable a feature flag.
- Revert a configuration change.
- Restore a known-good artifact.
- Apply a controlled hotfix.
- Escalate to an incident loop.

Recovery actions should also be recorded as evidence.

### 11. Record

Capture what happened in a durable location.

Record:

- Trigger.
- Qualification decision.
- Evidence observed.
- Diagnosis.
- Priority decision.
- Plan.
- Authorization.
- Execution links.
- Validation results.
- Recovery actions, if any.
- Final status.

Records make the loop auditable and reusable.

### 12. Learn

Extract the lesson from the loop.

Learning should identify:

- What was misunderstood.
- What signal was missing.
- What control failed.
- What worked well.
- What should change in standards, tests, runbooks, or tooling.

Learning is only useful when it changes future behavior.

### 13. Standardize

Turn the lesson into a reusable standard.

Standardization may update:

- Checklists.
- Templates.
- Coding standards.
- Test suites.
- CI/CD gates.
- Runbooks.
- Architecture decision records.
- Observability dashboards.
- Definition of ready or definition of done.

The standard should reduce the chance of repeating the same gap.

### 14. Monitor Effectiveness

Watch whether the standard actually works over time.

Effectiveness signals:

- Fewer repeat incidents.
- Lower defect escape rate.
- Faster recovery time.
- Higher test reliability.
- Shorter review cycles.
- Better deployment success rate.
- Improved user experience metrics.

Monitoring should have a defined window and owner.

### 15. Repeat, Pause, or Retire

Decide the loop's next state.

- Repeat when the outcome is still below target.
- Pause when there is no current signal but future monitoring is needed.
- Retire when the outcome is stable, ownership is absorbed elsewhere, or the loop no longer creates value.

Retired loops should leave behind their standards and records.

## Connected SDLC Loop System

The SDLC should be managed as a network of connected loops. Each loop owns one outcome and passes evidence to adjacent loops.

```text
Strategy Loop
  -> Discovery Loop
  -> Requirements Loop
  -> Design Loop
  -> Architecture Loop
  -> Implementation Loop
  -> Code Review Loop
  -> Test Quality Loop
  -> Security Loop
  -> Release Readiness Loop
  -> Deployment Loop
  -> Production Health Loop
  -> Incident Learning Loop
  -> Backlog Refinement Loop
```

The flow is not strictly linear. A finding in any loop can trigger another loop.

Examples:

- A production incident can trigger the Incident Learning Loop, Test Quality Loop, Observability Loop, and Backlog Refinement Loop.
- A security review can trigger the Architecture Loop, Implementation Loop, and Release Readiness Loop.
- A failed deployment can trigger the Deployment Loop, Release Readiness Loop, and Test Quality Loop.

## Recommended Loop Catalog

### Strategy Loop

Outcome: Product and engineering work maps to current business priorities.

Primary evidence:

- Strategy documents.
- Roadmap decisions.
- Business metrics.
- Customer commitments.
- Investment tradeoff records.

Common gaps:

- Work is not tied to a measurable business outcome.
- Priorities conflict across stakeholders.
- Teams are building against stale assumptions.

### Discovery Loop

Outcome: Problems are understood before solutions are selected.

Primary evidence:

- User interviews.
- Support themes.
- Market research.
- Usage analytics.
- Opportunity assessments.

Common gaps:

- Solution chosen before problem validation.
- Weak evidence of user need.
- Missing constraints or edge cases.

### Requirements Loop

Outcome: Requirements are clear, testable, and implementation-ready.

Primary evidence:

- User stories.
- Acceptance criteria.
- Nonfunctional requirements.
- Dependency notes.
- Open question logs.

Common gaps:

- Ambiguous acceptance criteria.
- Missing error states.
- Missing compliance or security requirements.
- Requirements conflict with technical constraints.

### Design Loop

Outcome: UX and interaction decisions are usable before build starts.

Primary evidence:

- Wireframes.
- Prototypes.
- Design reviews.
- Accessibility checks.
- User validation notes.

Common gaps:

- Missing empty, loading, or error states.
- Inaccessible interactions.
- Workflow does not match user intent.
- Design system drift.

### Architecture Loop

Outcome: Technical direction supports reliability, maintainability, scale, and security.

Primary evidence:

- Architecture decision records.
- System diagrams.
- Threat models.
- Data flow diagrams.
- Dependency reviews.

Common gaps:

- Hidden coupling.
- Unclear ownership boundaries.
- Fragile integration points.
- Missing migration or rollback strategy.

### Implementation Loop

Outcome: Code changes are correct, maintainable, and aligned with project standards.

Primary evidence:

- Commits.
- Static analysis.
- Local test results.
- Implementation notes.
- Code ownership records.

Common gaps:

- Logic does not match requirements.
- Change scope is too broad.
- Error handling is incomplete.
- Performance risks are not considered.

### Code Review Loop

Outcome: Review catches meaningful risks before merge.

Primary evidence:

- Pull request comments.
- Approval records.
- Review checklists.
- Diff risk notes.
- Required status checks.

Common gaps:

- Review focuses on style instead of behavior.
- Missing tests are not challenged.
- Security or data risks are overlooked.
- Review latency blocks delivery.

### Test Quality Loop

Outcome: Tests detect the risks that matter.

Primary evidence:

- Unit test results.
- Integration test results.
- End-to-end test results.
- Coverage reports.
- Flake history.
- Mutation or fault-injection results where available.

Common gaps:

- Tests pass without validating real behavior.
- Critical paths lack coverage.
- Tests are flaky or environment-dependent.
- Regression tests are missing for known failures.

### Security Loop

Outcome: Security risks are identified, fixed, and prevented from recurring.

Primary evidence:

- Threat models.
- Dependency scans.
- Secret scans.
- SAST and DAST results.
- Pen test findings.
- Security review notes.

Common gaps:

- Secrets are exposed.
- Authorization is incomplete.
- Input validation is weak.
- Dependencies are vulnerable.
- Logging leaks sensitive data.

### Release Readiness Loop

Outcome: A release is safe to ship.

Primary evidence:

- Release checklist.
- Version notes.
- Test summaries.
- Risk assessment.
- Rollback plan.
- Stakeholder signoff.

Common gaps:

- No rollback path.
- Unresolved blocker defects.
- Missing migration validation.
- Release notes do not match shipped behavior.

### Deployment Loop

Outcome: Changes deploy reliably to the intended environment.

Primary evidence:

- Deployment logs.
- Environment configuration.
- Smoke test results.
- Feature flag state.
- Rollback records.

Common gaps:

- Environment drift.
- Missing secrets or configuration.
- Build artifact mismatch.
- Smoke tests are too shallow.

### Production Health Loop

Outcome: Production behavior remains within expected service levels.

Primary evidence:

- Metrics.
- Logs.
- Traces.
- Alerts.
- SLO reports.
- User experience telemetry.

Common gaps:

- Alerts are noisy or missing.
- Dashboards do not answer operational questions.
- Service levels are undefined.
- User impact is hard to detect.

### Incident Learning Loop

Outcome: Incidents create durable prevention and faster recovery.

Primary evidence:

- Incident timeline.
- Root cause analysis.
- Customer impact summary.
- Action items.
- Follow-up validation.

Common gaps:

- Action items are vague.
- Root cause stops at human error.
- Preventive controls are not implemented.
- Repeat incidents are not detected.

### Backlog Refinement Loop

Outcome: Improvement work becomes visible, prioritized, and executable.

Primary evidence:

- Backlog items.
- Priority decisions.
- Dependency notes.
- Capacity allocation.
- Closed-loop follow-up records.

Common gaps:

- Lessons do not become work.
- Technical debt has no owner.
- Improvement items are too large.
- Priority is not connected to evidence.

## Loop Evidence Contract

Each loop should maintain an evidence record with this minimum structure:

```markdown
## Loop Record

- Loop:
- Outcome:
- Trigger:
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

## Loop Health Metrics

Use a small set of metrics per loop. Avoid measuring everything.

Recommended metric types:

- Trigger volume: How often the loop starts.
- Qualification rate: How many triggers are real and actionable.
- Time to diagnosis: How long it takes to understand the gap.
- Time to validation: How long it takes to prove the fix.
- Repeat rate: How often the same gap returns.
- Standard adoption: Whether the lesson became normal practice.
- Effectiveness trend: Whether the target outcome improved.

## Operating Rules

- One loop owns one outcome.
- Every loop must produce evidence.
- Every diagnosis must name the gap.
- Every fix must have a validation method.
- Every failed validation must trigger recovery or replanning.
- Every lesson must be recorded.
- Every repeated gap must update a standard or monitor.
- Every loop must eventually repeat, pause, or retire.

## Example: Escaped Defect Loop

Outcome: Reduce defects that escape to production.

```text
Trigger: A customer reports a production defect.
Qualify: Confirm it is a real product defect, not expected behavior or user configuration.
Observe: Collect customer report, logs, reproduction steps, affected versions, and support impact.
Diagnose: Identify the missed requirement, code path, test gap, or deployment issue.
Prioritize: Rank by customer impact, severity, frequency, and risk.
Plan: Define the fix, regression test, release path, and rollback option.
Authorize: Obtain product, engineering, or release approval based on risk.
Execute: Implement the fix and add the missing test.
Validate: Reproduce the original defect, prove it is fixed, and run regression checks.
Recover if needed: Roll back or disable the change if validation fails or harm appears.
Record: Capture evidence, links, decisions, and final status.
Learn: Identify why the defect escaped.
Standardize: Update acceptance criteria, review checklist, or test strategy.
Monitor effectiveness: Track repeat defects in the same area for the next release window.
Repeat, pause, or retire: Repeat if related escapes continue, pause if stable, retire if absorbed into standards.
```

## Implementation Checklist

- Define the initial loop catalog.
- Assign one owner per loop.
- Define each loop outcome.
- Define trigger conditions.
- Create the evidence record template.
- Choose one to three health metrics per loop.
- Connect loops through evidence handoffs.
- Run the first loop manually before automating.
- Review loop health on a recurring cadence.
- Retire loops that no longer create useful signal.



---

# Source Taxonomy Appendix

The initial framework above intentionally defines the operating model for small, connected improvement loops. The following appendix preserves the attached 108-loop taxonomy, consolidation logic, category distribution, boundary rules, standard skill contract, and common result envelope so important source details are not lost.

# Consolidated 108-Loop Taxonomy

The complete framework contains **108 distinct loops across 13 categories**.

The consolidation follows three rules:

1. Two loops are combined when they have substantially the same trigger, processing steps, decision point, and output.
2. Related loops remain separate when they operate at different control points, such as runtime enforcement versus periodic governance.
3. Each loop has a clear boundary so it can be implemented as an independent skill, automation, pipeline control, agent, or operating procedure.

These should not become 108 meetings. Most loops should run as automated skills, workflow steps, scheduled evaluations, pipeline gates, monitoring controls, or event-driven agents.

---

## Duplicate Consolidation

The earlier framework contained 118 labels. The following consolidation removes 10 overlaps and results in exactly 108 loops.

| Combined loop                                                                | Earlier loops combined                                                            |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **Model and Agent Interaction Security**                                     | Model-Level Security + Agent Hijacking Resistance                                 |
| **Performance, Capacity, Cost and AI Economics**                             | AI Cost and Latency + Capacity and Cost Optimization                              |
| **Reliability, SLO and Error-Budget Management**                             | SLO and Error Budget + Reliability Engineering                                    |
| **Rollback, Backup and Recovery**                                            | Rollback and Recovery + Backup, Restore and Disaster Recovery                     |
| **Model Evaluation and Benchmarking**                                        | Model Evaluation + AI Benchmark Drift                                             |
| **Model Lifecycle and Upgrade Safety**                                       | Model Upgrade Safety + Model Lifecycle, Deprecation and Rollback                  |
| **Human Oversight, Approval and Calibration**                                | Human-in-the-Loop Approval + Human Oversight Calibration and Reviewer Quality     |
| **Architecture Fitness and Future Compatibility**                            | Architecture Fitness + Future Architecture Compatibility                          |
| **Post-Quantum Cryptography, Crypto-Agility and Long-Lived Data Protection** | Quantum Cryptography Readiness + Cryptographic Agility + Long-Lived Data Exposure |

The first eight combinations reduce the count by eight. The final three-to-one combination reduces it by another two.

**118 − 8 − 2 = 108**

---

## Category Distribution

| Category                                          | Number of loops |
| ------------------------------------------------- | --------------: |
| 1. Product Strategy, Discovery and Lifecycle      |               5 |
| 2. Requirements, Backlog and Delivery Management  |               9 |
| 3. Architecture, Design and Modernization         |               6 |
| 4. Software Engineering and Build                 |               5 |
| 5. Testing, Validation and Experience Quality     |              10 |
| 6. DevOps, Release and Environment Management     |               5 |
| 7. Operations, Reliability and Service Management |               8 |
| 8. Data, Database and Knowledge Management        |               8 |
| 9. AI and Generative AI Lifecycle and Quality     |               9 |
| 10. Agentic AI Execution and Orchestration        |              11 |
| 11. Security, Privacy and Supply-Chain Assurance  |              14 |
| 12. Frontier, Quantum and Strategic Resilience    |               8 |
| 13. Enterprise Governance, Adoption and Workforce |              10 |
| **Total**                                         |         **108** |

The frequency shown below is a recommended minimum. A high-risk or highly regulated product may need more frequent execution.

---

# 1. Product Strategy, Discovery and Lifecycle

|  # | Loop name                                                   | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                                     | Trigger or minimum cadence            |
| -: | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
|  1 | **Product Discovery Loop**                                  | **Trigger:** New customer evidence, support patterns, market changes, or proposed opportunities. **Run:** Collect evidence, define the user problem, identify expected outcomes, test assumptions through research or prototypes, and rank opportunities. **Output:** Validated problem statement, supporting evidence, rejected assumptions, and candidate backlog items.                                 | Continuous, with weekly review        |
|  2 | **AI Use-Case Validation Loop**                             | **Trigger:** A proposal to use AI, GenAI, or agents. **Run:** Compare AI with deterministic alternatives, assess data availability, evaluation feasibility, cost, risk, explainability, human oversight, and operational support. Prototype where necessary. **Output:** Go, revise, or no-go decision with an AI use-case contract and success measures.                                                  | At use-case intake and before funding |
|  3 | **Business Value Validation Loop**                          | **Trigger:** A scheduled value review or material variance in product performance. **Run:** Compare expected benefits with actual revenue, savings, quality, adoption, risk reduction, and operating cost. Check whether results are attributable to the product. **Output:** Value scorecard and a scale, continue, change, pause, or stop recommendation.                                                | Monthly or quarterly                  |
|  4 | **Roadmap Alignment Loop**                                  | **Trigger:** Strategy, customer priority, capacity, dependency, regulation, or technology changes. **Run:** Rebalance initiatives based on value, risk, capacity, dependencies, architectural constraints, and sequencing. **Output:** Prioritized roadmap, updated assumptions, dependency decisions, and release direction.                                                                              | Monthly or after major change         |
|  5 | **Product and Service Retirement and Decommissioning Loop** | **Trigger:** End of support, low value, replacement, obsolescence, excessive risk, or strategic exit. **Run:** Inventory users, data, integrations, infrastructure, contracts, and obligations; migrate consumers; archive or dispose of data; communicate changes; and verify shutdown. **Output:** Approved retirement plan, migration evidence, residual-risk record, and decommissioning confirmation. | Annual review and lifecycle event     |

---

# 2. Requirements, Backlog and Delivery Management

|  # | Loop name                                                    | Skill-ready definition                                                                                                                                                                                                                                                                                                                                       | Trigger or minimum cadence      |
| -: | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------- |
|  6 | **Requirements Quality Loop**                                | **Trigger:** Creation or modification of a requirement, feature, story, or acceptance criterion. **Run:** Check clarity, completeness, testability, feasibility, assumptions, non-functional needs, data needs, security, dependencies, and measurable acceptance criteria. **Output:** Ready, revise, or reject decision with identified gaps.              | Every requirement or story      |
|  7 | **Requirements Change Control Loop**                         | **Trigger:** Requested change to approved scope or behavior. **Run:** Assess impact on value, scope, cost, schedule, architecture, data, security, testing, operations, and dependencies; route the change to the correct authority. **Output:** Approved, deferred, or rejected change with updated baselines and impact evidence.                          | Every material change           |
|  8 | **Requirements Traceability Loop**                           | **Trigger:** Requirement, design, code, test, or release changes. **Run:** Link business objective to requirement, design, implementation, test case, release, and production evidence; identify broken or missing links. **Output:** Traceability graph or matrix, coverage gaps, and release evidence.                                                     | Every change, with release gate |
|  9 | **Backlog Refinement Loop**                                  | **Trigger:** New work, changed priorities, or upcoming iteration planning. **Run:** Remove duplicates, split oversized work, clarify outcomes, add acceptance criteria, identify dependencies, estimate effort, and establish readiness. **Output:** Prioritized, estimated, and delivery-ready backlog.                                                     | Weekly or every sprint          |
| 10 | **Cross-Team, System and Vendor Dependency Management Loop** | **Trigger:** Work depends on another team, platform, vendor, approval, interface, or delivery. **Run:** Record dependency, owner, required outcome, due date, assumptions, status, contingency, and escalation threshold. **Output:** Current dependency register, alerts, and resolution or escalation actions.                                             | Event-driven, reviewed weekly   |
| 11 | **Risk Management Loop**                                     | **Trigger:** New work, material change, incident, delay, audit finding, or emerging uncertainty. **Run:** Identify and score probability and impact, define triggers, assign ownership, plan mitigation and contingency, and reassess residual risk. **Output:** Updated risk register and explicit accept, mitigate, transfer, avoid, or escalate decision. | Continuous, reviewed weekly     |
| 12 | **Sprint Execution Loop**                                    | **Trigger:** Start of an iteration or committed delivery period. **Run:** Confirm goal and capacity, commit work, track progress, remove blockers, validate completed work, demonstrate outcomes, and close unfinished items correctly. **Output:** Completed sprint objective, accepted work, delivery metrics, and carried-over decisions.                 | Every sprint, tracked daily     |
| 13 | **Delivery Forecasting Loop**                                | **Trigger:** New scope, throughput changes, dependency changes, or schedule variance. **Run:** Use remaining scope, historical throughput, capacity, uncertainty, and dependencies to produce scenario-based forecasts. **Output:** Updated completion range, confidence level, assumptions, and corrective actions.                                         | Weekly                          |
| 14 | **Retrospective Improvement Loop**                           | **Trigger:** End of sprint, release, incident, or major delivery stage. **Run:** Review evidence, identify effective and ineffective practices, find root causes, select a limited number of improvements, assign owners, and measure whether prior actions worked. **Output:** Owned improvement actions with due dates and effectiveness measures.         | Every sprint or release         |

---

# 3. Architecture, Design and Modernization

|  # | Loop name                                              | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                               | Trigger or minimum cadence                      |
| -: | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| 15 | **Design Review Loop**                                 | **Trigger:** New solution, major feature, integration, data flow, or significant design change. **Run:** Review functional design, non-functional requirements, interfaces, data movement, failure modes, security boundaries, operability, scalability, and standards. **Output:** Approved, conditionally approved, or rejected design with required actions and decision record.                  | Every material design change                    |
| 16 | **Architecture Fitness and Future Compatibility Loop** | **Trigger:** Architectural change, fitness threshold breach, or scheduled review. **Run:** Measure modularity, coupling, scalability, resilience, portability, replaceability, interoperability, technology support, and readiness for new models, runtimes, or deployment targets. **Output:** Architecture fitness score and prioritized remediation backlog.                                      | Continuous metrics, monthly or quarterly review |
| 17 | **API Lifecycle and Backward Compatibility Loop**      | **Trigger:** New API, contract modification, version change, or planned deprecation. **Run:** Validate schemas, authentication, authorization, rate limits, errors, versioning, consumer impact, backward compatibility, documentation, and deprecation plan. **Output:** Approved API version, migration guidance, consumer notifications, and retirement timeline.                                 | Every API change                                |
| 18 | **Configuration and Feature Flag Governance Loop**     | **Trigger:** Configuration or feature-flag creation, modification, rollout, or retirement. **Run:** Validate ownership, environment scope, safe defaults, secrets handling, expiry date, rollout population, rollback behavior, and stale-flag removal. **Output:** Approved configuration baseline or flag record with expiry and rollback controls.                                                | Every change, with daily stale scan             |
| 19 | **Technical Debt Loop**                                | **Trigger:** Detection of obsolete code, complexity, poor maintainability, workaround, unsupported component, or repeated delivery friction. **Run:** Record debt, estimate impact and continuing cost, prioritize against business risk, remediate, and verify measurable reduction. **Output:** Technical-debt register, remediation decision, and trend metrics.                                  | Continuous capture, weekly or monthly review    |
| 20 | **Application Modernization Loop**                     | **Trigger:** Unsupported technology, excessive operating cost, reliability limitation, scalability constraint, or strategic platform change. **Run:** Inventory legacy components, assess support and risk, compare modernization options, plan migration, execute incrementally, and retire replaced assets. **Output:** Modernization roadmap, migration increments, and decommissioning evidence. | Quarterly or annual                             |

---

# 4. Software Engineering and Build

|  # | Loop name                                           | Skill-ready definition                                                                                                                                                                                                                                                                                                                        | Trigger or minimum cadence                  |
| -: | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| 21 | **Code Build Loop**                                 | **Trigger:** Approved engineering task or defect. **Run:** Inspect existing code, understand constraints, design the change, implement it, compile or package it, execute local checks, and prepare reviewable artifacts. **Output:** Working change, updated tests, build artifact, and implementation evidence.                             | Every work item or commit                   |
| 22 | **Code Quality Loop**                               | **Trigger:** Code creation or modification. **Run:** Check standards, readability, complexity, duplication, maintainability, error handling, dead code, logging, and testability; refactor until thresholds pass. **Output:** Quality results, resolved findings, and maintainable code.                                                      | Every commit or pull request                |
| 23 | **Pull Request Review Loop**                        | **Trigger:** Pull request ready for review. **Run:** Independently inspect correctness, tests, design, security, performance, data impact, compatibility, and operational effects; require correction and re-review where needed. **Output:** Approved or rejected pull request with resolved comments and review evidence.                   | Every pull request                          |
| 24 | **Software Dependency and Package Management Loop** | **Trigger:** New package, version update, vulnerability, license change, or package retirement. **Run:** Check necessity, version support, vulnerabilities, licenses, compatibility, transitive dependencies, upgrade impact, and regression results. **Output:** Approved package baseline, lockfile update, exception, or replacement plan. | Continuous scan and every dependency change |
| 25 | **CI Pipeline Loop**                                | **Trigger:** Commit, pull request, merge, or release candidate. **Run:** Build, test, scan, package, sign where required, publish artifacts, retain evidence, and enforce quality gates automatically. **Output:** Accepted or blocked build with immutable pipeline results and deployable artifact.                                         | Every commit or pull request                |

---

# 5. Testing, Validation and Experience Quality

|  # | Loop name                        | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                 | Trigger or minimum cadence                   |
| -: | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| 26 | **Test Data Management Loop**    | **Trigger:** New test scenario, changed data structure, or test-environment refresh. **Run:** Define representative cases and expected results, create synthetic or properly masked data, version datasets, seed environments, reset state, and enforce privacy and retention controls. **Output:** Approved test dataset, expected outcomes, and data-control record. | Before test execution and scheduled refresh  |
| 27 | **Unit Testing Loop**            | **Trigger:** Function, class, module, or component change. **Run:** Derive positive, negative, boundary, and error cases; execute tests; measure coverage and test strength; fix failures. **Output:** Passing unit suite and coverage evidence.                                                                                                                       | Every commit or build                        |
| 28 | **Integration Testing Loop**     | **Trigger:** Change to service, database, API, queue, file, event, or external integration. **Run:** Validate contracts, data transformation, authentication, timeout, retry, failure handling, and reconciliation across participating components. **Output:** Passing integration suite and verified interface contracts.                                            | Every relevant merge or build                |
| 29 | **End-to-End Testing Loop**      | **Trigger:** Release candidate or material change to a critical journey. **Run:** Execute complete user and business workflows across systems, verify data movement and final outcomes, handle external dependencies, and clean up state. **Output:** End-to-end journey evidence and unresolved failure list.                                                         | Nightly for critical paths and every release |
| 30 | **Regression Testing Loop**      | **Trigger:** Code, configuration, infrastructure, model, data, or dependency change. **Run:** Select an impact-based regression set, execute it, compare with approved baseline, triage failures, and rerun after corrections. **Output:** Regression confidence result and release-blocking findings.                                                                 | Every merge and release                      |
| 31 | **Performance Testing Loop**     | **Trigger:** Significant implementation, architecture, infrastructure, database, or model change. **Run:** Execute load, stress, spike, endurance, concurrency, and scalability tests; measure latency, throughput, error rate, and resource use; identify bottlenecks. **Output:** Performance report, capacity recommendation, and tuning backlog.                   | Major change and release                     |
| 32 | **User Acceptance Testing Loop** | **Trigger:** Business-ready release candidate. **Run:** Prepare real business scenarios, authorized testers, expected outcomes, and representative data; record findings, resolve defects, and obtain explicit acceptance or waiver. **Output:** Business sign-off, rejected release, or conditional acceptance.                                                       | Every business release                       |
| 33 | **Accessibility Loop**           | **Trigger:** New or changed user interface, interaction, document, or customer journey. **Run:** Perform automated and manual checks for keyboard use, screen readers, labels, focus, structure, contrast, alternatives, and understandable errors. **Output:** Accessibility results, defects, exceptions, and conformance evidence.                                  | Every UI change and release                  |
| 34 | **Defect Management Loop**       | **Trigger:** Defect reported by testing, monitoring, customer, security, or operations. **Run:** Record and reproduce the issue, classify impact and priority, assign ownership, determine cause, fix, retest, run regression, and close with evidence. **Output:** Resolved or accepted defect and defect-trend data.                                                 | Event-driven, triaged daily                  |
| 35 | **UX Improvement Loop**          | **Trigger:** User feedback, usability issue, abandonment, support volume, or product-analytics signal. **Run:** Identify friction, form a hypothesis, redesign or prototype, perform usability testing, release the improvement, and measure the outcome. **Output:** Validated UX improvement and updated journey metrics.                                            | Continuous, reviewed each sprint or month    |

---

# 6. DevOps, Release and Environment Management

|  # | Loop name                                  | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                          | Trigger or minimum cadence                                                 |
| -: | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 36 | **Release Readiness Loop**                 | **Trigger:** Release candidate prepared for deployment. **Run:** Verify scope, traceability, tests, defects, security, compliance, data migration, operational support, monitoring, rollback, approvals, and known limitations. **Output:** Go, conditional-go, or no-go decision with evidence.                                                                                                | Every release                                                              |
| 37 | **Operational Readiness and Runbook Loop** | **Trigger:** New service, major capability, support-model change, or production release. **Run:** Confirm ownership, SLOs, monitoring, alerts, capacity, dependencies, support hours, escalation, recovery steps, runbooks, and on-call readiness. **Output:** Operational-readiness approval and usable runbook package.                                                                       | Every new service or major release                                         |
| 38 | **Deployment Validation Loop**             | **Trigger:** Deployment to any controlled environment. **Run:** Execute prechecks, deploy, validate configuration and migrations, run smoke tests, inspect logs and health metrics, compare canary results, and continue or roll back. **Output:** Verified deployment or controlled rollback with evidence.                                                                                    | Every deployment                                                           |
| 39 | **Environment Drift Loop**                 | **Trigger:** Detected or scheduled comparison between actual and approved environments. **Run:** Compare infrastructure, configuration, secrets references, runtime versions, dependencies, and access settings against source-controlled baselines; reconcile or record approved exceptions. **Output:** Drift report and restored or accepted environment state.                              | Continuous or daily                                                        |
| 40 | **Rollback, Backup and Recovery Loop**     | **Trigger:** Release planning, backup schedule, recovery test, deployment failure, data loss, or service disruption. **Run:** Create and verify backups, validate rollback compatibility, restore systems and data, reconcile state, test recovery objectives, and document unrecoverable gaps. **Output:** Proven rollback and restore capability, recovery evidence, and remediation actions. | Backup continuously or daily; test quarterly and before high-risk releases |

---

# 7. Operations, Reliability and Service Management

|  # | Loop name                                             | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                                                    | Trigger or minimum cadence             |
| -: | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 41 | **Observability Improvement Loop**                    | **Trigger:** Monitoring gap, unexplained behavior, incident, new component, or noisy alert. **Run:** Assess logs, metrics, traces, business events, dashboards, correlation identifiers, alert coverage, and signal quality; add missing telemetry and remove noise. **Output:** Improved observability coverage and owned instrumentation backlog.                                                                       | Continuous, reviewed weekly            |
| 42 | **Reliability, SLO and Error-Budget Management Loop** | **Trigger:** SLO definition, service degradation, error-budget consumption, or scheduled reliability review. **Run:** Define or measure SLIs and SLOs, analyze failure modes, track error budget, prioritize reliability work, and restrict risky changes when thresholds are exceeded. **Output:** Reliability scorecard, error-budget decision, and resilience actions.                                                 | Continuous, reviewed weekly or monthly |
| 43 | **Incident Management Loop**                          | **Trigger:** Actual or suspected service disruption, degradation, security event, or customer-impacting failure. **Run:** Detect, classify severity, assign command, contain, restore service, communicate, preserve evidence, and create follow-up actions. **Output:** Restored service, incident timeline, impact statement, and corrective actions.                                                                   | Event-driven                           |
| 44 | **AI Incident Response Loop**                         | **Trigger:** Harmful AI output, data leakage, agent overreach, retrieval poisoning, model failure, prompt attack, or unsafe automated decision. **Run:** Contain the AI path, suspend tools or model versions, preserve prompts and traces, assess affected users and data, remediate controls, and retest. **Output:** Containment evidence, AI incident report, corrected configuration, and expanded evaluation cases. | Event-driven                           |
| 45 | **Problem Management Loop**                           | **Trigger:** Repeated incidents, recurring defects, unexplained instability, or material post-incident finding. **Run:** Group related events, analyze systemic cause, document known error and workaround, implement permanent correction, and monitor recurrence. **Output:** Root-cause record, permanent corrective action, and recurrence evidence.                                                                  | Weekly and after major incidents       |
| 46 | **Performance, Capacity, Cost and AI Economics Loop** | **Trigger:** Utilization change, budget variance, latency issue, demand forecast, or new model or infrastructure option. **Run:** Analyze application and AI workloads, capacity, token use, model routing, caching, storage, network, and infrastructure; optimize while protecting quality and reliability. **Output:** Capacity forecast, cost-per-outcome metrics, optimization actions, and verified savings.        | Continuous, reviewed weekly or monthly |
| 47 | **Chaos Engineering and Resilience Testing Loop**     | **Trigger:** New resilience hypothesis, architecture change, or scheduled exercise. **Run:** Define safe failure scenarios and blast radius, inject controlled faults, observe detection and recovery, stop safely, remediate weaknesses, and repeat. **Output:** Proven resilience behavior, failure evidence, and hardening backlog.                                                                                    | Monthly or quarterly                   |
| 48 | **Business Continuity and Crisis Management Loop**    | **Trigger:** Scheduled exercise or prolonged technology, vendor, facility, workforce, cyber, or regional disruption. **Run:** Identify critical services, dependencies, alternate operating methods, authority, communication, and recovery priorities; exercise the plan and correct failures. **Output:** Tested continuity plan, crisis decision record, and recovery improvements.                                    | Semiannual or annual                   |

---

# 8. Data, Database and Knowledge Management

|  # | Loop name                                                   | Skill-ready definition                                                                                                                                                                                                                                                                                                                                             | Trigger or minimum cadence                |
| -: | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| 49 | **Data Governance Loop**                                    | **Trigger:** New dataset, changed use, new system, ownership gap, or governance review. **Run:** Catalog and classify data, assign owner and steward, define permitted use, quality expectations, lineage, access, retention, residency, and disposal rules. **Output:** Governed data asset with accountable ownership and enforceable policies.                  | Continuous, reviewed monthly or quarterly |
| 50 | **Data Schema and Contract Evolution Loop**                 | **Trigger:** Schema, event, file, table, or data-interface change. **Run:** Version the contract, identify producers and consumers, test compatibility, plan migration and backfill, manage dual-read or dual-write periods, and define rollback. **Output:** Approved schema version, migration plan, and consumer compatibility evidence.                        | Every schema change                       |
| 51 | **AI Data Preparation Loop**                                | **Trigger:** New or changed data for training, tuning, evaluation, retrieval, or prompt examples. **Run:** Validate source and usage rights, clean, normalize, deduplicate, label, de-identify, assess coverage and bias, split datasets, and version the result. **Output:** Approved dataset, data documentation, quality results, and lineage.                  | Every AI dataset change                   |
| 52 | **Data Quality Loop**                                       | **Trigger:** Data arrival, failed rule, anomaly, consumer complaint, or scheduled profiling. **Run:** Measure completeness, accuracy, validity, consistency, uniqueness, and timeliness; locate the source; correct data or pipeline logic; and reprocess affected records. **Output:** Data-quality score, resolved issue, and preventive rule.                   | Continuous or daily                       |
| 53 | **Data Pipeline Reliability Loop**                          | **Trigger:** Batch or stream execution, freshness breach, volume anomaly, schema failure, or downstream mismatch. **Run:** Monitor execution, reconcile counts, handle retries and dead letters, preserve idempotency, backfill safely, and confirm downstream receipt. **Output:** Reconciled pipeline run, recovery evidence, and unresolved exceptions.         | Continuous                                |
| 54 | **Database Performance Loop**                               | **Trigger:** Slow query, capacity alert, lock contention, replication lag, or scheduled review. **Run:** Inspect execution plans, indexes, partitions, locks, connection use, storage, replication, and configuration; tune and retest under realistic load. **Output:** Database performance results and approved tuning changes.                                 | Continuous, reviewed daily or weekly      |
| 55 | **Knowledge Base Freshness and RAG Content Lifecycle Loop** | **Trigger:** Source creation, modification, expiry, revocation, or retrieval-quality issue. **Run:** Validate authority and access, ingest, chunk, index, refresh, expire, remove, and reindex content; confirm that deleted or restricted material is no longer retrievable. **Output:** Current knowledge index, freshness status, and content-lineage evidence. | Continuous or daily                       |
| 56 | **Model, Data and Prompt Lineage and Reproducibility Loop** | **Trigger:** Change to model, data, prompt, code, configuration, evaluation, or environment. **Run:** Record exact versions, relationships, parameters, approvals, artifacts, and runtime conditions; rerun a representative case to confirm reproducibility. **Output:** Lineage manifest and reproducible execution evidence.                                    | Every AI change and release gate          |

---

# 9. AI and Generative AI Lifecycle and Quality

|  # | Loop name                                   | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                                | Trigger or minimum cadence                              |
| -: | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 57 | **Prompt Engineering Loop**                 | **Trigger:** New AI task, prompt defect, model change, or evaluation regression. **Run:** Define the task contract, instructions, variables, examples, constraints, source use, output schema, and refusal behavior; evaluate, version, deploy, and preserve rollback. **Output:** Approved prompt version and evaluation results.                                                                    | Every prompt change                                     |
| 58 | **Model Evaluation and Benchmarking Loop**  | **Trigger:** New model, configuration, provider, fine-tune, routing strategy, or scheduled challenger review. **Run:** Execute current and candidate models on production-relevant and adversarial datasets; compare task quality, consistency, tool use, safety, latency, and cost. **Output:** Model scorecard and adopt, retain, route, restrict, or reject decision.                              | Every model change, with monthly or quarterly challenge |
| 59 | **RAG Quality Loop**                        | **Trigger:** Retrieval, embedding, chunking, reranking, source, index, or model change. **Run:** Evaluate ingestion, recall, precision, ranking, source authority, citation accuracy, groundedness, answer relevance, conflict handling, and abstention behavior. **Output:** RAG scorecard, failure categories, and tuning actions.                                                                  | Every RAG change, with scheduled regression             |
| 60 | **AI Safety and Responsible AI Loop**       | **Trigger:** New AI use case, model, data, prompt, user group, deployment, or material behavior change. **Run:** Assess harmful outputs, bias, fairness, privacy, transparency, human impact, explainability needs, misuse, vulnerable users, and control effectiveness. **Output:** Risk classification, required safeguards, residual-risk acceptance, and approval status.                         | Every AI release, with quarterly deep review            |
| 61 | **Hallucination Reduction Loop**            | **Trigger:** Unsupported answer, incorrect citation, fabricated detail, or low-grounding score. **Run:** Capture and classify the failure, inspect context and retrieval, improve prompt, source selection, verification, confidence, or abstention controls, and add the case to regression testing. **Output:** Corrected behavior and reduced unsupported-answer rate.                             | Continuous, reviewed daily or weekly                    |
| 62 | **Model and Data Drift Monitoring Loop**    | **Trigger:** Production inference, scheduled evaluation, or detected distribution change. **Run:** Monitor input, data, concept, output, calibration, segment, and outcome drift; compare with baselines; alert and initiate reconfiguration, retraining, rollback, or investigation. **Output:** Drift status, affected segments, and corrective decision.                                           | Continuous or daily                                     |
| 63 | **AI Feedback Learning Loop**               | **Trigger:** User rating, correction, escalation, override, abandonment, or measured downstream outcome. **Run:** Validate and categorize feedback, remove noise, identify systemic causes, prioritize improvements, add suitable cases to evaluation or training data, and measure change. **Output:** Feedback-derived improvement backlog and verified quality movement.                           | Continuous, processed weekly                            |
| 64 | **Evaluation Dataset Evolution Loop**       | **Trigger:** Production failure, new capability, emerging threat, model change, or weak evaluation coverage. **Run:** Add difficult, representative, adversarial, ambiguous, and edge cases; check labels, duplication, leakage, contamination, segment balance, and version history. **Output:** Versioned evaluation set with documented coverage.                                                  | Weekly or monthly, and after incidents                  |
| 65 | **Model Lifecycle and Upgrade Safety Loop** | **Trigger:** Model onboarding, upgrade, routing change, deprecation, provider retirement, or rollback need. **Run:** Register the model, evaluate compatibility and risk, perform shadow and canary testing, obtain approval, promote gradually, monitor behavior, and roll back or retire safely. **Output:** Approved lifecycle state, deployment decision, migration record, and rollback package. | Every model lifecycle event                             |

---

# 10. Agentic AI Execution and Orchestration

|  # | Loop name                                              | Skill-ready definition                                                                                                                                                                                                                                                                                                                                              | Trigger or minimum cadence                             |
| -: | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 66 | **Agent Goal Achievement Loop**                        | **Trigger:** Agent receives an objective. **Run:** Interpret the goal, constraints, authority, and success conditions; build a plan; execute actions; observe results; evaluate progress; replan; and stop, complete, or escalate. **Output:** Verified result, execution trace, and completion evidence.                                                           | Every agent task                                       |
| 67 | **Agent Planning Quality Loop**                        | **Trigger:** New agent workflow, planning failure, or sampled production run. **Run:** Evaluate decomposition, ordering, dependencies, assumptions, risks, unnecessary actions, stopping conditions, and recovery paths; improve planning prompts or policies and retest. **Output:** Planning score and corrected planning strategy.                               | Every material workflow change and continuous sampling |
| 68 | **Tool Selection Loop**                                | **Trigger:** Agent determines that an external capability may be required. **Run:** Match intent to approved tools, schemas, permissions, data sensitivity, cost, reversibility, and risk; select the safest suitable tool or decline tool use. **Output:** Authorized tool choice and rationale.                                                                   | Every proposed tool action                             |
| 69 | **Tool Execution Validation Loop**                     | **Trigger:** Tool call proposed or completed. **Run:** Validate arguments and preconditions, execute within scope, inspect the response, verify the actual system state, detect partial effects, and compensate, retry, or escalate when necessary. **Output:** Verified action result and tool evidence.                                                           | Every tool call                                        |
| 70 | **Agent Context Management Loop**                      | **Trigger:** New task, reasoning step, context-window pressure, or retrieval request. **Run:** Preserve instruction hierarchy, retrieve authoritative material, separate untrusted content, remove irrelevant information, compress safely, maintain provenance, and enforce token limits. **Output:** Minimal sufficient context package with source traceability. | Every task or reasoning cycle                          |
| 71 | **Agent Memory Loop**                                  | **Trigger:** Memory read, write, update, expiry, correction, or deletion request. **Run:** Decide whether information should be stored, classify sensitivity, obtain required consent, deduplicate, resolve conflicts, set retention, retrieve selectively, and support correction and deletion. **Output:** Accurate, relevant, and governed memory state.         | Every memory operation, with scheduled cleanup         |
| 72 | **Agent Resource, Budget and Rate-Limit Control Loop** | **Trigger:** Agent run, tool call, transaction, or resource-threshold approach. **Run:** Enforce limits for tokens, time, model calls, tool calls, spend, concurrency, retries, data volume, and transaction impact; stop or escalate before limits are exceeded. **Output:** Resource decision, consumption record, and controlled termination where required.     | Real-time during every run                             |
| 73 | **Agent State Consistency and Idempotency Loop**       | **Trigger:** State-changing action, retry, timeout, parallel execution, or recovery. **Run:** Use operation identifiers, checkpoints, transactions, locks where appropriate, and idempotency controls; detect duplicates, conflicts, replay, and partial completion; reconcile or compensate. **Output:** Consistent system state and state-transition evidence.    | Every state-changing action                            |
| 74 | **Agent Failure Recovery Loop**                        | **Trigger:** Planning, model, tool, data, permission, policy, or execution failure. **Run:** Classify the failure, determine whether retry is safe, apply limits and backoff, select an alternate path, roll back partial work, or escalate to a human. **Output:** Recovered workflow or controlled failure with diagnostic evidence.                              | Every agent failure                                    |
| 75 | **Multi-Agent Coordination Loop**                      | **Trigger:** A goal is divided among multiple specialized agents. **Run:** Define roles and contracts, assign work, manage dependencies and shared state, exchange outputs, resolve conflicts, validate contributions, and integrate the result. **Output:** Coherent combined result and contribution trace.                                                       | Every multi-agent workflow                             |
| 76 | **Agent Delegation and Accountability Loop**           | **Trigger:** Human or agent delegates authority or work to another agent. **Run:** Record delegator, delegatee, permitted scope, data, tools, duration, limits, downstream delegation, and accountable human; prevent authority expansion beyond the original grant. **Output:** Enforceable delegation record and accountability trail.                            | Every delegation                                       |

---

# 11. Security, Privacy and Supply-Chain Assurance

|  # | Loop name                                          | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                                               | Trigger or minimum cadence                          |
| -: | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| 77 | **Secure SDLC Loop**                               | **Trigger:** New product, feature, design, code change, or release. **Run:** Define security requirements, perform threat modeling, design review, static and dynamic testing, secrets and infrastructure scanning, remediation, retesting, and release-risk assessment. **Output:** Security evidence, unresolved-risk decision, and release status.                                                                | Every material change                               |
| 78 | **Model and Agent Interaction Security Loop**      | **Trigger:** Model, prompt, retrieval, memory, agent, tool, or external-content change. **Run:** Test direct and indirect prompt injection, jailbreaks, context and memory poisoning, retrieval poisoning, system-instruction exposure, data exfiltration, tool hijacking, and cross-agent attacks; strengthen isolation and authorization. **Output:** Attack results, control effectiveness, and regression suite. | Every AI change, with continuous runtime controls   |
| 79 | **Agent Guardrail Loop**                           | **Trigger:** Agent proposes an action, response, tool call, or state change. **Run:** Evaluate the proposal against user intent, policy, authorization, allowlists, risk tier, reversibility, transaction limits, and approval requirements; allow, modify, block, or escalate. **Output:** Guardrail decision and audit record.                                                                                     | Every consequential agent action                    |
| 80 | **Agent Identity and Credential Governance Loop**  | **Trigger:** Agent creation, session start, tool access, credential change, or termination. **Run:** Assign a distinct non-human identity, issue scoped and short-lived credentials, store secrets securely, rotate and revoke access, and preserve action attribution. **Output:** Governed agent identity and credential record.                                                                                   | Every agent session or access change                |
| 81 | **Access Governance Loop**                         | **Trigger:** User, service, agent, role, employment, responsibility, or system change. **Run:** Apply least privilege, role or attribute policies, privileged-access controls, joiner-mover-leaver processing, conflict checks, periodic recertification, and access removal. **Output:** Approved access state and certification evidence.                                                                          | Continuous, with quarterly recertification          |
| 82 | **Vulnerability Management Loop**                  | **Trigger:** Scanner finding, advisory, penetration test, incident, or researcher report. **Run:** Validate the issue, assess exposure and exploitability, prioritize by business impact, assign remediation SLA, patch or mitigate, retest, and accept residual risk only through authority. **Output:** Closed, mitigated, or accepted vulnerability record.                                                       | Continuous scanning, daily triage                   |
| 83 | **Security Operations and Threat Detection Loop**  | **Trigger:** Security telemetry, suspicious behavior, intelligence update, or detection rule. **Run:** Collect and correlate signals, enrich context, triage alerts, investigate, contain threats, preserve evidence, and tune detections based on false positives and missed events. **Output:** Security disposition, incident escalation, and improved detection logic.                                           | Continuous                                          |
| 84 | **AI Abuse and Misuse Monitoring Loop**            | **Trigger:** AI request, user behavior, traffic anomaly, policy evasion, or suspicious usage pattern. **Run:** Detect malicious automation, fraud, scraping, prohibited content, credential abuse, data extraction, evasion, and coordinated misuse; throttle, block, challenge, or investigate. **Output:** Abuse disposition and updated detection controls.                                                       | Continuous                                          |
| 85 | **Frontier Cyber Defense Loop**                    | **Trigger:** New attacker capability, frontier-model release, critical vulnerability class, or threat-intelligence change. **Run:** Reassess attack surface assuming AI-enhanced reconnaissance, code analysis, social engineering, and exploit chaining; red-team the product and reduce remediation time. **Output:** Updated threat model, exploit-chain findings, and hardening plan.                            | Monthly or quarterly, and after major threat change |
| 86 | **Software Supply-Chain and Build Integrity Loop** | **Trigger:** Source change, dependency update, build, artifact publication, or release. **Run:** Verify source provenance, signed changes, isolated build process, dependency integrity, software bill of materials, artifact signatures, attestations, and reproducibility. **Output:** Trusted or blocked artifact with provenance evidence.                                                                       | Every build and release                             |
| 87 | **AI Supply-Chain Security Loop**                  | **Trigger:** Onboarding or changing a model, dataset, embedding, agent framework, plugin, MCP server, tool, container, or external AI API. **Run:** Inventory the component, assess provenance, ownership, license, security, privacy, availability, provider change risk, and required access; approve, restrict, monitor, or replace it. **Output:** AI component record and supplier-risk decision.               | Every component change, reviewed quarterly          |
| 88 | **Privacy Engineering and Data Protection Loop**   | **Trigger:** New feature, data flow, processing purpose, jurisdiction, model use, or privacy incident. **Run:** Map data, minimize collection, confirm purpose and consent, enforce residency, retention and deletion, perform privacy threat assessment, and test controls. **Output:** Privacy decision, required controls, assessment evidence, and residual-risk record.                                         | Every data-flow change                              |
| 89 | **Audit Logging and Forensic Readiness Loop**      | **Trigger:** User, service, model, agent, tool, data, configuration, security, or administrative action. **Run:** Produce tamper-resistant, time-synchronized, correlated logs with appropriate retention and access controls; periodically prove that an event can be reconstructed. **Output:** Searchable evidence trail and forensic-readiness result.                                                           | Continuous, tested quarterly                        |
| 90 | **AI Red-Team Evolution Loop**                     | **Trigger:** New attack method, provider disclosure, internal failure, incident, or model capability. **Run:** Convert threats and failures into adversarial cases, run them across versions, record bypasses, improve defenses, and preserve failures as security regression tests. **Output:** Expanding adversarial suite and control-effectiveness trend.                                                        | Monthly or quarterly, and after incidents           |

---

# 12. Frontier, Quantum and Strategic Resilience

|  # | Loop name                                                                         | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                                                                                            | Trigger or minimum cadence                                |
| -: | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 91 | **Frontier Model Advancement Loop**                                               | **Trigger:** New model, major capability release, material price change, or strategic review. **Run:** Maintain a capability radar, benchmark new models on product-specific tasks, compare quality, safety, autonomy, cost, latency, and operational constraints, and decide whether to experiment, adopt, route, or defer. **Output:** Model-advancement scorecard and product action plan.                                                                     | Monthly or quarterly                                      |
| 92 | **Model Portability and Exit Loop**                                               | **Trigger:** Provider concentration concern, model retirement, service degradation, contract change, or scheduled portability test. **Run:** Test alternate models, isolate provider-specific prompts and schemas, verify tool and state portability, measure migration effort and quality loss, and maintain failover and exit procedures. **Output:** Portability score, validated fallback, and exit plan.                                                     | Quarterly or semiannual                                   |
| 93 | **Capability Absorption Loop**                                                    | **Trigger:** A model gains native capability currently implemented through custom code, chains, classifiers, extraction logic, or infrastructure. **Run:** Identify potentially redundant components, benchmark native replacement, compare quality, cost, control, and risk, simplify architecture, and retire unnecessary layers. **Output:** Simplification decision, removed complexity, and verified replacement.                                            | Quarterly                                                 |
| 94 | **Product Obsolescence Detection Loop**                                           | **Trigger:** Frontier capability, competitor, platform, pricing, or customer-expectation change. **Run:** Test whether a general model or platform now performs the product’s core task, identify commoditized features, assess unique data, workflow, trust, integration, compliance, and distribution advantages, and reposition where needed. **Output:** Obsolescence-risk score and defend, differentiate, pivot, partner, or retire decision.               | Quarterly                                                 |
| 95 | **AGI Readiness and Capability Escalation Loop**                                  | **Trigger:** Material increase in reasoning, autonomy, cyber ability, tool use, self-correction, persistence, or ability to complete long-horizon work. **Run:** Reclassify capability and impact, rerun adversarial evaluations, reassess permissions and human supervision, strengthen containment, and reduce or expand autonomy only with evidence. **Output:** Capability tier, permitted use, and required safeguards.                                      | Every significant capability increase, reviewed quarterly |
| 96 | **Post-Quantum Cryptography, Crypto-Agility and Long-Lived Data Protection Loop** | **Trigger:** Cryptographic change, standard update, vendor roadmap change, or scheduled quantum-risk review. **Run:** Inventory cryptography, identify quantum-vulnerable algorithms and long-lived sensitive data, abstract algorithm dependencies, test replacement or hybrid methods, measure interoperability and performance, and prioritize migration. **Output:** Cryptographic inventory, exposure register, crypto-agility score, and migration roadmap. | Semiannual or annual                                      |
| 97 | **Catastrophic Failure and Containment Loop**                                     | **Trigger:** High-risk model, agent, privileged tool, major release, or scheduled containment exercise. **Run:** Define worst-case scenarios, test kill switches, credential revocation, network isolation, rate and transaction limits, checkpoints, rollback, safe mode, manual takeover, and immutable evidence. **Output:** Containment result, maximum-loss estimate, and corrected emergency procedures.                                                    | Quarterly or semiannual                                   |
| 98 | **Quantum Computing Opportunity Scouting Loop**                                   | **Trigger:** Strategic technology review or credible quantum or hybrid capability development. **Run:** Identify optimization, simulation, search, security, or scientific workloads; establish a strong classical baseline; assess data, hardware, cost, maturity, and measurable advantage; run limited experiments. **Output:** Experiment evidence and pursue, monitor, partner, or reject decision.                                                          | Semiannual or annual                                      |

---

# 13. Enterprise Governance, Adoption and Workforce

|   # | Loop name                                               | Skill-ready definition                                                                                                                                                                                                                                                                                                                                                                       | Trigger or minimum cadence                         |
| --: | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
|  99 | **Adoption Loop**                                       | **Trigger:** Product launch, usage change, low activation, abandonment, weak retention, or support feedback. **Run:** Measure awareness, onboarding, activation, repeated use, outcome realization, and drop-off; segment users; improve training, workflow, guidance, and product experience. **Output:** Adoption scorecard and targeted intervention plan.                                | Continuous analytics, monthly review               |
| 100 | **Human Oversight, Approval and Calibration Loop**      | **Trigger:** High-impact action requiring approval or scheduled review of human decisions. **Run:** Present evidence, risk, alternatives, and recommendation to an authorized reviewer; capture the decision; periodically measure reviewer agreement, expertise, fatigue, automation bias, and escalation quality. **Output:** Approval record and calibrated human-review process.         | Every high-impact action, reviewed monthly         |
| 101 | **Agent Autonomy Calibration Loop**                     | **Trigger:** New agent, material model change, performance trend, incident, or scheduled autonomy review. **Run:** Evaluate task risk, historical reliability, reversibility, detectability, supervision cost, and failure severity; assign the appropriate autonomy mode and monitor outcomes. **Output:** Approved autonomy level and conditions for expansion or reduction.               | Monthly or quarterly                               |
| 102 | **Autonomy Boundary Review Loop**                       | **Trigger:** Agent permission, tool, system, model, workflow, or data-access change. **Run:** Inventory what the agent can read, write, delete, deploy, communicate, purchase, approve, spend, create, or delegate; simulate misuse and remove unnecessary authority. **Output:** Authority map, least-privilege policy, and prohibited-action list.                                         | Every authority change, reviewed quarterly         |
| 103 | **Capability-Based Governance Loop**                    | **Trigger:** Model or agent onboarding, upgrade, new use, or scheduled governance review. **Run:** Classify actual capabilities and potential impact rather than relying on vendor labels; map the tier to mandatory evaluations, security, monitoring, human approval, containment, and audit controls. **Output:** Governance tier and enforceable control profile.                        | Every onboarding or upgrade, reviewed quarterly    |
| 104 | **Compliance Evidence Loop**                            | **Trigger:** Control execution, audit requirement, regulatory obligation, or evidence-expiry threshold. **Run:** Map controls to systems and owners, collect authoritative evidence, verify completeness and freshness, identify gaps, initiate remediation, and package evidence for review. **Output:** Current control status and audit-ready evidence set.                               | Continuous collection, monthly or quarterly review |
| 105 | **Legal, Regulatory and Standards Watch Loop**          | **Trigger:** New law, regulation, standard, enforcement action, contractual obligation, or jurisdictional expansion. **Run:** Determine applicability, assess product and operating impact, map required changes to controls and owners, track implementation, and retain decision evidence. **Output:** Obligation register and required product, process, or policy changes.               | Monthly or quarterly                               |
| 106 | **Vendor and Third-Party Risk and SLA Loop**            | **Trigger:** Vendor onboarding, contract renewal, performance breach, incident, material service change, or scheduled review. **Run:** Assess security, privacy, resilience, compliance, concentration, subcontractors, data access, financial viability, service performance, exit capability, and SLA compliance. **Output:** Approved, restricted, remediated, or exited vendor decision. | Onboarding and monthly or quarterly review         |
| 107 | **IP, Copyright and License Compliance Loop**           | **Trigger:** New code, dataset, model, document, media, generated output, package, or external asset. **Run:** Verify ownership, permitted use, training and output rights, open-source obligations, attribution, redistribution, derivative-work limits, and contractual restrictions. **Output:** Approved use, required attribution, remediation, or blocked asset.                       | Every asset intake and release                     |
| 108 | **Workforce Skills and Operating Model Readiness Loop** | **Trigger:** Technology, process, product, role, or automation change. **Run:** Assess required roles, competencies, capacity, separation of duties, decision rights, training, support model, and standard procedures; close gaps and verify readiness through exercises or assessments. **Output:** Workforce-readiness score, training plan, role changes, and operating-model actions.   | Quarterly or annual                                |

---

# Important Boundaries Between Similar Loops

The following loops are related but are not duplicates.

| Loops                                                                                            | Boundary                                                                                                                                                                                          |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Incident Management** and **Problem Management**                                               | Incident management restores service. Problem management removes the systemic cause of repeated incidents.                                                                                        |
| **Incident Management** and **AI Incident Response**                                             | The general loop manages service disruption. The AI-specific loop handles model, prompt, retrieval, agent, tool, or autonomous-action evidence and containment.                                   |
| **Software Dependency and Package Management** and **Software Supply-Chain and Build Integrity** | Dependency management selects, updates, and validates packages. Supply-chain integrity proves that source, dependencies, builds, and artifacts are authentic and untampered.                      |
| **AI Supply-Chain Security** and **Vendor and Third-Party Risk**                                 | AI supply-chain security evaluates AI components and technical dependencies. Vendor risk covers the broader organization, contract, resilience, concentration, and SLA relationship.              |
| **AI Safety and Responsible AI** and **Model and Agent Interaction Security**                    | Responsible AI covers harm, fairness, privacy, transparency, and human impact. Interaction security covers adversarial compromise such as injection, poisoning, exfiltration, and tool hijacking. |
| **Agent Guardrail** and **Capability-Based Governance**                                          | Guardrails enforce policy during each runtime action. Capability governance defines the control tier that determines which policies must exist.                                                   |
| **Agent Autonomy Calibration** and **Autonomy Boundary Review**                                  | Calibration decides the general autonomy level. Boundary review checks the exact systems, data, actions, and permissions available to the agent.                                                  |
| **Model Evaluation and Benchmarking** and **Model and Data Drift Monitoring**                    | Evaluation compares models and configurations using controlled datasets. Drift monitoring detects production changes over time.                                                                   |
| **Release Readiness** and **Operational Readiness**                                              | Release readiness decides whether a particular version can ship. Operational readiness decides whether the organization can support the product in production.                                    |
| **Technical Debt** and **Application Modernization**                                             | Technical debt handles local maintainability and changeability problems. Modernization addresses broader platform, technology, or architecture replacement.                                       |
| **Product Obsolescence Detection** and **Capability Absorption**                                 | Obsolescence examines whether the product’s market value is disappearing. Capability absorption removes internal components made unnecessary by stronger models.                                  |
| **Rollback, Backup and Recovery** and **Business Continuity**                                    | Rollback and recovery restore technology and data. Business continuity keeps critical business operations functioning during prolonged disruption.                                                |

---

# Standard Skill Contract for Each Loop

Use the same implementation contract for all 108 skills.

```yaml
skill_id: unique-stable-id
name: loop-name
category: one-of-13-categories

purpose:
  outcome_to_improve: measurable outcome
  scope: systems, products, users, or processes covered
  exclusions: responsibilities owned by adjacent loops

triggers:
  event_triggers: []
  scheduled_trigger: ""
  threshold_triggers: []

inputs:
  required: []
  optional: []
  authoritative_sources: []

preconditions:
  permissions_required: []
  minimum_data_required: []
  dependency_checks: []

execution:
  - observe_current_state
  - assess_against_policy_and_thresholds
  - classify_findings
  - select_action
  - execute_or_recommend
  - validate_result
  - record_evidence
  - learn_and_update_tests

decisions:
  allowed_outcomes:
    - pass
    - pass_with_conditions
    - remediate
    - escalate
    - block
    - stop
  approval_authority: ""
  decision_rules: []

outputs:
  primary_artifact: ""
  machine_readable_result: ""
  human_readable_summary: ""
  downstream_events: []

quality_controls:
  acceptance_thresholds: []
  validation_checks: []
  false_positive_controls: []
  false_negative_controls: []

safety_and_governance:
  prohibited_actions: []
  data_handling_rules: []
  human_approval_points: []
  audit_requirements: []

recovery:
  retry_limit: 0
  retry_conditions: []
  rollback_or_compensation: []
  escalation_path: []

metrics:
  effectiveness: []
  efficiency: []
  risk: []
  trend: []

evidence:
  logs: []
  reports: []
  approvals: []
  retention_period: ""

ownership:
  business_owner: ""
  technical_owner: ""
  control_owner: ""

cadence:
  minimum_frequency: ""
  review_frequency: ""
```

For implementation, every skill should return a common result envelope:

```json
{
  "loop_id": "unique-loop-id",
  "execution_id": "unique-execution-id",
  "trigger": "event-or-schedule",
  "status": "pass | conditional | remediate | escalate | block | failed",
  "findings": [],
  "actions_taken": [],
  "actions_required": [],
  "evidence": [],
  "metrics": {},
  "owner": "",
  "next_execution": "",
  "timestamp": ""
}
```

This common structure allows the 108 skills to be orchestrated, audited, measured, and connected into larger SDLC, AI, and agentic-AI workflows.

