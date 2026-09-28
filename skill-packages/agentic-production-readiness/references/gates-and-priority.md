# Readiness gates and priority

## Severity

Assign severity from demonstrated or credibly supported impact, not gate number.

### Blocker

- The critical path cannot run.
- Data can be lost.
- One user or tenant can access or affect another's data, retrieved context, or agent memory.
- Tools can take unauthorized or unsafe actions.
- Tool loops, recursion, retries, delegation, or spending are unbounded.
- Another demonstrated failure makes the intended release unsafe or unusable.

Unbounded tool loops are a Gate 5 Blocker.

### Major

- Important agent behavior cannot be evaluated.
- Failures cannot be detected or investigated.
- Cost or rate limits are materially inadequate.
- Recovery or another material operational requirement remains unverified.

### Minor

Polish or documentation issues without material safety, reliability, or release impact.

State uncertainty explicitly. An evidence gap does not by itself prove exploitability, but missing mandatory proof can block the intended release.

## Twelve gates

1. **Critical path:** boots and runs locally, including relevant failure and retry behavior.
2. **Identity and isolation:** authentication, authorization, and separation of user data, retrieved context, and agent memory.
3. **Secrets and configuration:** source exposure and safe handling of missing, invalid, or rotated configuration.
4. **Untrusted input:** prompt injection, retrieval trust boundaries, parser boundaries, and tool allowlists.
5. **Consequential execution:** read-only defaults, explicit authorization, irreversible-action confirmation, and caps on tools, loops, recursion, delegation, retries, time, and spend.
6. **Agent evaluations:** applicable happy path, refusal, injection, wrong-tool, timeout, cancellation, and duplicate-submission behavior.
7. **Failure resilience:** timeouts, idempotency, partial failure, safe retry, provider outage, cancellation, and uncertain outcomes.
8. **Tracing and audit:** correlated model/tool calls and user-visible errors with sensitive-data redaction.
9. **Limits and shutdown:** enforced user, tenant, and system cost/rate limits plus a working disable or kill mechanism.
10. **Persistent state:** safe migrations, retention/deletion, backup, restore, and demonstrated recovery where applicable.
11. **Repository checks:** lint, types, tests, build, and other required project checks using the repository's commands.
12. **Operations:** one documented local boot command and a concrete verified recovery procedure.

For each slice record the asset, trust boundary, failure or abuse case, control, supporting test/procedure, and what that evidence does not establish.

## Applicability constraints

- Gates 1 and 3 cannot be `N/A`.
- Gates 4 and 5 cannot be `N/A` when the application calls a model or tool.
- Gate 6 cannot be `N/A` when agent behavior is on the critical path.
- Gate 2 may be `N/A` only after the user explicitly chooses single-operator localhost, the repository has no user or shared-user boundary, and remaining local access risks are documented. Never use this as a shortcut around an existing multi-user design.

## Ordering

1. If the critical path is broken, prioritize a boot repair and characterization test unless executing it would create a more immediate safety risk.
2. Otherwise choose the next open Blocker, then the next Major; use gate number to break ties.
3. Present a prerequisite before a dependent slice.
4. Keep skipped blockers visible. Re-present one only when a later slice depends on it or the user requests reconsideration.
5. When only external evidence, a missing fact, or deferred choices remain for Blockers and Majors, recommend `STOP` for the local session.
6. If no actionable Blockers or Majors remain, recommend `STOP`. Continue Minor work only if the user chooses it.
