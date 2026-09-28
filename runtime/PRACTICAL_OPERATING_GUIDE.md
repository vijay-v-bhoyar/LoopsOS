# LoopsOS Practical Operating Guide

## What This System Is For

LoopsOS is a system of smaller connected improvement loops. Each loop owns one outcome, gathers evidence, identifies gaps, applies bounded fixes, validates results, records learning, and monitors whether the improvement actually worked.

The practical unit is not the whole SDLC. The practical unit is one loop execution with one owner, one scope, one evidence packet, one verdict, and one effectiveness check.

## Ten-Minute Start

1. Choose one high-impact playbook from `runtime/pilot_playbooks.yaml`.
2. Open the selected loop descriptors under `runtime/loop-descriptors/`.
3. Resolve the policy owner, gate owner, risk owner, executor, validator, and backup owner in `owners/OWNER_REGISTRY.yaml`.
4. Resolve authoritative evidence locations in `evidence/EVIDENCE_LOCATION_REGISTRY.yaml`.
5. Open the matching operation cards in `runtime/practical_operation_cards.yaml`.
6. Run `python scripts\validate_loop_corpus.py`.
7. Run `python scripts\audit_loop_practicality.py`.
8. Execute one real loop event and store a result envelope that includes `loop_id`, `execution_id`, `correlation_id`, `risk_tier`, authority, state, evidence, verdict, and timestamp.
9. Validate immediate correctness.
10. Monitor effectiveness through the loop's cadence window before standardizing the change.

## Recommended Pilot Order

Start with the playbooks that save the most coordination effort:

1. Validator-backed SDLC governance operating system.
2. Evidence-backed release and deployment command center.
3. Agentic action safety control plane.
4. AI model lifecycle and evaluation flywheel.
5. Audit-ready compliance evidence autopackager.
6. Incident-to-prevention learning flywheel.

## Promotion Rules

Use `DRAFT` while a loop is documented but not bound to real owners, evidence, probes, and metrics.

Use `PILOT` when:

- owners are named for the pilot scope,
- evidence locations are authoritative for the pilot scope,
- metric targets are defined,
- probes or manual proof steps are executable,
- human handoffs are known,
- at least one golden task has a real fixture.

Use `ACTIVE` only when:

- proof has passed,
- effectiveness has been monitored,
- exceptions expire,
- state transitions are recorded,
- evidence is retained,
- repeated failures route to the graph instead of staying local.

## Human Handoff Rules

Handoff is required before irreversible consequence, privileged access, external effect, or uncertain proof.

Use `runtime/human_handoffs.yaml` for the authoritative handoff rules. The highest-priority handoffs are:

- missing authority,
- missing evidence source,
- R3 or R4 execution,
- destructive or customer-visible action,
- expired conditional approval,
- security, privacy, compliance, forensic, or supply-chain failure.

## Evidence Packet

A useful evidence packet contains:

- trigger record,
- scope and asset,
- current observation,
- diagnosis,
- control applicability,
- owner and authorization verdict,
- action record,
- validation result,
- proof result,
- effectiveness metric,
- learning or standard update.

## Practical Rule

Never treat `ACTION_APPLIED` as `EFFECTIVENESS_PROVEN`.

A change is not done when the fix is applied. It is done when the loop has proof, the proof survives the observation window, and the standard or baseline is updated.
