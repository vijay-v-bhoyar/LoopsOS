# Execution guide

Requires Python 3.12+ and requirements.txt. Install dependencies into an organization-approved environment. Commands below are run from this package. Replace values with actual authorized paths/IDs; no credentials belong in arguments or evidence.

```text
python scripts/assurance.py identity
python scripts/assurance.py plan --state run.sqlite --run-id RUN --trust TRUST.json --trust-sha DIGEST --subject SUBJECT.json --profile PROFILE.json --parent-goal GOAL --criterion CRITERION --engine codex-product-build-loop
python scripts/assurance.py ingest --state run.sqlite --run-id RUN --trust TRUST.json --trust-sha DIGEST --input ENVELOPE.json --blob-dir RAW
python scripts/assurance.py risk --state run.sqlite --run-id RUN --trust TRUST.json --trust-sha DIGEST --input RISK-ENVELOPE.json
python scripts/assurance.py challenge --state run.sqlite --run-id RUN --trust TRUST.json --trust-sha DIGEST --input REVIEW-ENVELOPE.json
python scripts/assurance.py decide --state run.sqlite --run-id RUN --trust TRUST.json --trust-sha DIGEST
python scripts/assurance.py export --state run.sqlite --run-id RUN --trust TRUST.json --trust-sha DIGEST --output NEW-EXPORT-DIRECTORY
```

The raw directory contains files named by their SHA-256 values. Ingest verifies their bytes, retains raw artifacts, authenticates the envelope and verifies semantic predicates. Sign body bytes using the canonical encoding in enterprise_assurance.common.encoded with Ed25519. Envelope issuers and public keys must already exist in the separately protected trust configuration; envelopes cannot introduce keys. Trust digests use the same canonical JSON encoding, not a raw-file hash.

Other commands: inspect (also works for expired runs), waiver, operate, resume, continue, help-request, help-receipt, schedule and tick. Operations and external help receipts use signed envelopes. A draft help-request is a durable local record; this CLI does not send mail or create tickets. Tick is finite, dead-letters overdue help and reevaluates due runs. An external scheduler must invoke it and supervise missing heartbeats. Operator-provided transport integrations are separately admitted.

For a changed immutable subject, continue requires --parent-run, --subject, --profile and a signed MIGRATE envelope. Its body targets the new run/subject/profile, uses the parent nonce, and its operation payload binds the current parent state hash and the new subject/profile digests in references. The parent is superseded; budgets, repair history and outstanding risk IDs carry forward. Fresh owner evidence and independent challenge are required. The old run is preserved for reviewed rollback analysis, never revived to bypass current revocation.

Every evidence payload declares generation from the current plan/inspect output and an observation time at or after the last repair and trust cutoff. A new signature on old observations cannot satisfy retesting. Decision expiry is bounded by supporting evidence, model evidence, reviewer/issuer validity, risk reviews, waivers, the trust checkpoint and the run budget.

The run command runs the fixed platform fixture suite and emits its exit code/output with scope assurance-platform-fixtures. It never converts those results into product evidence. For a complete synthetic local demonstration:

```text
python scripts/local_demo.py --output NEW-DIRECTORY
python -m unittest discover -s tests -p "test_*.py" -v
```

The demo creates only synthetic identities/data and test-only keys in memory. Its exported trust configuration cannot prove enterprise readiness. No provider credentials, deployments or external writes are used. Each owner package has additional local oracle tests in tests/.

Return codes: 0 means the command completed within its stated scope; 1 means a fixture failed or the decision is NO_GO/ESCALATE; 2 means invalid input or blocked authority/prerequisite. Never interpret exit 0 from plan, inspect or export as product readiness.
