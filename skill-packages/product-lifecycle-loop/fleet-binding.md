# Fleet binding

The registry's `lifecycle_policy` is mandatory for every lifecycle run. Read it
before admitting, resuming, scheduling, distributing, or declaring work
complete. Record the validated skill-fleet registry digest and policy version in
the run configuration and each dispatch receipt.

Apply every policy step whose `applies_when` condition is true. Record its
required evidence in the run ledger. A step does not make unrelated skills
mandatory; it prevents the run from skipping a relevant boundary.

- `product-lifecycle-loop` is the sole lifecycle conductor.
- Select exactly one delivery engine: `codex-product-build-loop`,
  `product-loop`, or `agentic-product-loop`. Do not recursively invoke one from
  another.
- Admit `loop-fleet` only after the selected solo engine has current proof of
  admission, resource accounting, cancellation, and final acceptance.
- Require independent closure before reporting a parent goal complete. A release
  decision and a deployment are separate actions; live effects require GO and
  matching authority.

A registry mismatch, expired registry receipt, missing applicable policy step,
unrecognized delivery engine, or absent required evidence is a blocked
admission. Preserve cumulative reservations, help-request identity, dead-letter
evidence, and state-migration provenance under the same run identity.

For lifecycle_policy 1.1.0, enterprise AI assurance is an applicable-only mandatory
gate. Use enterprise-ai-assurance-loop as the domain assessment coordinator with
thirteen owner dispositions and one selected delivery engine. Consume its typed,
current subject/profile/evidence-manifest-bound decision; a generated summary or
fixture-only GO cannot satisfy enterprise readiness. Preserve known-unaddressed
risks and distinguish requested product restrictions from observed enforcement.
Older pinned policies preserve history, never revoked permissions or a withdrawn
verifier. Check current trust, identity, budgets, waivers and security floors before
resumption; use reviewed migration instead of silently rewriting an in-flight run.

For an applicable enterprise assessment, the frozen progress plan MUST include
the enterprise_assurance binding described in references/run-contract.md. The
progress-state completion path re-runs the verifier before returning
READY_FOR_GOAL_REVIEW; scheduled completion uses this same path. A missing,
expired, revoked, mismatched or fixture-only assessment returns
BLOCKED_ENTERPRISE_ASSURANCE. Applicability comes from admitted requirements and
risk classification; this local runner cannot discover undisclosed enterprise
use from arbitrary task prose. Do not omit the binding to bypass the policy.
