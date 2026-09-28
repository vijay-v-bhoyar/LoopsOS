# LoopsOS: enterprise AI testing and assurance assessment

**Assessment:** LOOPSOS-EA-20260920. **Report date:** 20 September 2026, America/New_York; execution timestamps are 21 September UTC. **Decision: NO_GO for enterprise reliance on the release-readiness verdict or an unattended production rollout.**

LoopsOS has useful implemented controls and substantial passing local tests. However, targeted authenticated API probes produced **five erroneous release GO scenarios**. An operator can record a green release while omitting a gate, supplying an unauthenticated reviewer and invalid decision date, retaining an expired active exception, marking required evidence missing, or providing conflicting current decisions. These are failures of the release assurance decision path. They do **not** demonstrate bypass of the separate payload-bound execution/deployment approval path.

This assessment applied the enterprise-ai-assurance-loop and every owner skill numbered 0–12. It tested the app, rather than substituting the assurance framework's own fixture results for product evidence. No application fixes, deployment, paid provider calls, production mutations or messages to third parties were performed. All unresolved findings below remain open.

## 1. Scope, identity and limitations

The target is the current LoopsOS checkout at `C:/Users/vijay/OneDrive/Documents/LoopsOS`, branch `codex/production-hardening`, HEAD `c5ecf910e914cf267a01c231662c831e2f05af34`, including existing uncommitted changes. HEAD alone does not identify the tested working tree. The [source manifest](../output/loopsos-13-owner-20260920/subject.json) records 284 source/configuration/test files; its file-list digest is `78362e60b4b22d6c27c560a599354a85baef48c8c13ddb22813c3e3398593fe5`.

The assessment covers the React UI, intake/document/voice workflows, deterministic and optional LLM assistance boundaries, FastAPI authority, local persistence, identity and approval checks, tool execution contracts, release records and proof packs, audit/worker contracts, runtime corpus, deployment preflight and the selected pilot. Provider responses and enterprise identity in automated tests are mocked or synthetic. No deployed URL was supplied or exercised. Real Postgres, OIDC, credential broker, cloud egress, immutable audit sink, live model behavior and operator staffing therefore remain unverified.

Testing used isolated databases and loopback ports 4373/9287. Provider endpoints were disabled except for intercepted test requests. The production preflight ran against an explicitly isolated evaluation configuration: its failed configuration checks are **not evidence that a particular deployed environment is misconfigured**. They show that the tested local configuration cannot satisfy enterprise admission.

The source manifest was captured during assessment and checked again before report completion. It is local provenance, not a protected build attestation. The registry and installed skills validated, but organization-controlled collector credentials, an approved enterprise profile and an independent second-line signer were not supplied. No signed ENTERPRISE evidence or certification was manufactured. Red-team and blue-team analysis in this report came from the same assessment process; it does not establish institutional independence.

## 2. Fresh test results

| Check | Actual result | What it establishes / excludes |
| --- | --- | --- |
| Authority suite | 283 discovered: **282 passed, 1 skipped** | Local API/store/engine/security behavior. Live Postgres proof was skipped. |
| UI unit/integration | **221 passed**, 24 files | Current deterministic logic and mocked integration behavior. |
| Evaluation browser matrix | **94 passed, 10 skipped**, desktop and mobile Chromium | Real local UI journeys; ten enterprise-specific cases required another mode. |
| Enterprise browser matrix, launch settings as declared by repository script | **10 failed** | Required broker declaration was absent; the tests did not reach their intended assertions. |
| Enterprise browser matrix, assessment-only broker declaration added | **4 passed, 6 failed** | Remaining fixture/expectation drift persists; no app or test source was changed. |
| New adversarial API probes | **5 erroneous GO outcomes**, 2 expected NO_GO controls, 1 retention observation | Direct counterexamples against the running in-process API and real store. |
| TypeScript check | **Passed** | Type/build consistency, not semantic assurance. |
| Vite production build | **Passed** | Evaluation-configured build produced; not an enterprise deployment. |
| Design-token check | **Passed** | Existing token conformance rule. Not a full accessibility certification. |
| Runtime corpus validation | **160 checks passed** | Structural consistency of documents/contracts, not live implementation of every loop. |
| Skill fleet validation | **Passed** | Registered source/install metadata and parity; not app readiness. |
| Selected SDLC pilot | **NO_GO**, 11 selected loops remain DRAFT | Named owners, evidence locations/policies, targets and approved golden fixtures remain incomplete. |
| Local production configuration preflight | **NO_GO**, 8 checks passed / 18 failed | Expected for the isolated evaluation configuration; hosted handover NOT_PROVEN. |
| Current npm vulnerability advisory query | **Unverified** | Initial network query failed; automatic approval review rejected external metadata submission pending permission. |

There were two assessment-harness corrections. Concurrent initial jobs shared the same default database; the first browser startup reported database locked, after which per-job databases were used. The first UI run had 220 passes and one empty-string-versus-undefined assertion failure caused by the assessment's empty endpoint environment variable; removing that override for unit tests produced 221 passes. Raw attempts remain retained. A console encoding error occurred after the build log and successful exit receipt were written; the build itself exited 0. These are not counted as application vulnerabilities.

Primary evidence: [authority log](../output/loopsos-13-owner-20260920/authority.log), [UI log](../output/loopsos-13-owner-20260920/ui-unit.log), [evaluation browser log](../output/loopsos-13-owner-20260920/browser.log), [enterprise browser log](../output/loopsos-13-owner-20260920/enterprise-browser.log), [adversarial inputs and responses](../output/loopsos-13-owner-20260920/adversarial-results.json), [pilot report](../output/loopsos-13-owner-20260920/pilot.json), [configuration report](../output/loopsos-13-owner-20260920/production.json).

## 3. Reproduced release-decision failures

All five scenarios use a synthetic tenant, an authenticated Operator and an existing, fresh provider-verified connector event. The event was deliberately seeded as a valid prerequisite; **webhook-signature forgery was not tested or claimed**. Each scenario submits through POST /v1/release-initiatives, receives HTTP 201, and stores readiness_verdict GO. The payloads pass the current schema validation. Existing tests demonstrate that tenant isolation and webhook signatures are separate enforced controls.

Severity here is an engineering priority: P1 means address before relying on this assurance verdict for consequential release decisions. No CVSS or loss probability is claimed.

### F01 — P1: submitted gates define their own completeness

**Observed:** remove deployment-validation from the gate/decision arrays, leave the release scope and relevant loop bundle in place, and retain one passed gate. The API returns GO. **Cause:** the reducer checks that a nonempty submitted gate list has accepted statuses, but does not derive a protected required-gate set for the release profile. A submitter can reduce the denominator.

**Impact:** a proof pack can appear release-ready without the intended deployment validation. A model or human optimizing for green status can achieve it by omission rather than by supplying proof. **Blue-team correction:** derive required gates from a server-approved, versioned profile bound to scope, risk and subject; require exact applicability dispositions and prevent callers from removing required gates. **Closure test:** delete, rename or duplicate each required gate and ensure the API returns NO_GO or rejects the record; preserve an independently authorized N/A path with evidence.

Evidence: adversarial result `omitted-deployment-gate`; [store reducer](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/store.py:1003).

### F02 — P1: a claimed human reviewer is not an authenticated review

**Observed:** the Operator submits `decided_by=unregistered-independent-reviewer` and `decided_at=not-a-timestamp`; the API stores GO. **Cause:** decision fields are validated as strings and cross-references, not as an authenticated, scoped reviewer event. The create endpoint permits Operator submissions; no separate approval action establishes who made the embedded decision.

**Impact:** audit readers can mistake a user-supplied name for independently exercised decision authority. An invalid or stale review time can survive despite the contract describing a current human decision. **Blue-team correction:** store reviews through a separately authorized endpoint; derive identity from the session, enforce role/conflict rules, bind review to exact subject and evidence digest, validate timezone-aware time and expiry, and invalidate on changes. **Closure test:** an Operator cannot impersonate an Approver; wrong tenant, same producer/reviewer where forbidden, expired review and subject changes fail.

Evidence: `unverified-reviewer-and-date`; [decision validation](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/models.py:211), [release endpoint](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/api.py:803). This finding does not imply that the separate governed action approval mechanism lacks payload binding.

### F03 — P1: expired active exceptions do not affect the verdict

**Observed:** a passed gate plus an active exception describing missing rollback proof, an expiry in 2000, an unverified approver and no compensating controls still yields GO. **Cause:** the reducer examines gate statuses but does not reconcile the separate exceptions array with expiry, approval and residual exposure.

**Impact:** the system can display green while its own record contains unresolved, expired risk acceptance. **Blue-team correction:** evaluate every exception at decision time, require authenticated risk acceptance and valid compensation evidence, and make non-waivable controls explicit. Accepted risk must remain visible and expire. **Closure test:** expired, unapproved, orphaned, insufficiently compensated and non-waivable exceptions deny the affected scope; an allowed exception yields only its bounded permission, never an unconditional green.

Evidence: `expired-active-exception`; [exception schema](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/models.py:237), [readiness reduction](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/store.py:1003).

### F04 — P1: fresh connector evidence can conceal missing gate evidence

**Observed:** a required evidence artifact is marked missing with an observation date in 2000 while its gate remains passed; one fresh provider-verified event is enough for GO. **Cause:** connector-event freshness is checked separately from the gate's required artifacts and embedded external references. A valid provider event does not prove every gate claim.

**Impact:** an unrelated fresh event can lend credibility to stale or absent release proof. Hash-shaped strings in external references do not demonstrate collection, provenance or semantic relevance. **Blue-team correction:** bind each required artifact to retained bytes, source identity, subject, gate, collection time and expiry; evaluate all required artifacts and their semantic predicates. **Closure test:** missing/stale/mismatched artifacts deny GO even when a different connector event is fresh. Keep the existing read-time connector freshness recalculation.

Evidence: `required-evidence-missing`; [artifact validation](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/models.py:202), [freshness refresh](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/store.py:932).

### F05 — P1: conflicting current decisions are accepted

**Observed:** the gate's embedded last_decision says passed while the matching entry in the decisions array says blocked. The API stores GO. **Cause:** validation selects the embedded decision first. The later last_decision comparison is against that already selected decision, so it does not establish equality with the decisions-array entry.

**Impact:** different report consumers can read contradictory authoritative-looking answers. A summary can favor the favorable copy and hide a veto. **Blue-team correction:** maintain a single authoritative review record and references to it; reject disagreement while migrating existing records, preserve conflict evidence and apply veto precedence. **Closure test:** vary status, reviewer, time, evidence references and decision IDs across the two representations and reject every mismatch.

Evidence: `conflicting-current-decisions`; [decision selection and comparison](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/models.py:305).

**Positive controls:** removing all provider evidence returns NO_GO; an explicitly blocked gate returns NO_GO. These results show a selective semantic failure, not a reducer that always returns GO. Reproduce locally with [adversarial_probes.py](../output/loopsos-13-owner-20260920/adversarial_probes.py); it uses temporary fixture identities and does not deploy anything.

## 4. Findings and evidence for all thirteen owners

### Owner 0 — Enterprise AI discovery

**Skill:** enterprise-ai-discovery. **Disposition: PARTIAL; observable local inventory established, production routes unverified.**

The app has three materially different surfaces: deterministic recommendation/intake logic, explicitly requested external LLM/transcription services, and a governed authority capable of durable local or HTTP actions. The document-processing workers, browser state, connector webhooks, audit sink, OIDC/JWKS, database and background worker are dependencies in the business workflow even though not all are models. Treating only the configured LLM URL as the AI inventory would miss consequential control dependencies.

Graphify was queried first and refreshed for 146 Python/TypeScript/JavaScript files: 1,798 nodes and 5,536 edges, with 73 references explicitly unresolved. Zero dangling endpoints is a graph-integrity result, not proof all dependencies are understood. The 160 corpus checks passed, while the pilot verifier still classified all eleven selected operational loops as DRAFT. This separates executable local code from declared operating capability.

**Red-team view:** a configured endpoint may change provider/model behind the same URL; an assistive draft can be carried into release records whose decision semantics permit F01–F05. A diagram of individual tools can miss that composed authority. **Blue-team requirement:** inventory actual route, model, prompt, context, tool, source, data region, identity and enforcement versions per workflow; reconcile declared versus observed resources. Seed a missing dependency and measure detection rather than relying on a clean inventory export.

**Open evidence:** no real vendor endpoint, account/region mapping, live network inventory or shadow-service discovery was supplied. Owners 4 and 7 remain applicable because capability is unknown; this is not a claim that a frontier model is deployed. **Closure:** a named product/platform owner signs scope, reconciles runtime routes against the inventory and demonstrates detection of seeded drift. Reopen on endpoint, model, tool, permission or workflow composition changes.

### Owner 1 — AI quality and complete business outcomes

**Skill:** enterprise-ai-quality. **Disposition: LOCAL FUNCTIONAL COVERAGE PASSED; business effectiveness and release correctness incomplete.**

The UI's 221 tests and 94 passing evaluation browser cases cover recommendations, selected-field application, fallback behavior, workspace persistence, export, release planning and several failure boundaries. TypeScript, build and token conformance checks passed. These are meaningful implementation results; they do not establish customer value, decision correctness across a representative enterprise population, or long-term loss rates.

The five API counterexamples demonstrate why pass count cannot be the quality denominator. Existing tests accepted normal release shapes; adversarial mutations produced incorrect readiness even when those tests passed. A fresh green provider event and a user-authored gate decision are not a complete business outcome. ROI estimates and planning metrics must remain estimates until measurements are connected to actual outcomes.

**Red-team campaign:** preserve every intake item, including refused, failed, abandoned and delayed cases; challenge whether a green completion rate improves by excluding difficult cases. Evaluate false GO, false NO_GO, time to resolve, rework, missed deadlines, incomplete customer remediation and cumulative loss. Include multilingual and accessibility cohorts, with approved labels and sufficient samples.

**Blue-team requirement:** independently define the denominator and success criteria before testing. Use application events plus independent business records, not the app's own decision as its truth label. Keep delayed outcome observation separate from immediate technical success. **Open evidence:** no representative business dataset, cohort baseline, longitudinal observation or approved effect threshold was available. **Closure:** quality and business owners approve the sampling/labeling plan, establish a baseline and show that repaired release decisions and complete customer journeys meet the agreed bounds. Zero observed failures in a small fixture suite cannot support a general failure-rate claim.

### Owner 2 — LLM assurance

**Skill:** enterprise-llm-assurance. **Disposition: BOUNDARY TESTS PASSED; real-model robustness UNVERIFIED.**

Observed controls include explicit consent before external assistance, deterministic fallback, blocking sensitive/regulated use cases in relevant paths, bounded request/response handling, endpoint allowlists, HTTPS constraints for remote services, redirect rejection, omitted credentials and response shape validation. Question and field-proposal tests exercised invalid responses, missing consent and sensitive input. Browser tests exercised mocked LLM/transcription paths; none establish live model behavior.

**F06 — P2, source-confirmed gap:** external provenance records `configured-endpoint` and `provider-declared-model-required`, rather than retaining a verified provider/model revision from the response. See [questionAssistant.ts](C:/Users/vijay/OneDrive/Documents/LoopsOS/ui/src/lib/questionAssistant.ts:10) and [fieldProposal.ts](C:/Users/vijay/OneDrive/Documents/LoopsOS/ui/src/features/useCaseIntake/fieldProposal.ts:45). Consequently the app cannot reliably tie an observed answer, regression or incident to an immutable model route from these records alone.

**Red-team campaign:** malicious instructions in uploaded/retrieved material, repeated sources with one poisoned origin, multilingual multi-turn leakage, structured but semantically false responses, gradual disclosure across sessions, and a fallback with weaker safeguards. The response validator validates shape; it does not establish truth or source independence. Tests must measure effects and retained data, not just whether the model refuses a familiar attack string.

**Blue-team requirement:** place authorization and sensitive-data boundaries outside generation; retain authenticated route/model/prompt/configuration identity, trusted provenance labels and actual output evidence. **Closure:** provider-specific isolated campaigns with complete attempt logs, data canaries, held-out attacks, calibrated human/domain judgments and regression/fallback gates. No safe live target, budget or provider credentials were supplied, so no jailbreak success rate, hallucination rate or disclosure bound is asserted.

### Owner 3 — Agentic assurance

**Skill:** enterprise-agentic-assurance. **Disposition: SUBSTANTIAL LOCAL CONTROL PROOF; enterprise effect accounting incomplete.**

The authority suite passed tests for payload-bound high-risk approval, tenant-scoped mutation, idempotency, retry reuse, durable execution leases, lease-owner checks, retry-budget exhaustion, kill switches, restart/reconciliation and scoped credential leases. External effects require a rollback/compensation contract. Production connector dispatch refuses static bearer-token authority and requires the broker path. These are stronger controls than trusting model instructions alone.

**F07 — P1 for unattended consequential scope, design gap:** the inspected app ExecutionPlan has per-run max_attempts and bounded probe/evidence arrays, but no demonstrated transactional enterprise-wide business-exposure ledger across runs, tenants/workflows or unknown provider outcomes. [ExecutionPlan](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/models.py:504). Rate limits and retry limits are not dollar, resource, customer-impact or outstanding-effect reservations. The new assurance skill's reference ActionGateway must not be mistaken for an integration already installed in the app's HTTP dispatch path.

**Red-team campaign:** repeat small approved actions under distinct run IDs, partition a worker after provider commit, revoke authority during a retry, recover a stale lease, and combine individually allowed steps into a prohibited result. Test cancellation when an external action already happened. **Blue-team requirement:** shared reservations with fencing, explicit unknown exposure, reconciliation before reissue and separately authorized compensation. Bind delegation to subsets of parent authority and budget.

**Open evidence:** no real provider commit/duplicate semantics, OS sandbox enforcement or bounded stop latency was tested. **Closure:** an actual product enforcement adapter passes race, partition, restart, late-worker and compensation drills under approved aggregate bounds. A process stopping is not proof that its customer effects were reversed.

### Owner 4 — Frontier-model assurance

**Skill:** enterprise-frontier-assurance. **Disposition: APPLICABLE, UNVERIFIED for model behavior.**

The external route's capability is unknown, and the authority can support consequential tool effects. This makes a capability assessment relevant without assuming that the present configuration is highly autonomous. The local tests establish response boundaries and deterministic behavior, not whether a particular frontier model changes strategy over longer horizons or under different oversight cues.

The app's provenance limitation F06 prevents confident correlation of outputs with a stable provider/model revision. A model alias can remain constant while provider routing, prompt, context, tools or inference settings change. The assurance package includes a candidate model comparison helper, but this assessment found no evidence of an operational app-to-helper promotion pipeline or fresh provider benchmark campaign. Installing a skill does not automatically update or validate the app's model.

**Red-team campaign:** compare complete baseline and candidate system bundles; vary irrelevant evaluation cues; resume from checkpoints; extend task horizons; give an impossible authorized goal; and test whether the system requests help rather than expanding its authority. Include monitor effectiveness and fallback behavior, not just task accuracy. A claim that a test environment is simulated must never unlock a real endpoint.

**Blue-team requirement:** require a capability registry with dated evidence and deprecation status, fixed regressions, private adaptive tests, a bounded promotion decision and revocation-preserving rollback. **Closure:** independently collected candidate evidence satisfies approved quality, harm, cost and detection limits on the intended workload. Record unexplored capabilities, uncertainty and query/compute budgets. Behavioral differences may be observable without establishing deceptive intent; the report makes no claim to detect or exclude hidden intent.

### Owner 5 — Threat modeling and security architecture

**Skill:** enterprise-ai-threat-modeling. **Disposition: OPEN P1 FINDINGS.**

The primary demonstrated attack path is: authenticated Operator → release JSON → structurally valid but semantically incomplete decision/evidence → durable authority record → GO/proof-pack output. The valid connector event is a prerequisite, not an attacker-created signature. F01–F05 concern trust propagation inside this path. The independent action-execution approval boundary limits what those release records alone can do; no bypass of it was demonstrated.

The blue controls exercised include tenant checks, role restrictions, optimistic revisions, request limits, signed webhook ingestion, append-only audit triggers, outbound checks and broker fail-closed behavior. Source inspection shows redirects disabled and DNS results checked for non-global addresses in the HTTP tool. **Residual hypothesis:** DNS validation and connection establishment use separate operations; deployment-specific DNS rebinding resistance and an independent egress boundary still need a controlled test. This is not reported as a proven SSRF exploit.

**Red-team expansion:** malicious authenticated insiders, compromised reviewers/collectors, shared identity outages, poisoned evidence, cross-workflow budget slicing, accepted exceptions with a common failed compensating control, and an assurance system attacker who targets the grader instead of the model. A signed malicious input remains malicious after signature verification.

**Blue-team closure:** fix the five release invariants, freeze the required evidence manifest, and demonstrate negative controls through the public API. Add a composed threat/control/dependency graph, authorized abuse campaigns and an enterprise exposure register. Keep likelihood unknown where frequency data is absent. The presence of a threat-model document does not establish attack-tree completeness or zero residual risk.

### Owner 6 — Cryptographic and quantum-safe assurance

**Skill:** enterprise-quantum-safe-assurance. **Disposition: CLASSICAL CONTROL TESTS PARTIAL; quantum-safe posture UNPROVEN.**

Source inspection identifies HS256/HMAC-SHA-256 for local authority sessions, RS256 for OIDC verification, SHA-256 content/audit digests and HMAC-SHA-256 for anchor delivery. OIDC pins an algorithm list and checks issuer/audience and required time/subject claims. Session revocation tests passed; append-only audit rows and signed anchor dispatch are covered by local tests. Algorithm locations include [auth.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/auth.py:56), [identity.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/identity.py:67), and [audit_anchor.py](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/audit_anchor.py:37).

No claim of a complete cryptographic bill of materials, negotiated post-quantum transport, provider cryptography, protected key custody, cryptographic erasure or long-lived backup confidentiality follows from those observations. A post-quantum loop descriptor is an intention until actual cryptographic paths and migrations are verified. The report does not classify all currently used algorithms as broken.

**Red-team campaign:** retired signing key, revoked package rollback, wrong issuer/audience, replay, weak downstream hop behind secure ingress, backup/export outside the approved encryption boundary and a validly signed malicious tool. **Blue-team requirement:** inventory every confidentiality and authenticity path, key owner, lifetime, rotation/revocation process, dependent vendor and migration constraint. Distinguish hash integrity from issuer authentication and both from behavioral safety.

**Closure:** security/cryptography owners approve the CBOM and retention horizon, run rotation/revocation/downgrade drills and supply current transport/key-management evidence for the intended environment. The assurance library's local signatures and the app's local audit chain do not establish a protected enterprise root of trust.

### Owner 7 — Advanced capability, specification gaming and coordination

**Skill:** enterprise-advanced-capability-assurance. **Disposition: SPECIFICATION-GAMING PATH DEMONSTRATED; frontier hypotheses untested.**

F01 is a concrete specification-gaming opportunity: a submitter can lower the gate denominator and receive GO. F05 adds contradictory records from which a downstream summarizer could select the favorable result. These examples do not require a frontier model, and they do not prove model intent. They show that a capable optimizer would have an available path to apparent success without satisfying the business requirement.

The app's actual execution engine has stop and restart tests, but those do not establish multi-agent coordination safety, trust-preserving memory compaction, agent-to-agent delegation controls or a broad correction property. No live multi-agent system, persistent model memory service or advanced capability campaign was observed in this assessment. Those claims therefore remain bounded and conditional, rather than being marked passed or universally applicable to every feature.

**Red-team campaign:** conceal failed trials, merge allowed actions into a prohibited outcome, inject instructions into shared artifacts, present an impossible success target, modify a grader and resume after revocation. Use independent intake and effect ledgers so omissions can be measured. Compare isolated versus communicating agents only when that architecture actually exists.

**Blue-team closure:** freeze grading, authority and task denominators outside the candidate; prevent a model from editing its own judge or trust root; test correction and randomly timed stops over resumed work. Success means specified scenarios passed within stated limits, not corrigibility certification. Missing capabilities, unobserved coordination and uncertain oversight sensitivity remain in the risk register, with a named owner and explicit expansion prerequisites.

### Owner 8 — Regulatory and governance assurance

**Skill:** enterprise-ai-regulatory-assurance. **Disposition: GOVERNANCE READINESS BLOCKED; legal applicability unresolved.**

The corpus validator passed structural governance checks, but the selected pilot remains NO_GO: eleven descriptors are DRAFT; accountable policy/gate/risk/executor/validator/backup owners are not bound; authoritative evidence locations and retention/freshness policies are incomplete; target values and approved golden fixtures are missing. These are directly reported by the pilot verifier, not inferred from a generic maturity checklist.

F02 and F03 weaken the meaning of recorded decision authority and accepted risk. F04 breaks the link between a passed gate and its required proof. A notice or board report built from such a packet could accurately reproduce stored text while misrepresenting the actual basis for the decision. That is a governance-integrity concern; this report does not assert that a particular law has been violated.

**Red-team campaign:** apply a workflow under a different entity/jurisdiction; compose assistive tools into a consequential decision; change the model/data/policy without changing the notice; reuse expired acceptance; conflict deletion with a legal hold. **Blue-team requirement:** an effective-dated obligation register tied to actual deployment roles and workflows, immutable decision lineage, authenticated acceptance and non-waivable constraints.

**Closure:** organizational legal/risk owners determine applicability, required notices/contestability and retention/hold rules, and sign the actual risk profile. The Commission's current AI Act materials are a source to verify applicable classifications and dates, not a blanket finding that LoopsOS is compliant. [Official AI Act framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai). No outdated high-risk implementation deadline is hardcoded into this report.

### Owner 9 — Data lifecycle, privacy and evidence custody

**Skill:** enterprise-ai-data-lifecycle. **Disposition: LOCAL BOUNDARIES PARTIAL; derivative deletion and restore unproven.**

Document intake enforces file count/size and text limits, validates file-type signatures, and performs binary parsing in a worker that can be terminated. Sensitive-data outbound consent tests and selected-field review tests passed. Enterprise workspace persistence has tenant and optimistic-revision tests; the evaluation mode uses local browser storage. Export is an intentional data-copy path, not an encrypted enterprise records system.

**F08 — P2, observed retention behavior:** deleting a workspace returns 204, but a previously created release proof pack remains retrievable with HTTP 200 and retains its source event. This may be legitimate audit retention; it is **not** described as a proven privacy violation. It means “delete workspace” must not be represented as purging all related evidence, events, exports or backups. See result `deletion-retains-release-proof` and [delete_workspace](C:/Users/vijay/OneDrive/Documents/LoopsOS/authority/loopos_authority/store.py:552).

**Red-team campaign:** synthetic canary deletion, derivative/cache/export inventory, restore from an earlier backup, stale browser synchronization, consent changes and use of system-generated outcomes as training/evaluation labels. Prove tombstones and holds survive restoration where required, and track any deliberately retained audit material under an approved policy.

**Blue-team closure:** data/records owners define user deletion versus retained evidence semantics; implement an authorized lifecycle workflow and test all declared derivatives. Supply lawful-use, access control, encryption, retention, hold and purge evidence. The live Postgres test was skipped and no real backup restore or vendor deletion proof was supplied. A successful SQLite delete is not evidence of enterprise erasure.

### Owner 10 — Independent challenge and assurance integrity

**Skill:** enterprise-ai-independent-challenge. **Disposition: LOCAL CHALLENGE FOUND FAILURES; institutional independence NOT ESTABLISHED.**

The strongest evidence in this assessment is the counterexample set that passed request validation but contradicted intended release assurance. Passing the existing 282 authority tests did not prevent five new failures. This demonstrates why the same producer's green suite and self-described reviewer identity cannot be the only basis for release.

The new enterprise assurance skill has stronger typed evidence and reviewer contracts, but the tested app's release endpoint does not automatically inherit them. F02 accepts a reviewer name; F05 permits contradictory review representations; F01 lets the submitter define the tested denominator. An audit chain can preserve an incorrect claim exactly. Integrity of storage is not truth of collection or validity of judgment.

**Red-team campaign:** forged result summaries, dropped failures, stale evidence re-signed as current, grader instructions embedded in evidence, compromised collector, same principal with multiple names and a preserved old GO after revocation. **Blue-team requirement:** protected collection, frozen case manifest, direct raw evidence access, independently administered roles, full trial reconciliation, calibrated judgments and a binding veto.

**Closure:** an organizational second line independently reproduces the five counterexamples and their fixes against the exact subject, reviews open risk and issues a bounded challenge decision. No such person or institution is impersonated here. The local report and digests are reproducible evidence aids, not protected enterprise attestations. The absence of an approved trust configuration prevents a legitimate ENTERPRISE assessment receipt; it must remain a prerequisite, not be filled using locally invented signing identities.

### Owner 11 — Vendor, dependency and supply-chain assurance

**Skill:** enterprise-ai-vendor-assurance. **Disposition: SOURCE CONTROLS PARTIAL; current advisory and live vendor proof incomplete.**

The dependency manifests, pinned authority requirements, runtime image references, workflow and supply-chain tests were inspected. The authority suite includes successful negative OCI tests for absent archives/SBOMs, malformed attestations and mismatched subjects. These test the verifier's behavior; this task did not build, scan or run the release OCI images. An existing VEX document is source material, not a newly verified absence of vulnerabilities.

The LLM/transcription provider is configured externally and F06 prevents dependable per-output model identity in the inspected provenance path. A primary/fallback brand list would not establish independence if both depend on the same upstream model, region, identity system or broker. Provider-internal training, deletion and isolation remain outside direct local observation.

**External scan status:** npm's local attempt could not query advisories. Automatic approval review rejected the requested network retry because it would disclose package names/versions to registry.npmjs.org. No alternate service was used to bypass that decision; the advisory result remains unverified unless permission arrives and the scan succeeds.

**Red-team campaign:** compromised but signed tool, alias drift, correlated provider outage, account/region-specific behavior, expired dependency support and fallback that violates data terms. **Blue-team closure:** approved vendor inventory, observed route evidence, contractual assurances labeled separately from tests, current SBOM/advisory scan, release attestation and tested exit/fallback plan. Assign procurement/security/platform owners and expiration/recheck triggers; do not interpret a digest pin as a lifetime security guarantee.

### Owner 12 — Human oversight and operational recovery

**Skill:** enterprise-human-ai-operations. **Disposition: EVALUATION UX COVERAGE PASSED; enterprise operations unproven.**

The evaluation browser matrix passed desktop/mobile workflows for local entry, intake/review, document/voice failure handling, workspaces, release records and proof-pack download. Kill-switch and approval tests prove useful local authority boundaries. They do not establish that real operators detect seeded errors under workload, that an alert reaches an on-call responder, or that customer effects are corrected after stopping a process.

**F09 — P2, reproduced test-contract drift:** the repository enterprise runner omits the required credential-injection mode. Under equivalent settings all ten enterprise cases fail before reaching the intended scenario. Adding that declaration only in the assessment harness yields four passes and six failures. Several mocked readiness responses omit required broker/rate-limit fields, so the UI fails closed at readiness validation and the tests cannot reach their intended binding/retry assertions. See [run-enterprise-gate.mjs](C:/Users/vijay/OneDrive/Documents/LoopsOS/ui/scripts/run-enterprise-gate.mjs:3), [readiness parser](C:/Users/vijay/OneDrive/Documents/LoopsOS/ui/src/features/governedExecution/authorityClient.ts:661) and [enterprise tests](C:/Users/vijay/OneDrive/Documents/LoopsOS/ui/e2e/enterprise-readiness-gate.spec.ts:223). Repair fixtures and test the intended path; do not weaken the production validator to make tests green.

**Red-team campaign:** reviewer overload after many correct recommendations, absent approver/deputy, inaccessible warnings, misleading confidence, stale approval, notification failure and successful technical rollback with unresolved customer harm. **Blue-team closure:** authenticated effect-bound approval UI, representative operator drills, measured stop/detection response, staffed escalation and real customer recovery records. No human-fatigue or screen-reader study, real on-call delivery, restoration drill or customer-remediation exercise occurred in this task.

## 5. Cross-owner risk and remediation order

All named owners below are required roles, **not assigned people**. Risk acceptance is not recorded for any item. Review before pilot/release and reopen on material subject, model, data, policy, vendor or enforcement change.

| Priority / record | Required accountable role | Next change or evidence | Completion criterion |
| --- | --- | --- | --- |
| P1 F01/F04 | Authority and release-policy owner | Protected required-gate/artifact manifest with source/subject/freshness binding | Omission and missing/stale artifacts cannot yield GO. |
| P1 F02/F05 | Security, release owner and independent assurance | Authenticated immutable review events; remove conflicting decision sources | Impersonation, invalid dates, replay and conflicting reviews are rejected. |
| P1 F03 | Risk owner and release-policy owner | Executable exception/expiry/compensation and non-waivable rules | Expired or unapproved risk cannot disappear from the decision. |
| P1 F07 for unattended effects | Runtime/security owner | Aggregate exposure reservations and real provider reconciliation | Race, restart, timeout and lost-response drills remain within approved bounds. |
| P2 F06 | Model/platform owner | Provider/model/configuration provenance and model-change gate | Every output and candidate benchmark binds the actual approved route. |
| P2 F08 | Data/records owner | Explicit deletion/retention/hold/restore workflow | Synthetic canaries obey approved semantics across all derivatives. |
| P2 F09 | QA/platform owner | Update enterprise launch declarations and full readiness fixtures | All ten intended enterprise browser cases reach and validate their target conditions. |
| Activation blocker | Product/operations owners | Bind eleven pilot loops to real owners, evidence, targets and approved fixtures | Pilot verifier passes on organization-approved inputs and actual integrations. |
| Activation blocker | Security/platform/SRE | Real IdP, managed database, broker, worker, audit sink, retention and restore evidence | Hosted handover, tenant isolation, break-glass and recovery verified on the named target. |
| Evidence gap | Vendor/security owner | Approved current advisory scan and release image evidence | Current scans and retained attestations reviewed; unresolved findings retained. |
| Evidence gap | Independent second line | Protected collection and independent challenge | Current exact-subject challenge with conflicts disclosed and vetoes resolved. |
| Evidence gap | Business/domain/model owners | Complete outcome, frontier and human campaigns | Approved thresholds, denominators, uncertainty and residual risks documented. |

**Immediate containment recommendation:** continue local evaluation with synthetic/non-sensitive data and provider endpoints disabled. Treat existing release GO records as historical claims requiring re-evaluation after fixes. Do not consume them as enterprise release approval. This recommendation does not remotely disable an existing deployment; observed product restrictions require a separately authorized enforcement action and acknowledgement.

**Repair sequence:** first preserve the five counterexamples as regression tests and repair the release invariants together; next repair enterprise test fixtures and provenance; then implement product-specific aggregate effect and data-lifecycle controls. In parallel, obtain named organizational owners and infrastructure proof. Finish with independent retesting of the complete subject and all open risk, not only changed units. Any repaired version requires a new source manifest and fresh report; this report does not mark anticipated fixes complete.

## 6. Additional campaigns required before Fortune 500 reliance

1. **Complete decision lineage:** source event → retained bytes → gate requirement → authenticated review → exception → scoped decision → actual action. Mutate one link at a time; all unauthorized substitutions must deny the affected permission.
2. **Long-horizon and composition:** realistic sequences across sessions and workers, small repeated impacts, hidden failures and impossible goals. Preserve failures, deferrals and abandoned tasks in the denominator.
3. **Provider effects:** response lost after commit, duplicate webhook, reordered callback, expired lease, revoked approval, partial compensation and compensation failure. Measure business exposure separately from process state.
4. **Trust incident:** revoke a previously trusted collector/signer and enumerate every dependent decision. Historical evidence stays retained; current permission must be re-evaluated and actual restrictions acknowledged.
5. **Data restoration:** delete synthetic data, restore older snapshots, sync stale clients and query declared derivatives. Test legal hold conflicts under an approved policy, rather than deleting audit evidence indiscriminately.
6. **Independent controls:** malicious replacement model attempts forbidden actions; validly signed malicious package attempts prohibited egress; the host boundary must enforce denial without model cooperation.
7. **Human and service continuity:** workload, absent responders, accessibility/language differences, deputy handoff, alert dead letters, real recovery and customer correction. Acknowledged help is not completed remediation.
8. **Capability change:** pin complete old/new model-system bundles and approved profiles; run fixed and private campaigns, quality/cost/harm/detection comparisons and rollback drills. Newer models are candidates, not automatic improvements.

Each campaign needs an authorized target, an independent observation method, approved bounds, accountable owner, complete raw trials, expected versus observed effects, retest criteria and an expiry. Missing inputs remain missing; local synthetic thresholds cannot stand in for enterprise risk appetite.

## 7. Current reference basis and assurance limits

The assessment used the installed thirteen-owner methods and refreshed primary reference pages during this run. OWASP's agentic guidance is a current risk-discovery reference, not a certification checklist or evidence that its entire scope was executed. [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/).

NIST's AI RMF and Generative AI Profile provide risk-management context. NIST currently notes ongoing revision activity; a static mapping should retain version/date and be refreshed. [NIST AI RMF and GenAI profile](https://www.nist.gov/itl/ai-risk-management-framework).

Legal applicability requires the actual entity, jurisdiction, product role and use case. Current Commission guidance is consulted for that determination; this local code/test review is not a legal compliance opinion. [European Commission AI Act framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai).

No percentage safety score is assigned. No claim is made that finite tests exclude hidden capability, deception, unknown shadow services, privileged-host compromise, vendor-internal data use or correlated human failure. Those uncertainty classes remain explicit in the owner sections. The appropriate present conclusion is **useful local evaluation capability, demonstrated release-decision defects, and enterprise readiness not established**.

## 8. Evidence index and reproducibility

The [machine-readable risk register](../output/loopsos-13-owner-20260920/risk-register.json) retains sixteen open findings, evidence gaps and hypotheses, including unassigned accountable people, absent risk acceptance and required closure evidence. The [evidence index](../output/loopsos-13-owner-20260920/evidence-index.json) hashes retained logs, probes, reports and the installed skill methods. The [report integrity check](../output/loopsos-13-owner-20260920/report-validation.json) verifies all thirteen owner sections, local links, command-receipt hashes and unchanged source-manifest files. Its PASS means report integrity only; the product readiness decision remains NO_GO. These indexes are unsigned local records, not enterprise attestations.

All current assessment artifacts are under [output/loopsos-13-owner-20260920](../output/loopsos-13-owner-20260920). Command receipts retain start time, duration, command, local scope, exit code and log SHA-256. Previous failed attempts are retained separately. The [runner](../output/loopsos-13-owner-20260920/run_checks.py), [adversarial probes](../output/loopsos-13-owner-20260920/adversarial_probes.py), [source capture](../output/loopsos-13-owner-20260920/capture_subject.py), [source manifest](../output/loopsos-13-owner-20260920/subject.json) and [graph diagnostics](../output/loopsos-13-owner-20260920/graph-diagnostics.json) provide the reproducible basis.

Use an approved Python environment with the repository requirements. The test runner accepts authority, ui-unit, browser, enterprise-browser, typecheck, build, design, corpus, production, pilot or fleet. Its browser servers are temporary local test servers, not a deployed or persistent user preview. The output directory contains synthetic evidence and local test records, not production credentials.

The existing application sources were not repaired during this assessment. Tests/builds may update generated caches; report and probe artifacts were added under reports/output. A reader should use the raw failed outcomes as well as the passing summaries when deciding the next work.
