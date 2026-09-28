---
name: enterprise-human-ai-operations
description: "Test human approval integrity, reviewer workload, incident containment and customer recovery. Use for owner 12 of an enterprise AI assurance assessment; return evidence and unresolved exposure to the shared assurance loop."
metadata:
  version: "1.0.0"
  owner: "enterprise-assurance-owner-12"
---

# Owner 12: enterprise-human-ai-operations

Read [the owner method](references/method.md). Apply this discipline to the named subject, not to unrelated systems. The enterprise-ai-assurance-loop owns the shared run, protected catalog, evidence contracts and final reducer. Do not start another delivery engine or issue deployment permission.

1. Load the parent's subject/profile/verifier digests, nonce, permission boundary, approved thresholds and owner applicability. Owner 4 and Owner 7 use frontier-on-or-unknown OR autonomy at least A2. Other owners must report their bounded coverage. Unknown scope is not an automatic N/A.
2. Execute or obtain authorized observations for **HUMAN-REVIEW, HUMAN-RECOVERY** from the protected catalog. Preserve every trial, failure, timeout and abstention; do not infer missing metrics as zero. Record actual side effects, raw hashes, collection time and expiry, observed scope, limitations and counterevidence.
3. Emit enterprise-evidence/v1 inside an authenticated enterprise-envelope/v1. Use FIXTURE only for synthetic local exercises. Real evidence requires independently administered collector identity, raw artifact custody and the organization-controlled trust configuration. Never sign the producer's claims as if independently observed.
4. Add an enterprise-risk/v1 record for every unresolved applicable gap: impact, unknown exposure, named accountable person, reason unaddressed, interim controls, help needed, review deadline and permitted operation. Acceptance, evidence and technical treatment remain separate. Do not close risks from a passing rerun alone.
5. Request bounded repair through the parent's single selected delivery engine. Do not modify protected tests, thresholds, judges, trust roots, permissions or evidence to secure a pass. Return reproduction, attempted repairs and current subject-bound retest; second-line challenge owns independent closure.

Only prepare help messages unless the organization's adapter has standing delivery authority. A draft is not delivered help. Stop at missing authority or exhausted budgets; retain history and continue independent authorized work. A completed owner report can contain failures and never by itself establishes product readiness.

Run the local oracle fixtures with Python unittest discovery in this package's tests directory. These test assessment predicates and negative observations, not deployed controls. The shared runtime lives in the sibling enterprise-ai-assurance-loop package; install both from the reviewed fleet manifest.
