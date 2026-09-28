# Assurance report contract

Use this complete contract for a comprehensive run. Keep empty sections and explain why they are empty. Cross-reference stable IDs instead of repeating technical detail.

## 1. Decision summary

Application, run, build, environment, scope, requested decision, recommended exposure, evidence strength, blockers, conditions, business decision, and acceptance authority.

## 2. Six-dimension executive scorecard

All six lenses with evidence-qualified verdicts, optional rubric-based scores, blockers, and next decisions.

## 3. Scope, evidence, and completeness

Artifact inventory; missing, stale, and contradictory evidence; coverage numerators and denominators; included and excluded journeys; assumptions; and unavailable access or execution.

## 4. Twenty-layer maturity diagnosis

All layers with applicability, evidence, finding IDs, release effect, and target-state changes.

## 5. Master gap and risk register

Every substantiated finding and material evidence gap, prioritized and deduplicated. Keep hypotheses separate from confirmed defects.

## 6. Detailed remediation packages

Full packages for Critical and High findings and release-blocking evidence gaps. Give sufficient implementation and acceptance detail for every other actionable gap.

## 7. Dependency-ordered implementation plan

Containment, diagnostics/evidence, prerequisite controls, blocking repairs, regressions, operational proof, and later improvements. Include owner, target, dependency, effort assumptions, and definition of done. Treat 30/60/90-day horizons as planning buckets unless capacity and dates are supplied.

## 8. Test and verification matrix

```text
Test ID | Finding/control | Build/environment | Preconditions/fixture | Action | Expected result | Actual result | Pass/fail/not run | Evidence | Verifier
```

Keep proposed tests visibly distinct from executed tests. Include nonfunctional and recovery tests when required.

## 9. Release gates, exceptions, and recovery

Go/no-go/hold/conditional decision; non-waivable blockers; accepted risk; approvers; restrictions; expiry; monitoring; rollout; rollback; compensation; irreversible effects.

## 10. Product, value, and future-resilience decisions

Acquisition posture and valuation limits; value drivers and destroyers; moat evidence; comparison experiments; stop/double-down decisions; integration plan if relevant; future scenarios; immediate and deferred investments.

## 11. Change since previous run

New, unchanged, implemented, verification-pending, closed, rejected, reopened, and expired findings. Explain evidence-driven severity or decision changes.

## 12. Immediate action queue and continuation state

First executable actions in dependency order; exact artifact or approval for blocked items; next test; next decision owner; next trigger; and whether the run ended, handed off, or stopped incomplete.

## Quality gate

Before delivery verify that:

- every material claim is supported or labeled as inference, hypothesis, or missing evidence;
- every blocker has a stable finding ID, diagnostic or repair package, and acceptance-proof requirement;
- proposed locations are real or explicitly unknown;
- executed tests contain actual results for the correct build and environment, while unexecuted tests say `Not run`;
- severity, confidence, priority, and lifecycle status remain distinct;
- scores and positive summaries do not override blockers;
- owners, dates, finances, metrics, and evidence are not fabricated;
- all six lenses and twenty layers are covered or explicitly unassessed/not applicable with reasons;
- Critical and High findings are not hidden to shorten the report;
- secrets and personal data are protected;
- closure evidence, residual risk, dependencies, recovery limits, and next triggers are explicit;
- claims of independence, deployment, certification, valuation, universal safety, or future resilience stay within evidence.

## Optional durable outputs

When file creation helps and the environment supports it:

```text
<application_id>/<run_id>/assurance-report.md
<application_id>/<run_id>/evidence-ledger.json
<application_id>/<run_id>/findings.json
<application_id>/<run_id>/remediation-plan.md
<application_id>/<run_id>/verification-matrix.csv
<application_id>/<run_id>/continuation-state.json
```

These are suggested paths, not evidence that files exist. A single Markdown report is sufficient when separate artifacts add no value.
