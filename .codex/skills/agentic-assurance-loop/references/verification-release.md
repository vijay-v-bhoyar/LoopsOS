# Verification, release gates, and learning

## Verification sequence

1. Confirm the artifact, build, configuration, model, prompt, policy, retrieval, tool versions, and environment under test.
2. Run the original reproduction or diagnostic when safe; record why a pre-fix reproduction was unavailable.
3. Run acceptance tests that demonstrate required behavior after repair.
4. Run adjacent negative, adversarial, permission, concurrency, replay, retry, interruption, and failure cases.
5. Recheck critical journeys and applicable quality, cost, latency, privacy, accessibility, and operational targets.
6. Inspect deployment configuration, telemetry, alerting, rollback, compensation, and recovery evidence when applicable.
7. Record actual output, verifier, timestamp, residual exposure, and acceptance decision.

A repository test is not evidence that it ran. A green result for another build or environment does not prove the current release. Do not remove failing cases or change thresholds during verification.

For stochastic behavior, record dataset and version, case distribution, sample count, repeat policy, evaluator method, failures, and uncertainty. Finite testing cannot establish a universal zero failure rate.

## Closure

Mark a finding `Closed verified` only when required implementation, configuration, acceptance, regression, operational evidence, and residual-risk acceptance are complete for the defined scope.

Keep implementation completion separate from production effectiveness. If post-deployment observation is pending, leave effectiveness pending. A failed verification reopens the same stable finding ID and returns to diagnosis within the authorized attempt limit.

## Decision gates

Produce technical-exposure and business-investment decisions separately.

- `No-go`: a Critical blocker, active uncontrolled exposure, failed mandatory control, missing mandatory proof, or unapproved non-waivable requirement affects scope.
- `Hold for evidence`: relevant facts cannot be established; name the exact artifact or test that can change the decision.
- `Conditional go`: policy permits the residual risk; compensating controls are verified; exposure is bounded; the responsible authority accepts it; owners, monitoring, expiry, and recovery are recorded.
- `Go for assessed scope`: mandatory controls and tests pass for the exact release; prohibited blockers are absent; operating ownership and recovery are evidenced; designated authority approves.

An assessor cannot waive Critical exposure. Scores and positive narratives cannot override gates. A conditional decision expires when evidence, scope, controls, or acceptance expires.

## Scorecard

Use six dimensions:

1. Beta Readiness
2. Enterprise Maturity
3. Security and Safety
4. Value and Acquisition Strength
5. Category Potential
6. Future Resilience

Columns:

```text
Dimension | Scoped verdict | Score or Not scored | Evidence strength | Coverage | Blocking finding IDs | Decision needed
```

Use qualitative evidence strength: `Direct/reproduced`, `Supported but incomplete`, or `Insufficient`.

Optional 1–5 readiness scoring requires a declared rubric:

- 1: materially deficient under observed conditions.
- 2: partial controls with material gaps.
- 3: evidenced suitability for a bounded beta.
- 4: evidenced suitability for intended production scope.
- 5: sustained operational evidence with tested recovery and change management.

For value and category, use a separate rubric from unvalidated proposition through sustained durable advantage. Use `Not scored` when material commercial evidence is missing. Future-resilience scores apply only to named tested scenarios.

## Monitoring and next run

Define applicable signals such as task success/failure, unsupported outputs, denied actions, approval bypass attempts, retrieval or permission failures, escalation, latency, retries, cost per successful task, alert response, corrections, and reopened findings.

Assign source, owner, approved threshold, interval, and response. Proposed thresholds must be labeled and accepted before becoming gates.

Trigger reassessment after relevant code, model, prompt, policy, tool, permission, dependency, retrieval, data, configuration, architecture, or release changes; incidents; adverse feedback; failed service targets; expired exceptions; or expired evidence.

For changed-surface runs, reassess affected controls and dependencies and reuse only valid unchanged evidence. Rebaseline the full scope after major architectural or trust-boundary changes.
