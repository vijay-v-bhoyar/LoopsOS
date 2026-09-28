# Evidence, findings, and remediation

## Evidence states

| State | Meaning | Handling |
|---|---|---|
| Observed fact | Directly visible in an artifact | State only what the artifact proves |
| Reproduced failure | An authorized test demonstrated behavior | Record procedure, output, build, and environment |
| Supported inference | Evidence supports but does not directly prove the conclusion | Explain reasoning and a discriminating test |
| Hypothesis | Plausible but undemonstrated failure path | Keep separate from confirmed defects |
| Evidence missing | Relevant state cannot be established | Name the exact artifact or test needed |
| Contradictory evidence | Sources materially disagree | Preserve both and resolve scope/version before a positive claim |
| Not applicable | Exposure is genuinely outside scope | Record evidence, rationale, and approver status |

Missing evidence proves neither failure nor control effectiveness. Record potential impact separately from confidence.

## Finding model

Types: `Confirmed defect`, `Evidence gap`, `Design risk`, `Operational gap`, `Product/value gap`, `Improvement opportunity`, or `Rejected candidate`.

Keep these fields separate:

```text
Finding ID | Type | Title/root cause | Evidence state | Evidence IDs | Affected journeys/layers/dimensions/apps | Severity or potential impact | Confidence basis | Priority | Status | Release consequence | Owner | Fix package ID | Test IDs | Dependencies | Residual risk | Acceptance/expiry | First seen | Last changed
```

Use stable IDs across runs. Shared-component defects can have one parent finding with per-application exposure and verification records.

## Severity and priority

| Severity | Interpretation | Default decision effect |
|---|---|---|
| Critical | Substantiated severe harm, confidential cross-boundary exposure, unauthorized high-impact action, critical integrity loss, or intolerable critical-journey failure | Block affected beta and production scope |
| High | Major security, reliability, safety, or operational weakness without an adequate verified control | Block affected scope until repaired or valid time-limited treatment satisfies policy |
| Medium | Material issue with limited exposure and a workable verified mitigation | Conditional release only with owner, monitoring, and plan |
| Low | Minor friction, polish, or low-impact documentation/operations gap | Backlog unless a stated requirement makes it blocking |

For evidence gaps, record potential impact rather than asserting exploitability. Stricter legal, contractual, product, or organizational rules prevail.

Priorities:

- `P0`: active harm, exposed secrets, uncontrolled unsafe actions, or urgent containment.
- `P1`: release blockers, mandatory evidence gaps, and prerequisites that unlock multiple repairs.
- `P2`: significant quality, reliability, adoption, or cost improvements.
- `P3`: strategic experiments, later hardening, and polish.

Do not manufacture numeric risk precision or delivery estimates.

## Finding lifecycle

```text
Candidate -> Substantiated -> Planned -> Implemented -> Verification pending -> Closed verified
```

Alternate states: `Evidence pending`, `Blocked`, `Mitigated pending permanent fix`, `Risk accepted until expiry`, `Reopened`, `Rejected with evidence`, `Duplicate`, or `Closed by verified scope removal`.

A mitigation is not a durable repair. Risk acceptance is not successful verification. Scope removal closes only the proven removed exposure.

## Remediation package

Create this for each actionable gap. Fully specify Critical, High, and release-blocking evidence gaps.

```text
Finding ID and title:
Type, evidence state, severity or potential impact, priority:
Application, build, environment, journeys, layers:

1. Problem
   Observed behavior:
   Required behavior:
   Evidence and locator:
   Consequence and affected scope:

2. Diagnosis
   Root cause:
   Confidence and alternatives:
   Missing evidence or discriminating diagnostic:
   Why existing controls are insufficient:

3. Immediate treatment
   Containment or temporary mitigation:
   Limits, approvals, and side effects:

4. Durable repair
   Target component and verified locations:
   Dependency-ordered implementation steps:
   Data/schema/API/policy/prompt/infrastructure changes:
   Permissions, UX, migration, backfill, and compatibility:
   Minimal safe repair versus longer-term improvement:
   Explicit exclusions:

5. Delivery
   Owner or Owner unknown:
   Suggested role, clearly labeled:
   Release target or Release target unknown:
   Dependencies, effort assumptions, and implementation risks:

6. Verification
   Test IDs, fixtures, reproduction, positive, negative, abuse, failure, and regression cases:
   Expected observable results and approved thresholds:
   Actual results only after execution:
   Independent verifier or independence limitation:

7. Release and recovery
   Rollout sequence, exposure limits, monitoring, and abort criteria:
   Rollback or compensation procedure:
   Irreversible effects and recovery owner:

8. Closure
   Required evidence bundle:
   Acceptance authority:
   Residual risk and expiry/reassessment trigger:
   Definition of done:
```

When code is unavailable, use stack-neutral component steps and state `Exact file/function location unknown`. When diagnosis is uncertain, make diagnosis the first work item.
