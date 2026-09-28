# Run and handoff contracts

Use this for material lifecycle work, especially when work spans tasks, agents,
or external systems. Reuse established project records. If none exist, a compact
`.loop/runs/<run-id>.md` is enough; the fields below are a record shape, not a
requirement to create an empty folder of documents before useful work.

## Run record

Record:

- Run ID and timestamp; product/repository, branch and current working state.
- Mode, requested outcome, acceptance criteria, scope, constraints, and non-goals.
- Current stage and selected work; IDs or links to existing vision/backlog items.
- Decisions already provided by the user, material assumptions, and open inputs.
- Selected conductor and specialist roles with exact resolved skill paths and
  content hashes; tool availability and any substitutions or compatibility gaps.
- Validated skill-fleet registry digest, `lifecycle_policy` version, selected
  delivery engine, and one evidence-ledger row for each applicable mandatory
  policy step. An inapplicable step records the scope reason; it is never
  silently omitted.
- Authorized actions with the source of authorization, exact target, environment,
  scope, limits, and expiry/revocation terms if present. An agent-authored record
  is an index to authority, never a new grant.
- Ownership: current writer, delegated file/surface boundaries, integration owner.
- Resource limits actually available, maximum work per run, stop/recovery rules.
- Evidence ledger and the next action or reason an action cannot proceed.

Keep secrets out of run records. Store redacted configuration identity or a
non-secret fingerprint rather than credentials or raw customer data.

## Specialist handoff

When enterprise AI assurance applies under lifecycle_policy 1.1.0, retain the
enterprise run ID, immutable subject/profile/verifier identities, complete owner
applicability matrix, signed evidence manifest, independent challenge, risk and
waiver snapshot, and scoped decision expiry. The enterprise loop is an assessment
child; the lifecycle conductor retains the product goal and exactly one delivery
engine. Local fixture results do not establish enterprise evidence or deployment
permission. The typed evaluator in the registered enterprise package must verify
the current decision before parent acceptance; evidence and risk changes require
fresh challenge. Report unresolved product acceptance separately from a completed
assessment report.

Give each specialist the outcome, bounded scope, authoritative inputs, exact
files or resources it may change, relevant constraints, acceptance criteria,
side-effect permissions, and expected evidence. Include the active conductor
identity so the specialist does not start a second lifecycle owner.

Return: changes or findings, evidence pointers with results, unresolved inputs,
dependencies on other owners, and explicit side effects performed. The
integration owner checks compatibility and runs the necessary integrated tests.
Independent review should inspect actual artifacts rather than just another
agent's conclusion. Do not represent a second model as production approval.

## Evidence ledger

One row per requirement or decision:

| Field | Meaning |
|---|---|
| Requirement / work ID | The user outcome or gate being assessed |
| Subject | Source revision and dirty-diff identity, immutable artifact ID/hash, behavior bundle, schema and configuration versions as relevant |
| Target | Product, account/project, environment and exact endpoint or local runtime |
| Check / oracle | Command, test, probe or review; acceptance threshold; important exclusions |
| Evidence | Durable location, producer, timestamp and freshness rule |
| Result | PASS, FAIL, SKIPPED, BLOCKED, DEGRADED, or NOT_APPLICABLE with rationale |
| Proof level | Declared, implemented, exercised, proven for this scope, or sustained over the observation window |
| Gap / owner | What remains, who owns it, and the next useful action |

A prose success claim, numeric score, filename, or process exit code alone is
insufficient when the check did not exercise its intended oracle. Verify source
evidence exists and matches the subject. Tests on a dirty tree do not prove a
different committed artifact. A later merge, rebuild, prompt change, policy edit,
or environment change invalidates affected evidence and requires rechecking.

For a local task, keep the ledger compact. For release work, preserve separate
rows for local quality, build, Git publication, preview, live deployment,
authenticated journeys, real providers, migration/recovery, monitoring, and
authorization. A gate's `NOT_APPLICABLE` needs a defensible scope reason.

## State transitions and restart

For full-goal acceptance, cause-specific recovery, persistent help requests and
resumption, read [recovery-and-help.md](recovery-and-help.md). A cycle result and
the end-goal result are separate fields; retain every unmet mandatory criterion.

Work may move from selected to designed to implemented to verified to delivered
only with the corresponding evidence. A failed check returns to the affected
owner. A blocked dependency parks dependent work while independent work continues.

Before an implementation handoff, record one selected delivery engine. Before
fleet parallelism, attach current solo-engine admission, budget, cancellation,
and acceptance proof. Before completion, attach independent closure and current
parent-goal acceptance. Before any live effect, attach the named release
decision, authority, target identity, and rollback/compensation proof required
by the lifecycle policy.

On restart, verify the current repository and external state before resuming.
Reconcile any in-flight operation by its provider operation ID or idempotency
key before retrying. Reuse the same key for uncertain attempts. Do not create a
second payment, migration, deployment, or outbound message because the previous
response was lost. Claim one writer for shared mutable state using an actual
runtime lock when concurrency requires it; a line in a markdown file is not a lock.

Failure records include the observed failure, whether state changed, the next
diagnostic action, and a retry limit. Retry only when the cause or defined retry
semantics justify it. A repeated unchanged blocker does not become progress.

## Completion wording

- `PASS`: the stated work scope met its acceptance criteria with evidence.
- `PARTIAL`: useful requested work is complete but material scope remains.
- `BLOCKED`: a named dependency prevents further work on the outcome.
- `GO / NO_GO / ESCALATE`: a named readiness decision; record the decision owner
  and method. Missing mandatory evidence is `NO_GO`; a judgment or authority
  question can be `ESCALATE`. A decision does not describe deployment state.
- Deployment: planned, attempted, applied, validated, failed, or unknown.
- Recovery: planned, attempted, verified, failed, or unknown.

Use these distinctions in artifacts; ordinary final prose can be shorter.

## Required handoff for an unfinished goal

Include the stable goal/criteria IDs, state location and revision, current subject,
completed and unmet criteria, next runnable work, blocked dependencies, help IDs
and wake conditions, cumulative attempts/resources, in-flight operation keys,
and the exact next action after help. Preserve the goal across compaction/restart.
Do not claim that recording this packet schedules a wakeup or contacts an owner.
# Enterprise completion binding (policy 1.1.0)

When enterprise assurance applies, add enterprise_assurance to the immutable
progress plan with exactly these fields: state (absolute SQLite path), trust
(absolute organization-controlled JSON path), trust_sha256 (canonical JSON
digest), run_id, subject_sha256 (enterprise subject), parent_subject_sha256
(canonical digest of the lifecycle plan subject), and delivery_engine (one
selected engine). The approved admission maps both subject representations.
State and trust files must exist; a saved decision is insufficient. The runner
uses the installed sibling enterprise-ai-assurance-loop verifier, current time
and current pinned trust, matches goal/criteria/engine/subject, and requires
ENTERPRISE proof before goal review. The profile still bounds permitted scope;
completion never authorizes deployment.

The lifecycle ledger pins its own engine bytes. Existing ledgers whose engine
digest predates this change remain blocked under the new engine until an
operator-reviewed engine transition. The existing migrate_state.py supports
same-engine limit changes only; it cannot perform this engine transition.
Preserve the old state and its backed-up runner for review. Do not edit the
engine digest or remove an enterprise binding by hand. Non-enterprise
plans retain the existing contract and tests. A changed enterprise subject or
trust checkpoint needs a reviewed binding transition and fresh assessment.
Automatic cross-version lifecycle-ledger migration is not implemented.
