# Finding history and independent closure

For a reproduced defect, maintain one `.loop/findings/<finding-id>/record.json` across repair attempts. Preserve the stable finding ID and parent criteria. This supplements the finding register; it does not replace coverage, risk acceptance, evidence gaps or release governance.

Read [evidence-format.md](evidence-format.md) for CLI and receipts. Use `scripts/finding_ledger.py`. Exact top-level fields:

```text
id, parent_goal: stable nonempty IDs
criteria: nonempty accepted closure criterion IDs
mode: ASSESS_AND_PLAN | VERIFY_APPROVED_SANDBOX | REMEDIATE_APPROVED_SCOPE
owner: named acceptance owner
require_independent: boolean fixed by the parent risk policy
events: ordered list
```

| kind | Additional fields |
|---|---|
| reproduction | receipt (nonzero check exit), cause, confidence (hypothesis/supported/confirmed) |
| repair | owner, changes (artifact references), rationale |
| verify | criteria, original (receipt), regression (receipt), acceptance (artifact), acceptance_owner, residual_risk |
| help | owner, question, needs, wake_condition |

Imported reproduction evidence can be assessed without running it. Recording a newly executed repair requires `REMEDIATE_APPROVED_SCOPE`; assessment mode cannot append repair or verification events. No helper operation executes a product repair or test. The caller still checks actual user authorization before any application action. A verification-only request for an already implemented change uses the broader assurance register; do not relabel it remediation merely to use this defect-repair helper.

Keep original source and oracle snapshots. New reproduction records must retain the original oracle; repair resets prior closure readiness. Both current verification receipts must cover the changed artifacts and exact accepted criteria, and the original check retains its oracle. If independence is required, verifier names must differ from the repair owner. Named separation is a structural check, not identity authentication: the parent verifies who actually performed the work and discloses shared context or other independence limits.

`CLOSURE_REVIEW_READY` returns `closed: false` and `authority: none`. It proves the local record has coherent, current bindings. Before marking `Closed verified`, the responsible verifier inspects direct outputs, repair diff, all required acceptance and operational evidence, residual exposure and valid acceptance authority. Omitted applicable controls stay in the coverage denominator. A forged assertion count or output can satisfy structure but cannot establish behavior; direct review is required.

Changed subject or expired evidence returns `FINDING_OPEN`; historical events remain. A failed retest can append another reproduction under the same finding ID and return to the bounded delivery owner. The parent retains aggregate retry/spend limits and routes help packets; report completion never closes an unresolved finding.

Run `python -B scripts/test_owner_ledger.py` after changes. The suite executes local positive/negative probes, validates restart persistence, and rejects self-verification when independence is required, assessment-mode repair, changed original oracles, incomplete criteria and omitted changed artifacts.
