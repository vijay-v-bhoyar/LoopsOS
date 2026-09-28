# State and evidence contract

Use one durable readiness document per application scope. Prefer an existing state file; otherwise adapt `assets/production-readiness.template.md` and default to `docs/production-readiness.md`.

## Required sections

1. Critical path and target environment.
2. Stack constraints.
3. Scorecard.
4. Backlog and dependencies.
5. Decision log.
6. Assumptions.
7. Verified versus untested evidence.

Keep the file concise but preserve history. Do not erase an earlier failure, rejected option, deferral, or approval when updating current state.

## Evidence binding

For each gate or verification record capture:

```text
Evidence ID | Gate | Claim | Source revision or working-tree identity | Configuration identity | Environment | Command/procedure | Date | Actual result | Limits/unknowns
```

Use a commit SHA when it accurately identifies the tested source. For dirty or uncommitted work, record the branch, HEAD, relevant changed paths, and a stable diff or artifact digest when available. Do not call an uncommitted tree a commit.

Reassess evidence after relevant code, configuration, model, prompt, tool, retrieval, dependency, data, or deployment changes. A result for another build or environment is context, not current proof.

## Gate statuses

| Status | Meaning |
|---|---|
| `UNASSESSED` | Inspection is insufficient to judge the gate. |
| `OPEN` | An applicable acceptance criterion is unmet. |
| `LOCAL_VERIFIED` | Applicable local criteria passed; broader readiness remains unestablished. |
| `EXTERNAL_EVIDENCE_REQUIRED` | Provider, hosted, deployment, restore, or operational proof is required and unavailable here. |
| `CLOSED` | Every applicable criterion is evidenced for the explicitly named target environment. |
| `N/A` | Genuinely inapplicable, with a one-line evidence-based reason. |

For every gate record severity, concrete acceptance criteria, status, evidence and environment, remaining limits and dependencies, and whether the user deferred it.

Local tests support local claims. Mocked tests support simulated behavior only. Neither establishes hosted authorization, provider behavior, real recovery, or deployment readiness.

## Initial inspection output

On the first run, produce:

- scoped application and critical path;
- target environment or `Unknown`;
- current source/working-tree identity;
- actual repository commands and their side-effect risks;
- twelve-gate scorecard;
- dependency-ordered Blocker/Major backlog;
- assumptions and one necessary blocking fact, if any;
- first decision card.

Do not implement the first option during initialization.
