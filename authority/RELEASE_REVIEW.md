# Protected release readiness and authenticated review

This protocol records readiness. It never deploys, grants an execution approval, or establishes organizational independence from a local test.

## Policy and evidence

An authenticated caller reads `GET /v1/release-policy`. The authority owns the policy ID, version, monotonic `policy_epoch`, digest, required baseline loops, check names, freshness windows, reviewer roles and no-waivers rule. All selected loops add requirements; removing selected loops cannot remove the six baseline requirements. Its digest binds the startup-captured evaluator and guard source digest (`release_policy`, `models`, `store`, `postgres_store`, `contracts`, `api` and `config`), so changing predicate, persistence-contract or route-guard code invalidates old reviews even if a version bump is missed.

Every authority process activates its configured `LOOPOS_RELEASE_POLICY_EPOCH` in the shared `release_policy_control` row at startup. Increment the epoch whenever the evaluator or trusted release policy changes. Activation is monotonic. If startup detects a different policy at the same epoch, it durably advances a fence marker while retaining the last active policy identity, records `RELEASE_POLICY_EPOCH_FENCED`, and blocks the candidate process. This also makes already-running guarded workers observe a stale epoch and return `NO_GO`; it prevents a missed configuration bump from leaving their prior `GO` current. The operator must then configure an epoch greater than the fence marker and activate the intended policy. Readiness and policy discovery return 503 for a fenced process. Release reads and reviews hold the shared policy row lock while recomputing readiness, so guarded workers cannot make a stale check concurrently with a committed epoch promotion. A stale guarded worker recomputes old records as `NO_GO`; its previous `GO` is not retained. SQLite and Postgres enforce monotonic updates and no-delete rules at the storage layer, Postgres also rejects truncation, and epoch activation is recorded in the existing append-only audit chain.

Drafts still enter through the existing release initiative endpoints. The release assurance object additionally carries `policy_id`, `policy_version`, `policy_digest`, and `release_subject: {repository, commit_sha}`. Repository is an exact owner/repository name; the commit is a 40-character lowercase immutable SHA. An absent policy/subject remains a draft with actionable NO_GO reasons.

For each required loop, provide exactly one gate whose `loop_id` matches the requirement. Its required-evidence list equals the single protected check name `loopos:<loop_id>`; unsupported additional declarations fail closed until a reviewed server policy defines their evidence slots. The artifact label is that same check name, its `loop_id` and `gate_id` match, `required` is true, and `source_ref` is an actual authority connector-event ID. An external ref with that ID must declare GitHub/check, the actual authority event payload hash, and the observed time. Current gate claims must cite that event. These claims do not authenticate their declared reviewer.

Evidence must arrive through configured signed GitHub webhook ingestion as a completed successful check_run with the exact protected name, repository, commit and recent completion time. Both source ingestion and artifact/ref times must be current. A fresh unrelated webhook, caller freshness flag, stale completion, changed digest, removed artifact or optional flag cannot satisfy the requirement. Local manually recorded/session-authenticated evidence cannot yield GO.

All observed signed check states for the same tenant/repository/commit participate, including callbacks received in other workspaces and repository case variants. Selecting an older source ID cannot hide a later failing, pending, stale or invalid current check. Provider completion/start times order observations; ingestion time breaks ties, so a late older success cannot mask a newer failure. Required artifacts must reference the current observed evidence slot, and the entire observed history is bound into the review digest. A newer success still requires a new current evidence binding and fresh review; old approval does not revive automatically. `review_context.observed_check_event_ids` identifies this wider observed evidence set.

The tenant must separately protect its webhook secret, CI publisher and repository controls. A valid webhook signature proves origin under that configured trust, not that an arbitrary check implementation is a reliable enterprise test. The independent authenticated reviewer must inspect the evidence and test meaning. The server protocol and synthetic fixtures are not live provider assurance.

## Review action

Each release record includes `review_context` with exact subject, policy and evidence digests, `reviewable`, blocking reasons and the current authenticated review. The subject digest covers the immutable release record and profile; evidence digest includes the linked observed event content and artifact/source bindings. Reviewability is evidence completeness, not user authorization or permission to deploy.

Submit `POST /v1/release-initiatives/{initiative_id}/reviews` with an `Idempotency-Key` of 8–200 characters and:

```json
{
  "decision": "approve",
  "subject_digest": "<digest returned by current record>",
  "policy_digest": "<digest returned by current record>",
  "evidence_digest": "<digest returned by current record>",
  "previous_review_id": null,
  "basis": "The reviewer explains their evidence-based conclusion."
}
```

Only authenticated Approver/Executive users distinct from the record producer may review. Identity, role and timestamp come from the server; extra claimed reviewer fields are rejected. A stale digest returns a conflict. Approval requires complete evidence and no exceptions. Set `previous_review_id` to the current latest review ID, or null only when none exists. A new approval cannot overwrite an unseen newer review; it returns 409 until the reviewer refreshes and acknowledges it. Rejection is allowed for incomplete records and makes current readiness NO_GO; a later authorized review is a new immutable event, not an overwrite. Reusing an idempotency key with another actor or payload conflicts. Exact retries are checked before review-concurrency comparison and return current state; they cannot resurrect an older approval after a later rejection.

## Exception and retention boundary

The initial policy does not authorize waivers. Any exception in a release record, including caller-marked closed, prevents GO. Known exception history is reconciled across tenant records for the same exact repository/commit and included in the evidence digest: creating another record or changing workspaces cannot erase it. Remediation needs a new commit with its own complete evidence and independent review. Existing exception text remains retained; arbitrary status changes do not create authenticated risk acceptance or closure. This conservative policy does not implement risk waivers or same-commit exception adjudication.

Review facts use existing append-only audit events with exact server-generated type `RELEASE_REVIEW:<initiative_id>`, hash chaining and the existing anchor outbox. The shared policy fence adds only the `release_policy_control` table; its Supabase migration enables RLS and revokes browser-role access. SQLite serializes transactions; PostgreSQL uses the existing per-tenant advisory lock for audit predecessor selection plus row locks for review and policy-epoch serialization. Local tests exercise SQLite persistence, promotion and concurrency; deployed PostgreSQL behavior still requires the authenticated production test environment.

Reads and proof exports recompute the policy, event freshness, complete bindings and review expiry. Legacy contradictory records remain readable for audit but cannot retain a green verdict. A new review requires the workspace to exist. Review identity separation is a technical user-ID/role rule, not proof of an independently administered enterprise reviewer organization.

## Local verification and changed legacy oracles

`authority/tests/test_release_review.py` provides signed synthetic webhook ingestion through the actual local API and a separate authenticated review journey. Its reusable `seed_reviewable_release` accepts a TestClient/httpx client for isolated browser setup. Fixture signatures and identities are deliberately local, never real enterprise endorsements.

The former GO fixture used two passed claims, one old artifact, an unrelated verified event and an unauthenticated approver string. The independent pre-implementation review identified that oracle as the defect. Its exact inputs remain in `test_authority.py`, now expected to fail closed. New tests demonstrate reachable GO with complete signed evidence, actual independent user review, retry safety, persistence, read-time expiry, rejection, recovery, and failure rollback. F05's canonical-decision tests remain in place.

## Production boundaries still requiring acceptance

The shared epoch fences only workers that run this guarded release-policy implementation. A binary started before the fence existed never consults `release_policy_control` and must be drained or otherwise blocked by deployment infrastructure before a policy promotion is accepted. No multi-process Postgres deployment or authenticated old-binary drain was exercised here. Provider App/workflow identity pinning, protected CI definitions and organization-approved attestor mapping also remain unproven. Signed fixture success is not evidence of those controls.

Observed-check and exception-history reconciliation currently scans tenant records in Python. Local correctness tests do not establish enterprise-volume latency or denial-of-service resistance. Persisted subject/check indexes and representative-volume performance acceptance are needed before high-volume rollout.
