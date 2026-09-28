# LoopsOS — current enterprise AI assessment across all thirteen owners

**Decision: NO_GO for Fortune 500 production reliance or unattended enterprise rollout. Assessment complete with open findings; remediation and enterprise acceptance are not complete.**

Assessment ID: `LOOPSOS-EA-REFRESH-20260921`. Report date: 21 September 2026. Exact UTC execution timestamps are in the attached receipts. This is a detailed assessment of the actual LoopsOS application, applying the enterprise-ai-assurance-loop and all thirteen owner methods (0–12). It does not substitute tests of the assurance skills for tests of the product.

The current application suites pass locally, but targeted challenges still expose two consequential boundaries: a retired audit worker can send to an old destination after rotation, and a release check from a missing or unapproved publisher can become GO after valid separate review. Provider, infrastructure, business-outcome, human-effectiveness and organizational-independence evidence remains incomplete. No numerical safety score is assigned because those missing denominators would make it misleading.

## Scope, provenance and how to read this report

The target is `C:/Users/vijay/OneDrive/Documents/LoopsOS`, branch `codex/production-hardening`, HEAD `c5ecf910e914cf267a01c231662c831e2f05af34`, including preexisting uncommitted changes. A manifest of **315 source/configuration/test/document files** identifies the tested content: `af68e093015bf19cea8636e464825632b44284e4ff44c3f952440661404a6226`. Every file was rehashed at report generation with **zero drift**. HEAD alone is insufficient to identify this checkout. Graphify refreshed 164 code files: 2,033 nodes, 6,342 edges, 82 explicit unresolved references, zero dangling endpoints. This is structural orientation, not complete security coverage.

The [authoritative registry](../skill-fleet/registry.json) has SHA-256 `1a3b198b8d6a6108ab0a3a8a194e86fc22039465ce724ee8782ba8ab732974b0`. Lifecycle policy version is `1.1.0`; canonical policy JSON digest is `436576de960e56410d114ecccbb654215b22146080dcff2e84936baaf55d43cf`. The assurance catalog and all owner skill/method hashes are retained in [verification.json](../output/loopsos-13-owner-refresh/verification.json). The lifecycle conductor remains product-lifecycle-loop; codex-product-build-loop remains the sole selected delivery engine for any separately authorized repairs. No application repairs were made during this assessment refresh.

The supplied framework v3.0.0 informed the owner structure. Its instructions are source requirements, not execution authority. Its insurance-specific retention formulas, named roles and regulatory assertions were not silently adopted as applicable law or evidence about this deployment. There is no approved enterprise entity/jurisdiction/profile, organization-controlled collector/trust bundle or second-line signer for this assessment. Consequently the output is an **unsigned local engineering report**, not a signed ENTERPRISE envelope, legal opinion, certification or deployment permission.

Fresh execution used temporary/isolated SQLite, in-process API clients and local desktop/mobile Chromium. Remote LLM/transcription behavior was intercepted; synthetic gateway/webhook signatures and identities were used. No live provider spending, production deployment, real tenant changes or third-party messages occurred. Public reference browsing did not transmit source code or dependency inventories. No hosted app URL was exercised.

The owner narratives below retain relevant repair history from earlier reports on this same source manifest, with fresh suite evidence separately identified. Earlier reproduction/independent-review artifacts are historical evidence, not newly rerun campaigns unless stated. A local PASS closes only its exact test claim. Unrun live campaigns remain **UNPROVEN**, and frontier/advanced applicability is kept open because the deployed capability/autonomy profile is unknown. None of the 26 catalog case families is asserted enterprise-complete from these local tests.

## Fresh execution results

| Check | Result | Meaning and limit |
| --- | --- | --- |
| Authority API/store/engine/security suite | **374 passed, 1 skipped; 375 executions** | 355 distinct IDs; 20 imported API cases run twice. The PostgreSQL live test remains skipped. |
| UI unit/integration | **278 passed in 29 files** | Deterministic and mocked integration behavior. |
| Evaluation browser matrix | **100 passed, 10 skipped** | Desktop/mobile Chromium; enterprise-only cases intentionally skipped here. |
| Enterprise-mode browser matrix | **10 passed, zero skipped** | All ten skipped evaluation cases reached their enterprise-mode assertions; infrastructure remains simulated. |
| TypeScript / Vite build / design tokens | **PASS / PASS / PASS** | Evaluation build and token rules; no production or accessibility certification. |
| Runtime corpus | **PASS** | Structural document/schema consistency, not operational activation. |
| Skill fleet | **PASS; no validator errors** | Registered metadata, references and parity within validator scope. |
| Production configuration preflight | **NO_GO; 9 passed / 18 failed** | Isolated evaluation configuration; not a claim that an uninspected deployment is misconfigured. Hosted handover NOT_PROVEN. |
| Selected SDLC pilot | **NO_GO; eleven selected loops remain DRAFT** | Missing organization-owned activation inputs. |
| Audit-worker rotation probe | **FAILURE REPRODUCED** | Retired worker delivered one event; new worker delivered none; current receipt remained unverified. |
| Release publisher probes | **2 incomplete-trust outcomes reproduced** | Missing and unapproved origin metadata both reached GO after valid separate review. |

All command arguments, timing, exit codes and SHA-256 log digests are retained in [the evidence index](../output/loopsos-13-owner-refresh/verification.json). Detailed logs: [authority](../output/loopsos-13-owner-refresh/authority.log), [UI](../output/loopsos-13-owner-refresh/ui-unit.log), [evaluation browser](../output/loopsos-13-owner-refresh/browser.log), [enterprise browser](../output/loopsos-13-owner-refresh/enterprise-browser.log). Test totals are executions, not statistical trials or independent safety measurements. The authority suite's expected missing-OCI negative-test output is not a failed suite. Local test servers were temporary.

## Highest-priority current findings

### F12 — audit destination binding does not revoke old workers

**Observed, fresh local reproduction; P1.** Two independently opened SQLite connections share an outbox. The old dispatcher is configured for a retired destination; the new dispatcher uses another destination and key. After a new event is appended, the old worker drains first, sends to the old destination and marks the event delivered. The current worker sends nothing. Its current-target receipt correctly remains unverified, but the undesired old send has already occurred. [Raw result](../output/loopsos-13-owner-refresh/independent-baseline.json); [reproduction](../output/loopsos-13-owner-refresh/stale_worker_probe.py).

The dispatcher stores endpoint/key in process and uses only an instance asyncio lock. Receipt binding protects the reader from historical acknowledgments; it does not provide shared sending admission. The synthetic transport makes **zero real network calls**, so this proves a control defect, not an observed production disclosure. Likelihood and business loss are unknown.

**Repair and closure:** shared monotonic configuration epoch and destination/key binding; atomic durable send admission and configuration transition; a draining phase that prevents old admissions from starving rotation; exact attempt-token completion; epoch-bound receipts including A→B→A; stale writers cannot alter backoff; unknown/crashed attempts require evidenced reconciliation, never automatic expiry into authority. No database transaction should remain open across HTTP. Test separate processes/connections, rotation during a held send, restart, timeout/cancel, storage failure and old callback completion. Updated database rules cannot revoke a legacy binary that bypasses them: drain old binaries and revoke retained network/key authority separately. Previously emitted remote requests remain a separate sink concern.

**Accountability:** audit platform/operations owner; no named person or accepted exception supplied. Interim requirement is to drain/revoke old workers before relying on rotation. This report has not enforced that control on a deployment.

### F13 — release proof accepts an unapproved or absent check publisher

**Observed, fresh local reproduction; P1.** The real local webhook API receives correctly HMAC-signed synthetic check-run events matching the protected gate names, repository and commit. One case omits app/workflow origin; another explicitly names an unapproved synthetic app and workflow. Both releases initially require review. A separate authenticated Approver reviews the exact subject, and both then return GO. [Raw result](../output/loopsos-13-owner-refresh/attestor-results.json); [reproduction](../output/loopsos-13-owner-refresh/attestor_probe.py).

This does **not** demonstrate webhook signature forgery, stolen credentials, unauthenticated release or reviewer bypass. It demonstrates that event authenticity and a check name do not establish an approved test publisher/workflow. Source inspection of release_policy.py confirms requirement matching without a protected app/workflow eligibility check. A valid but inappropriate publisher can therefore supply apparently authoritative test claims. Actual exploitability depends on GitHub permissions and deployment configuration, which were not tested.

**Repair and closure:** bind eligible GitHub App/installation and workflow identity to server-owned policy, using actual provider-attested identity rather than trusting a newly caller-filled string. Reject missing/wrong publisher and replay across workflow/subject. Retain positive approved-publisher tests, compromised-approved-publisher residuals and separate review. CI/security owners must approve the trust policy. No risk acceptance has been supplied.

### Remaining enterprise blockers

Retention/restore across derivatives and providers, real OIDC/Postgres/RLS, observed broker and egress enforcement, durable external audit storage, model/vendor truth and revocation, business outcome thresholds, staffed recovery and organizational second-line challenge remain open. Scanner/advisory coverage is incomplete. These are evidence gaps with possible material consequences, not zero-risk findings and not all proven software vulnerabilities. The current [20-record risk snapshot](../output/loopsos-13-owner-refresh/risk-register.json) preserves the earlier nineteen records and adds F13. Earlier local repairs are not relabeled as full enterprise closure.

## Thirteen-owner disposition matrix

| Owner | Discipline | Current disposition |
| --- | --- | --- |
| 0 | Enterprise AI discovery | PARTIAL — deployed discovery unverified |
| 1 | AI quality and complete business outcomes | PARTIAL — local correctness; business quality unknown |
| 2 | LLM assurance | PARTIAL — provenance and egress controls pass locally |
| 3 | Agentic assurance and consequential effects | PARTIAL / OPEN DEFECT — retired anchor workers retain sending ability |
| 4 | Frontier-model assurance | UNPROVEN — frontier campaign not executed |
| 5 | Threat modeling and security architecture | PARTIAL — local controls tested; scanner and host coverage incomplete |
| 6 | Cryptographic and quantum-safe assurance | UNPROVEN — no enterprise crypto inventory or quantum-safe proof |
| 7 | Advanced capability and specification gaming | PARTIAL — metric gaming regressions; advanced behavior untested |
| 8 | Regulatory and governance assurance | BLOCKED — organizational/regulatory applicability not supplied |
| 9 | Data lifecycle, privacy and evidence custody | PARTIAL — honest deletion UX; full retention/restore unproven |
| 10 | Independent challenge and assurance integrity | BLOCKED — institutional independence not established |
| 11 | Vendor, dependency and supply-chain assurance | UNPROVEN — dependency and provider assurance incomplete |
| 12 | Human oversight and operational recovery | PARTIAL — local oversight UI; operational effectiveness unknown |

## Detailed owner assessments

### Owner 0 — Enterprise AI discovery

**Current verdict:** PARTIAL — deployed discovery unverified. **Priority:** P1 admission.

**Skill and catalog cases:** `enterprise-ai-discovery`; `DISCOVERY-ROUTES`, `DISCOVERY-COMPOSITION`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Graphify source manifest; corpus validation; selected-pilot verifier; configuration preflight.

**Skill:** `enterprise-ai-discovery`. **Disposition: local scope established; enterprise inventory incomplete.**

The inspected system includes React intake and workspace flows, deterministic recommendations, optional LLM field/question assistance, document/voice handling, FastAPI authority, durable execution, connector ingestion, release review and proof export. These are actual product surfaces, not the assurance skills' reference implementation. Existing architecture, configuration and corpus records were traced before selecting repairs.

The repair is tied to one parent run and one engine. All original findings, external prerequisites and the DNS hypothesis remain represented. Additional defects discovered during challenge are linked to their originating risk: extra release declarations, stale review overwrite, evidence supersession, fixture-key trust, policy drift and F10 sensitivity downgrade.

**Residual exposure:** no named production target, legal entity, authoritative enterprise inventory, accountable people or approved risk profile was supplied. Optional endpoints, organizational integrations and shadow workflows therefore remain unknown. Repository discovery does not establish the absence of shadow AI.

**Acceptance:** the product owner must provide actual workflows, data classes, tenants, dependencies, autonomy/effect scope and accountable owners. Reconcile deployed routes and services against that inventory, then repeat applicable owner gates for the exact deployment. Reopen on a new endpoint, model route, data source, workflow or authority expansion.

**Red-team extension and uncertainty:** A trusted SaaS adds an undisclosed subprocessor or model; several draft-only helpers combine into an unattended consequential workflow. These are untested deployed hypotheses, not discovered shadow assets.

**Required blue-team work:** Reconcile actual identity, endpoint, procurement, network and runtime inventories. Seed an unregistered route in an authorized staging target and verify detection. Record model/prompt/tool/data/tenant/region and end-to-end autonomy.

**Exact closure condition:** Named product owner signs the deployed inventory; seeded route detection meets a preapproved interval; no required dependency has an unexplained scope or owner.

**Linked risk records:** F06, E01. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 1 — AI quality and complete business outcomes

**Current verdict:** PARTIAL — local correctness; business quality unknown. **Priority:** P1 before business reliance.

**Skill and catalog cases:** `enterprise-ai-quality`; `QUALITY-DENOMINATOR`, `QUALITY-CUMULATIVE`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Full UI, authority and browser suites; protected release denominator and missing-artifact regression tests.

**Skill:** `enterprise-ai-quality`. **Disposition: stronger local contract proof; business effectiveness unproven.**

The original five erroneous-GO scenarios were preserved as failures and regression inputs. Protected requirements prevent the caller from shrinking the denominator. Missing, optional, stale, unbound or contradictory evidence cannot count as satisfying a required check. Independent challenge additionally found that an extra declared requirement could be ignored; the supported policy now rejects unsupported declarations instead of silently omitting them.

The browser journey creates signed local checks, records a release, authenticates a separate reviewer, approves it and then records a rejection. It validates the actual authority response rather than mocking the review endpoint. This demonstrates reachable positive and negative paths under the local contract.

**Residual exposure:** a successful check with a trusted signature may still be a poor test, have a compromised publisher or use an invalid business oracle. There are no approved enterprise outcome denominators, representative business cases, loss limits or measured effectiveness targets. Passing a software suite does not establish business value or acceptable harm.

**Acceptance:** domain and product owners approve complete task populations, thresholds, failure costs and observation windows; an independent collector retains every trial, timeout, abstention and repair. Evaluate successful completion and downstream effects, not only model answer quality. E05 remains open.

**Red-team extension and uncertainty:** The system looks more accurate by refusing difficult work, excluding timeouts or accepting a validly signed weak test. Small accepted errors accumulate into cohort harm. No customer population was measured.

**Required blue-team work:** Create an independently sourced intake denominator with success, failure, abstention, timeout, rework and delayed harm. Evaluate cohorts and workload, not only average answer quality. Include performance, accessibility and recovery objectives.

**Exact closure condition:** Domain owner approves task population, labels, loss limits and observation window before trials; retained outcomes meet those limits with uncertainty reported.

**Linked risk records:** F01, F04, F09, E05, F13. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 2 — LLM assurance

**Current verdict:** PARTIAL — provenance and egress controls pass locally. **Priority:** P1 before enabling live AI.

**Skill and catalog cases:** `enterprise-llm-assurance`; `LLM-PROVENANCE`, `LLM-DISCLOSURE`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** llmProvenance, fieldProposal, secureRequest and questionAssistant unit tests; local intercepted LLM browser journeys.

**Skill:** `enterprise-llm-assurance`. **Disposition: F06 gateway binding repaired locally; live provider assurance incomplete.**

The new verifier binds output to exact request bytes and configured route/model/prompt identity. It rejects unsigned claims, tampering, wrong request/nonce, identity or prompt substitution, invalid timestamps and expired claims. Trust is compiled configuration; neither a response nor a window override can supply signing keys. Independent probes found and repaired published-fixture-key acceptance and an enterprise timeout override.

Consent and sensitivity remain separate authorization checks. F10's downgrade reproduction and browser negative establish that untrusted source text cannot lower the saved classification at the external field-structuring boundary. Deterministic fallbacks remain available when attestation fails.

**Residual exposure:** these tests use synthetic signatures, not a live gateway or provider. A trusted compromised gateway can sign false provider/model statements. Historical imported provenance is not automatically reverified. Trust revocation requires rebuild/reload; old tabs and caches may retain an old pin. There is no claim of measured hallucination, jailbreak, disclosure or semantic accuracy rates.

**Acceptance:** a model/platform owner supplies protected gateway custody, observed provider adapter evidence, approved prompt/revision mapping, revocation and fallback drills, and a bounded representative adversarial campaign. Retain uncertainty and failed trials. Newer models remain candidates until these gates pass.

**Red-team extension and uncertainty:** A compromised gateway signs false route claims; poisoned sources appear independent; cumulative disclosures reconstruct a secret across sessions; source text attempts sensitivity downgrade. Only the local contract and downgrade regressions are exercised here.

**Required blue-team work:** Run a consented synthetic-secret campaign across languages, documents, turns and fallback routes. Observe gateway-to-provider execution, key revocation in old tabs, request/response binding, and actual data-use terms. Track campaign-wide disclosure.

**Exact closure condition:** Protected provider adapter observations and representative campaigns satisfy approved bounds; revoked pins fail in active consumers; all eligible fallbacks pass the same controls.

**Linked risk records:** F06, E05, F10. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 3 — Agentic assurance and consequential effects

**Current verdict:** PARTIAL / OPEN DEFECT — retired anchor workers retain sending ability. **Priority:** P1 code repair before rotation reliance.

**Skill and catalog cases:** `enterprise-agentic-assurance`; `AGENT-AUTHORITY`, `AGENT-RESTART`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Effect-budget concurrency/restart/cancel/unknown-outcome tests; authority execution tests; fresh two-connection stale audit-worker reproduction.

**Skill:** `enterprise-agentic-assurance`. **Disposition: durable local effect enforcement added; enterprise exposure acceptance incomplete.**

F07 is integrated into `ToolRegistry.execute_action`, using the same authority store. A protected policy declares tenants, exact method/endpoint mappings, units, ceilings and reviewed measurement references. Integer currency minor units require explicit amount and currency paths. Missing tenant/route policy denies an external action. Safe local record actions remain distinct.

Reservations precede dispatch and cover multiple runs. Tests exercise independent database connections, races, restart, fencing, unknown responses, cancellation and compensation charging. A lost response after possible provider commitment keeps exposure reserved; it cannot expire into another dispatch. Cancellation before dispatch may release a reservation; stopping after dispatch is not reversal. Compensation has its own charge and cannot silently refund the original effect.

Independent challenge found policy changes did not invalidate an old reservation. A durable monotonic policy epoch/hash now fences changed policy, stale workers and old unsent reservations. The active epoch is checked inside the transaction before dispatch. Unknown-outcome handling also must avoid a misleading automatic ROLLED_BACK state.

**Residual exposure:** route measurements are trusted deployment policy and may be wrong or incomplete. A count ceiling is not a universal loss bound; a per-tenant ledger is not a cross-company shared-risk model. Production Postgres locking/RLS, live provider duplicate semantics, actual refunds and human reconciliation remain unproven. The trusted reconciliation seam is not an implemented organizational help desk or approval workflow.

**Acceptance:** platform/security/business owners approve actual exposure mappings and ceilings, deploy the reviewed database migration, and run provider commit/lost-response/duplicate/late-worker/compensation drills on an authorized target. Retain uncertainty and observed business consequences. F07 remains PARTIAL for enterprise acceptance.

**Red-team extension and uncertainty:** Old worker wins a shared outbox event after rotation. A separate risk is confusing cancelled local work with a reversed remote effect. Passing tool-budget fencing does not establish audit-worker fencing.

**Required blue-team work:** Implement shared monotonic configuration epochs, durable attempt admission and draining, exact-token completion and explicit orphan reconciliation. Serialize activation/admission without a database lock across HTTP. Deny stale writers from changing retries. Bound remote effects by measured business units.

**Exact closure condition:** Two-process races, A-to-B-to-A rotation, restart, cancellation, crash, stale finish and starvation tests pass; old binaries are drained or externally revoked; remote unknown outcomes remain reserved until evidenced reconciliation.

**Linked risk records:** F07, E02, F11, F12. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 4 — Frontier-model assurance

**Current verdict:** UNPROVEN — frontier campaign not executed. **Priority:** P1 before model promotion.

**Skill and catalog cases:** `enterprise-frontier-assurance`; `FRONTIER-CUES`, `FRONTIER-GOAL`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Source review of model identity/prompt/request binding and fail-closed fallbacks; no live frontier model trials.

**Skill:** `enterprise-frontier-assurance`. **Disposition: applicable because capability is unknown; behavioral campaign not executed.**

Model identity evidence is now more useful for tracking change, but no frontier model was exercised. The repair does not automatically discover, install or promote newer models. A provider alias can hide routing changes; a gateway-signed revision still requires trusted adapter evidence.

Required campaigns include long-horizon behavior, altered oversight cues, resumed tasks, impossible authorized goals, bounded help-seeking, fallback degradation and candidate-versus-baseline comparison. Evaluate the complete system bundle: model, prompts, tools, memory, policy, data and monitor. Do not let test-context claims unlock real endpoints.

**Residual exposure:** unknown capabilities, adaptive behavior, evaluation contamination, monitor failure and correlated model/judge weaknesses remain unknown. Finite tests cannot certify absence of hidden capabilities or intent.

**Acceptance:** model and independent assurance owners approve dated capability evidence, representative private tests, fixed regressions, resource bounds and promotion/rollback rules. A recommendation expires on material model/provider/system changes or its review deadline; freshness alone is not sufficient proof of improvement. E05 remains open.

**Red-team extension and uncertainty:** The same alias changes capability through tools, context, routing or inference settings; evaluation cues change behavior; an impossible goal encourages unauthorized scope expansion. Behavioral differences do not by themselves prove deception.

**Required blue-team work:** Compare complete old/new system bundles on protected holdouts, randomized evaluation cues and longer resumed tasks. Include impossible authorized goals, refusal, help, budget exhaustion and independent stop points.

**Exact closure condition:** Bounded capability-delta evidence, unexplored regimes and uncertainty reviewed by accountable model/risk owners. A new model is promoted only after affected gates pass; age out evidence after material change.

**Linked risk records:** F06, E05. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 5 — Threat modeling and security architecture

**Current verdict:** PARTIAL — local controls tested; scanner and host coverage incomplete. **Priority:** P1 security closure.

**Skill and catalog cases:** `enterprise-ai-threat-modeling`; `THREAT-COMMON-CAUSE`, `THREAT-CAMPAIGN`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Release integrity/review, connector transport, outbox integrity, authentication and tenant-boundary tests; targeted stale-worker counterexample.

**Skill:** `enterprise-ai-threat-modeling`. **Disposition: reproduced decision attacks addressed in local repair; security coverage degraded.**

The principal attack chain was authenticated Operator input → apparently valid gate/evidence claims → durable record → erroneous GO/proof pack. The repair moves requirement derivation, evidence checking and reviewer authority to server-controlled boundaries. Independent tests deliberately attack omissions and the decision system itself, rather than checking only familiar prompt-injection strings.

Additional challenge exposed a stale approval overwriting a later veto and newer adverse evidence being absent from producer-selected evidence IDs. Those cases are retained as independent reproductions and tracked in the release repair. A trusted signature authenticates an origin under its key; it does not establish that the signed content is safe.

**Coverage limitation:** local Semgrep was attempted with local rules and metrics disabled but failed before scanning because the Windows certificate store could not initialize. Gitleaks was unavailable. Focused source review and retained secret-pattern checks are limited substitutes, not full SAST or secret-scan coverage. The pending npm advisory query was not retried through another route.

**H01 follow-up:** Independent deterministic tests reproduced unpinned DNS-to-socket routing and ambient proxy substitution. The connector now validates complete DNS answers at connection time and dials a checked numeric address with the original TLS hostname. Local independent closure passed; hosted TLS/routing and independently enforced egress remain unproven. See the [repair addendum](LOOPSOS_CONNECTOR_EGRESS_REPAIR_2026-09-21.md).

**Acceptance:** security/network owners supply an authorized test target, working scanner environment and deployed egress evidence. Exercise compromised reviewer/collector, signed malicious input, trust revocation, cross-workflow composition and host-boundary failures. Preserve open paths and operational restrictions explicitly.

**Red-team extension and uncertainty:** Compromised authorized signer, identity outage, shared reviewer or database administrator defeats multiple controls together. OIDC/JWKS networking and mixed-policy deployments require separate review; an untested path is not a proven exploit.

**Required blue-team work:** Complete a working SAST/secret/advisory scan; pin eligible CI attestor app/workflow identities; review every outbound client; test DNS/proxy/TLS and approved host network controls. Inject shared dependency failures and reconcile aggregate risk.

**Exact closure condition:** Each attack path has prevention/detection evidence or explicit bounded residual treatment; real egress and identity boundaries are observed; all required scanners produce retained results.

**Linked risk records:** F01, F02, F03, F04, F05, F07, E02, H01, F10, F11, F12, F13. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 6 — Cryptographic and quantum-safe assurance

**Current verdict:** UNPROVEN — no enterprise crypto inventory or quantum-safe proof. **Priority:** P1 key lifecycle; risk-based quantum migration.

**Skill and catalog cases:** `enterprise-quantum-safe-assurance`; `CRYPTO-PATHS`, `CRYPTO-REPLAY`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Classical session, webhook, evidence binding and browser P-256 verifier regressions. Historical audit-binding tests do not revoke an active worker.

**Skill:** `enterprise-quantum-safe-assurance`. **Disposition: local classical mechanisms exercised; cryptographic enterprise inventory incomplete.**

Existing authority mechanisms include signed sessions, pinned OIDC algorithms, content/audit hashes and signed anchor delivery. The LLM change adds P-256 verification and explicit fixture-key isolation. Hashes identify local source/evidence bytes; they are not protected enterprise attestations by themselves.

**Residual exposure:** no complete cryptographic bill of materials, key custody record, live rotation/revocation proof, backup confidentiality assessment, downstream TLS observation or post-quantum migration evidence was supplied. Browser trust pins require rebuilding/reloading to change. A compromised authorized key remains powerful until effective revocation reaches every consumer.

**Acceptance:** the cryptography/security owner approves an inventory of confidentiality/authenticity paths, owners, algorithms, retention horizons, lifetimes and dependent vendors. Test key retirement, wrong issuer/audience, downgrade, rollback to revoked packages, exports and backups. E06 remains open; no quantum-safe claim is made.

**Red-team extension and uncertainty:** A valid retired key or old package restores authority; strong ingress hides weak exports/backups; an old key retained by an old process remains usable. Algorithm presence is not a complete crypto posture.

**Required blue-team work:** Build a cryptographic inventory covering transport, sessions, database, backups, exports, signatures and vendors; document confidentiality lifetimes, custody and approved algorithms. Test retirement, rotation, downgrade and recovery with real consumers.

**Exact closure condition:** Security/cryptography owner approves the inventory and migration rationale; key compromise/retirement drills pass across all consumers; residual vendor paths remain explicit.

**Linked risk records:** E02, E06. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 7 — Advanced capability and specification gaming

**Current verdict:** PARTIAL — metric gaming regressions; advanced behavior untested. **Priority:** P1 before expanded autonomy.

**Skill and catalog cases:** `enterprise-advanced-capability-assurance`; `ADVANCED-OMISSION`, `ADVANCED-COORDINATION`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Protected gate omission, contradictory decision, adverse-evidence supersession and policy-revocation tests.

**Skill:** `enterprise-advanced-capability-assurance`. **Disposition: concrete grading and policy-drift attacks tested; broader advanced behavior unknown.**

The original gate-omission bug and later extra-requirement omission are concrete ways to optimize a reported score without satisfying the requirement. Contradictory decisions, stale veto overwrite and selective evidence reveal why the grader and manifest must be outside the candidate's authority. The budget epoch challenge similarly tests whether old authority survives a new restriction.

These failures require no claim about model intent. They are observable control weaknesses available to either a human or a capable agent. Repairs should be judged by denied unauthorized effects and correct records, not persuasive explanations or model self-reports.

**Residual exposure:** no production multi-agent coordination system, agent memory service or advanced autonomy campaign was exercised. Collusion, shared artifacts, memory compaction losing restrictions, repeated small effects and hidden failed trials require actual architecture and bounded targets. Local cancellation is not proof that a remote effect was reversed.

**Acceptance:** freeze the trial denominator, authorization hierarchy, budgets and independent observation. Test random interruption/resumption, impossible goals, cross-agent artifact poisoning and composed actions where applicable. Distinguish untested hypotheses from reproduced defects. Do not claim corrigibility certification.

**Red-team extension and uncertainty:** Agents coordinate through shared artifacts to create a prohibited end state; failed attempts disappear from a summary; memory compaction drops a restriction. No claim of observed collusion or strategic model intent is made.

**Required blue-team work:** Freeze denominators and grading outside candidate authority. Test cross-agent artifacts, random-point interruption, correction after restart, and composed permitted actions. Reconcile intake and effect ledgers against all reported outcomes.

**Exact closure condition:** Observable prohibited effects are denied under the declared campaign; failed and omitted trials reconcile; independent challenge records limits and vetoes. No universal corrigibility claim.

**Linked risk records:** F01, F05, F07, E05. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 8 — Regulatory and governance assurance

**Current verdict:** BLOCKED — organizational/regulatory applicability not supplied. **Priority:** P1 enterprise admission.

**Skill and catalog cases:** `enterprise-ai-regulatory-assurance`; `REGULATORY-LINEAGE`, `REGULATORY-COMPOSITION`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Authenticated subject-bound release review, no-waiver floor, retained exception history, pilot and configuration checks.

**Skill:** `enterprise-ai-regulatory-assurance`. **Disposition: technical decision lineage improved; organizational admission remains NO_GO.**

Authenticated review and retained exception history improve the meaning of a release record. No-waivers means unresolved risk cannot acquire authorization through a caller's status field. Review identity is derived from an authenticated session, but a distinct user ID is only a technical separation rule; it is not proof of organizational independence.

The fresh selected-pilot verifier still reports NO_GO. Eleven selected descriptors remain DRAFT, with missing accountable owners, evidence locations/policies, metric targets or approved golden fixtures. Local production configuration likewise remains NO_GO and hosted handover NOT_PROVEN. These are evaluation-environment results, not accusations about an uninspected deployment.

**Residual exposure:** entity, jurisdiction, regulated role, notices, contestability, legal holds and approved risk appetite remain unresolved. This report makes no legal compliance determination and invents no law-specific deadline.

**Acceptance:** legal/risk/product owners approve effective-dated obligations and an enterprise profile, bind named people and permitted scope, and review residual risks. Reassess on material product, model, data, vendor or regulatory change. E01 and E04 remain open.

**Red-team extension and uncertainty:** An apparently compliant notice describes a different executed model or data policy. Assistants compose into a consequential regulated workflow. A retention figure copied from a framework is treated as law without applicability review.

**Required blue-team work:** Identify actual entities, jurisdictions, users and decisions; obtain effective-dated obligation mapping and qualified interpretations. Bind notices, contestability, holds and non-waivable constraints to executed lineage. Resolve the document's regulatory assertions with primary sources before adopting them.

**Exact closure condition:** Authorized legal/risk owners approve applicability, remaining interpretations, risk appetite and operating scope. No legal certification is inferred from technical passes.

**Linked risk records:** F02, F03, F04, F05, F08, E01. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 9 — Data lifecycle, privacy and evidence custody

**Current verdict:** PARTIAL — honest deletion UX; full retention/restore unproven. **Priority:** P1 before sensitive data.

**Skill and catalog cases:** `enterprise-ai-data-lifecycle`; `DATA-RESURRECTION`, `DATA-CONTAMINATION`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** WorkspaceStore and deletion-dialog tests, real local UI persistence/retry flows, classification egress regressions and outbox-integrity tests.

**Skill:** `enterprise-ai-data-lifecycle`. **Disposition: F10 egress downgrade repaired locally; F08 retention lifecycle PARTIAL.**

Deletion explicitly distinguishes browser draft removal from an authority request. The confirmation lists retained related records and copies, and acknowledgment resets when the workspace or storage boundary changes. Cancellation preserves data. The empty-state UI keeps authority persistence failure and retry visible.

This addresses a misleading deletion promise, not enterprise erasure. The earlier observation that a deleted workspace's release proof remains retrievable is retained. Such retention may be required; its legitimacy depends on an approved records policy. No audit evidence was destroyed to create a superficial deletion pass.

**Residual exposure:** derivatives, caches, downloaded exports, backups, stale synchronization, provider records, legal holds and restored snapshots need explicit policy and tests. No live Postgres restore or provider deletion proof exists. Classification checks do not detect all sensitive material mislabeled by an authorized user.

**Acceptance:** a named data/records owner supplies retention and hold rules plus an inventory of derivatives. Use synthetic canaries to test purge, intentional retention, tombstones, restoration and access revocation against those rules. Preserve retained material's purpose, scope, access and expiration. F08 remains PARTIAL.

**Red-team extension and uncertainty:** Deleted data returns from backup, stale client, summary or export; product decisions become training truth while rejected users vanish from evaluation; retained evidence itself leaks confidential content.

**Required blue-team work:** Map derivatives and copies; define lawful retention/hold policy and access boundaries. Use synthetic canaries for purge, intended retention, restores and stale sync. Keep protected independent holdouts and raw/redacted lineage.

**Exact closure condition:** Records/privacy owner approves each retained class and expiry; canaries demonstrate correct deletion or authorized retention across declared stores and restore paths; provider-unobservable paths stay flagged.

**Linked risk records:** F08, E02, F10, F11, F12. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 10 — Independent challenge and assurance integrity

**Current verdict:** BLOCKED — institutional independence not established. **Priority:** P1 before enterprise acceptance.

**Skill and catalog cases:** `enterprise-ai-independent-challenge`; `CHALLENGE-INDEPENDENCE`, `CHALLENGE-COMPLETENESS`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Fresh result/log/source hashes; duplicate-test disclosure; preserved failed history; separately authored stale-worker reproduction. All local processes share one host/trust environment.

**Skill:** `enterprise-ai-independent-challenge`. **Disposition: substantive local independent challenge; institutional independence absent.**

Separately assigned reviewers found defects after implementation tests passed: public fixture-key acceptance, classification downgrade, untested extra release requirements, changed budget policy, stale review overwrite and adverse evidence supersession. Each finding retains its reproduction and correction history. Positive local results do not erase those failed attempts.

The release review records an authenticated user, exact subject/policy/evidence and an append-only event. Evidence digests and evaluator identity age out stale bindings. The UI cannot manufacture an organizational approver by displaying a generated name. Exact operation retries preserve later vetoes.

**Residual exposure:** all local agents share the same workspace and trust environment. Reviewers who subsequently patched a finding are not counted as independent reviewers of their own correction. A protected enterprise collector, organizational second-line signer and approved trust/revocation configuration were not supplied. Mixed evaluator versions during a rolling deployment need an enforced rollout boundary; startup source hashes alone do not establish cluster-wide active-policy revocation.

**Acceptance:** an independently administered second line repeats the final counterexamples against the exact deployed subject, reconciles the complete trial/risk/waiver/repair manifest and issues a bounded challenge decision. Preserve conflicts, common dependencies and vetoes. No ENTERPRISE receipt is forged from local fixture keys. E04 remains open.

**Red-team extension and uncertainty:** Producer controls case selection, collector key, grader and report; valid signatures conceal weak tests or excluded failures; policy versions coexist across a rolling deployment. Different model personas do not remove that common control.

**Required blue-team work:** An organization-controlled second line receives raw artifacts and the complete case/risk/repair manifest. Protect collector, holdouts, signing, time and revocation independently of the assessed product. Test candidate attempts to alter the evaluator.

**Exact closure condition:** A distinct authorized organization-owned principal challenges the exact deployed subject, records common dependencies and unresolved vetoes, and issues a time/scoped decision. Local fixtures cannot satisfy this.

**Linked risk records:** F01, F02, F03, F04, F05, E04, F10, F11, F12, F13. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 11 — Vendor, dependency and supply-chain assurance

**Current verdict:** UNPROVEN — dependency and provider assurance incomplete. **Priority:** P1 supply chain and provider activation.

**Skill and catalog cases:** `enterprise-ai-vendor-assurance`; `VENDOR-ROUTES`, `VENDOR-CORRELATION`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Lockfile/source capture, local build, configured gateway-route validation and fleet parity. No fresh external vulnerability advisory submission or live provider call.

**Skill:** `enterprise-ai-vendor-assurance`. **Disposition: local source/configuration boundaries strengthened; current external evidence incomplete.**

No new third-party package was needed for these repairs. Provider/model identity now has a signed local contract, but actual gateway/vendor behavior remains an external prerequisite. Source and log digests support reproducibility of this working tree; they are not a protected build provenance chain for a deployed image.

**Residual exposure:** the current npm advisory result is unknown. Automatic approval review rejected submission of package metadata to the external registry; authorization remains pending and no alternative transmission was used. Actual release SBOM, image scanning, artifact attestations, vendor contractual controls, training/retention terms and exit exercises remain absent.

**Acceptance:** procurement/security/platform owners supply an approved advisory path and actual release artifact inventory, protected build attestations, vendor route/retention commitments clearly labeled as contractual evidence, and tested fallback/exit plans. Reopen for advisory, route, signing-key, dependency or vendor-term changes. E03 remains open.

**Red-team extension and uncertainty:** Primary/fallback share an underlying provider, region, identity service or failure mode. Signed tools carry malicious behavior. A stable URL hides a changed route. A successful build is mistaken for a clean dependency scan.

**Required blue-team work:** Obtain an approved advisory scan and exact release SBOM/image provenance; verify allowed attestor identities, dependency concentration, vendor route/region/retention terms, fallback quality and exit strategy. Separate contract claims from observed behavior.

**Exact closure condition:** Retained approved scan results, protected build/attestor evidence and actual provider-route/fallback drills cover the intended deployment. Unknown vendor internals remain disclosed.

**Linked risk records:** F06, E03, F13. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

### Owner 12 — Human oversight and operational recovery

**Current verdict:** PARTIAL — local oversight UI; operational effectiveness unknown. **Priority:** P1 before unattended operation.

**Skill and catalog cases:** `enterprise-human-ai-operations`; `HUMAN-REVIEW`, `HUMAN-RECOVERY`. Both case families remain visible; local coverage below is not ENTERPRISE completion.

**Fresh local coverage:** Desktop/mobile approval, rejection, stale confirmation, error/retry and enterprise-admission browser cases; queued execution and kill-switch contracts.

**Skill:** `enterprise-human-ai-operations`. **Disposition: local workflows improved; staffed operations and recovery unproven.**

F09 repaired the enterprise test launcher and readiness fixtures while preserving the fail-closed production parser. Tests can now reach their intended binding, queued-work and retry assertions. The new aggregate-effect readiness field is required rather than silently ignored. These fixtures simulate readiness; they do not provision a broker, database or on-call team.

The release-review UI shows concrete evidence and requires a meaningful rationale and current acknowledgment. Mobile tests check usable layout. Deletion failure remains visible. Unknown remote outcomes must remain explicit and avoid automatic success/rollback claims. These changes reduce misleading operational signals.

**Residual exposure:** there has been no representative reviewer workload study, screen-reader certification, on-call notification delivery, deputy handoff, real break-glass drill, live restore or customer-remediation exercise. A skill's help packet is not delivered help, and a NO_GO report does not remotely disable a running deployment.

**Acceptance:** operations owners establish staffed escalation, authorized delivery adapters, acknowledgement/retry/dead-letter behavior, response limits and actual incident/restore drills. Measure stop latency and customer correction separately from worker shutdown. E02 and E05 remain open.

**Red-team extension and uncertainty:** Correct early suggestions train reviewers to miss later harm; no responder is on call; the agent stops but customer effects continue; a draft help request is mistaken for delivery. None of these human outcomes was measured here.

**Required blue-team work:** Conduct representative accessible workload drills with seeded errors, deputies and absent responders. Verify delivery/acknowledgement/retry/dead-letter handling, measured stop latency, restore, incident command and customer correction.

**Exact closure condition:** Named staffed owners accept response and recovery objectives with observed drills; queued/remote effects reconcile; customer correction is measured separately from shutdown. Calendar review dates must be assigned by accountable people.

**Linked risk records:** F02, F09, E01, E02, E05, F11, F12. Accountable roles are assigned in the risk snapshot; named people and calendar deadlines remain unsupplied. No silence or elapsed time counts as acceptance.

## Remediation and enterprise verification sequence

1. **Close locally reproducible authority gaps:** F12 shared audit-worker fencing and F13 approved check publisher/workflow identity. Preserve these reproductions as regressions, add meaningful positive controls, and obtain separately authored challenge of the final candidate. Do not weaken the required evidence denominator.
2. **Complete security coverage:** working SAST and secret scanner; approved dependency advisories; exact release SBOM/image attestations. Review OIDC/JWKS outbound transport separately from the guarded tool/anchor client. Treat mixed evaluator versions and stale consumer trust as explicit rollout/revocation concerns.
3. **Admit a named enterprise target:** organization profile, actual tenants/workflows/data classes, risk bounds, permitted effects, named owners/deputies and independently administered trust. Keep the eleven pilot descriptors DRAFT until their real prerequisites exist.
4. **Exercise hosted infrastructure:** Postgres tenant/RLS/migration and backup restore, two real OIDC tenants, broker lease lifecycle, worker scheduling/heartbeats, network isolation, immutable audit sink and break-glass. Static migration checks cannot replace those observations.
5. **Exercise AI and business outcomes:** exact provider/model/prompt/context/tool bundle; independent holdouts; complete trial denominator; multi-turn/multimodal disclosure and impossible-goal campaigns; representative outcome/cohort/human workload measurement; safe fallbacks and provider unknown-outcome reconciliation.
6. **Finish data and operations proof:** policy-owned retention/holds, synthetic deletion/restore canaries across derivatives, authorized help delivery and dead-letter handling, staffed containment/restore/customer remediation.
7. **Obtain independent acceptance:** second line verifies the exact final source/build/config/model/prompt/tool/data subject plus every risk, failure, repair and waiver. Material changes invalidate affected evidence. A readiness decision still does not authorize deployment.

No hosted credentials, policy decisions, organizational people or delivery receipts are fabricated to satisfy these steps. Unavailable prerequisites should produce a help packet with requested artifact, accountable recipient, impact, interim restriction and due date. Sending it requires an authorized adapter; a drafted packet remains undelivered. This assessment drafted no third-party messages.

## Staying current as models and standards change

The reference check on 21 September 2026 confirmed that the current OWASP LLM project points to its **2026** edition, alongside the Agentic Applications Top 10 2026. Treat references that stop at the 2025 LLM list as an update candidate. This is a reference freshness observation, not a completed item-by-item conformance mapping. [OWASP current release](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/), [Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/).

OWASP's Agent Control Standard resource, dated September 1, 2026, describes runtime middleware hooks and portable policy enforcement. It is relevant when assessing where LoopsOS actually prevents an agent effect. This assessment does not establish ACS implementation or certification. [Official ACS resource](https://genai.owasp.org/resource/agent-control-standard-acs/).

NIST's Generative AI Profile and 2025 adversarial-machine-learning taxonomy are useful risk and attack references. They do not provide a product-specific assurance verdict. The concrete failures and proposed scenarios here derive from LoopsOS code, tests and the thirteen owner methods; they are not claims of exhaustive standards coverage. [NIST AI RMF resources](https://www.nist.gov/itl/ai-risk-management-framework/ai-risk-management-framework-resources), [NIST AI 100-2e2025](https://www.nist.gov/publications/adversarial-machine-learning-taxonomy-and-terminology-attacks-and-mitigations-0).

Maintain a versioned provider/model capability registry with observed model/revision, route, prompt, tools, inference configuration, context/data and safety policy. Record dated primary sources and approved evidence lifetimes. Trigger reassessment on capability, permissions, model route, prompts, data/jurisdiction, provider terms, evaluator, key or deployment changes—even if the marketing model name is unchanged. Compare candidate and current bundles on protected business/security holdouts; retain regressions, uncertainty and all attempted trials. Stage promotion with measured rollback/stop criteria and independently verified enforcement. A newer model should become a candidate automatically; production trust should follow evidence and authorization.

No recurring monitor or scheduler was installed by this assessment. Skills and finite ticks are not a daemon. The operating owner must provide an actual scheduler, heartbeat supervision and authorized help transport before claiming continuous assurance.

## Limits, retained evidence and reproduction

All thirteen areas were evaluated for applicability, local coverage, residual exposure and closure. This does not mean every recommended adversarial campaign was executed. No long-horizon live model test, provider deletion/retention verification, representative human fatigue study, screen-reader certification, statistically powered fairness/outcome study, hosted chaos drill or quantum migration test is claimed. No finite suite establishes universal safety or absence of unknown failure modes.

Earlier scanner attempts are inherited gaps: Semgrep failed during certificate-store initialization, gitleaks was unavailable, and the dependency-advisory query did not complete. Those scanners were not freshly rerun here. Automatic approval review previously rejected external submission of package names/versions; that submission was not retried or routed elsewhere. The current advisory status therefore remains unknown.

The prior [baseline assessment](LOOPSOS_13_OWNER_ASSESSMENT_2026-09-20.md), [repair assessment](LOOPSOS_13_OWNER_REPAIR_ASSESSMENT_2026-09-21.md), [connector addendum](LOOPSOS_CONNECTOR_EGRESS_REPAIR_2026-09-21.md) and [anchor addendum](LOOPSOS_AUDIT_ANCHOR_REPAIR_2026-09-21.md) remain unchanged. Their older counts describe earlier snapshots. This report's fresh execution table controls the current local testing claim.

Reproduction uses the pinned local runtime recorded in each receipt and `output/loopsos-13-owner-refresh/run_checks.py <check-name>`. Available names used here are authority, ui-unit, browser, enterprise-browser, typecheck, build, design, corpus, fleet, production and pilot. Run browser modes sequentially because they share loopback ports 4373/9287. The two targeted probes are standalone Python scripts in the same directory and use only synthetic/local inputs. Preserve the existing output directory before rerunning; exact raw logs and hashes identify this report's run.

The report recommends restrictions; it does not remotely stop an existing deployment. The final operational conclusion remains **NO_GO for enterprise production reliance until the applicable code and evidence blockers are resolved and independently accepted.**
