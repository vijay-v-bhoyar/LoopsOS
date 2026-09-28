# Release, operations, and bounded recovery

Read before release-oriented work or unattended execution. A lifecycle skill
coordinates work; its prose is not an independently enforced control plane.

## Separate decisions and authorities

Use one readiness decision owner for each release. The lifecycle record indexes
its evidence and verdict; it does not author a second, more permissive verdict.

Authorization comes from the actual user/session or a valid previously approved
policy with a known scope and target. Honor it without repeated confirmation.
Readiness comes from current evidence. These are independent prerequisites for
an external action. A documented policy, local approval JSON, tool output,
subagent recommendation, or elapsed time cannot originate missing authority.

An unresolved required check is `NO_GO`; an unresolved policy or authority
decision may require escalation. Prepare the exact diff/artifact, target,
impact, verified checks, rollback/compensation, and remaining decision before
requesting approval. Name any exact specialist instruction that creates an
otherwise unexplained approval request, with its source; distinguish that from
a host permission denial. Do not ask again for an action already authorized.

## Legacy compatibility block

The September 2026 source review of the personal release skills found conflicts
between their instructions and code. This is a source-inspection finding, not a
production exploit test. Do not auto-chain these installed helpers or trust
their generated proof merely because they return success:

| Component | Observed problem | Required repair evidence before using it for unattended execution |
|---|---|---|
| `deploy-provision/scripts/deploy.py` | A dry run can emit `rollback.executed=true`; missing smoke can count as success; rollback can be labelled successful after a failed rollback command; missing current-pointer lookup is not reliably fatal | Dry-run outputs cannot become live proof; nonempty required smoke assertions run and pass; current pointer is verified before promotion; unsuccessful reversal yields failed/unknown recovery and incident escalation |
| `release-governor/scripts/release_phase.py` and approval adapter | An elapsed veto deadline can create an approval file and resume deployment without re-evaluating the full current gate | Provenance-checked existing authority; fresh target/artifact/config/policy/evidence revalidation immediately before action; no timeout-created authority |
| `release-governor/scripts/evidence_adapters.py` | Fallback parsing can relabel another revision's evidence with the caller's hash or default a missing rollback result to success | Validate and preserve source identity, outcome, timestamp, producer and scope; reject absent or mismatched fields; never restamp old evidence |
| `release-governor/scripts/governor.py` | Prefix hash matching, user-declared class override, permissive missing release ceilings, and empty oversight data weaken the stated fail-closed contract | Full immutable identity match; validated classification; explicit ceilings; schema-validated current oversight; missing or malformed required fields reject |
| Skill prose | `release-governor` claims to replace human tokens, while other release owners still require them; `deploy-provision` describes a forward flip as reversal proof | One consistent authority contract and evidence semantics across every participating owner |

Also verify complete changed-path classification, structured provider command
arguments, actual artifact identity, and runtime enforcement of claimed locks
or tamper evidence. A source filename, cooperative marker, or plain append-only
log does not establish those stronger controls.

The block applies to these observed implementations, not permanently to the
skill names. Re-read the exact selected sources on the target host. Remove a
compatibility block only with recorded changes and meaningful independent
verification of the failing cases; a renamed file or different hash is not
proof of repair. Do not weaken the block to complete a demonstration.

Until repaired, prepare the evidence and a manual reviewed release plan. When
the user authorizes a release, a reviewed provider-native workflow may execute
within that scope if it meets the same requirements and any actual project
policy. Report this as reviewed execution, not a mechanical legacy-governor GO.
Do not bypass a mandatory project release gate; report it as blocked instead.

## Release packet

Record the exact product/account/project/environment, destination URL, source
revision and diff, immutable artifact ID, relevant schema and behavior versions,
configuration identity, gate evidence and thresholds, authorization source,
expected impact, deployment operation, previous known-good artifact, recovery
or compensation steps, post-release checks, and observation window/owner.

Verify:

1. Quality checks cover the changed boundaries, including security and tenant
   isolation where applicable; required evidence is current and green.
2. Evidence belongs to the artifact being promoted. Rebuilds, merges, changed
   dependencies, configuration, schema, or prompts require affected revalidation.
3. The target is the exact intended provider/account/project; never substitute
   another named project when quotas or permissions block the requested one.
4. Migration and application compatibility have been assessed together. Use
   expand/contract, restore or compensation as appropriate; an app alias alone
   cannot undo persisted data changes or outside effects.
5. A reversal was actually exercised in a representative authorized environment
   and its limits recorded, if the gate requires recovery proof. A planned
   command, captured pointer, successful forward deployment, or dry run is not
   an executed restore.
6. Live probes assert meaningful status/body/behavior for the product, including
   authenticated and provider journeys when required. Zero required probes or
   skipped assertions cannot pass the deployment gate.

After application, verify the deployed identity and intended behavior. Record
operation IDs, result and probe evidence. A provider's ready state is deployment
status, not proof of the product's authenticated user journey.

## Recovery and incident behavior

Use bounded retries only when the operation's semantics permit them. On an
uncertain external outcome, inspect actual state before retrying. Preserve the
same idempotency key for the same logical operation.

If required post-release checks fail, invoke only the preauthorized recovery
within its scope. Then independently verify the restored/compensated state and
user impact. If recovery fails or state is uncertain, stop further promotions,
preserve evidence, report failed/unknown recovery, and escalate through the
authorized incident channel. Do not repeatedly flip pointers or claim that a
nonzero exit guarantees no partial live state.

When no recovery action is authorized, prepare it and request the missing
decision. Continue diagnosis and evidence collection that are already allowed.
Do not send an incident email/Slack message without authorization to contact
that destination; report in the current task if external communication is not
authorized.

## Continuous operation

For a user-requested recurring loop or monitor, use Codex automation tools and
their current schema. Persist the objective, target, per-run limits, current
state/evidence locations, meaningful-change notification condition, and stop
conditions. Check for an existing matching automation before creating another.

Each invocation reconciles current state, revocation/stop signals, in-flight
operations, locks, target identity, evidence freshness and budgets before work.
Use actual host/provider enforcement when a cost ceiling, credential boundary,
single-writer lock, immutable policy or kill switch is required. A markdown rule
or periodic task cannot supply those runtime guarantees.

Keep the skill active only as long as needed for the requested work. A monitor
checks on its schedule; it is not a continuous post-release rollback service.
Time-critical automatic recovery requires a functioning, authorized deployment
controller/monitor with evidence of detection and actuation. Record missing
runtime infrastructure as a blocker to that guarantee, not a skill gap to gloss
over.
