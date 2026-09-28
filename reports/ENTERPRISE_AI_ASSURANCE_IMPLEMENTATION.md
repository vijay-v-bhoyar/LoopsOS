# Enterprise AI assurance implementation

Implementation date: 2026-09-20. Enterprise loop/owner packages: 1.0.0. Lifecycle conductor and lifecycle policy: 1.1.0. Registry schema: skill-fleet/v2.

Lifecycle policy canonical JSON SHA-256: `436576de960e56410d114ecccbb654215b22146080dcff2e84936baaf55d43cf`.

The portable assurance implementation is installed. It provides one assessment loop, thirteen owner skills, a deterministic evidence verifier, persistent risk/repair records, bounded recovery contracts, and an executable lifecycle completion gate. **This is local implementation and fixture proof. Enterprise activation remains NO_GO until the named organization supplies and verifies its operational integrations and evidence.**

## Authoritative locations

- Registry: [skill-fleet/registry.json](../skill-fleet/registry.json). 118 registered skills. Registry file SHA-256: `1a3b198b8d6a6108ab0a3a8a194e86fc22039465ce724ee8782ba8ab732974b0`.
- Assessment entrypoint: [enterprise-ai-assurance-loop/SKILL.md](../skill-packages/enterprise-ai-assurance-loop/SKILL.md).
- Execution commands: [execution.md](../skill-packages/enterprise-ai-assurance-loop/references/execution.md).
- Owner routing and phase map: [SKILL_FLEET_LIFECYCLE_MAP.md](SKILL_FLEET_LIFECYCLE_MAP.md).
- Approved design: [ENTERPRISE_AI_ASSURANCE_13_OWNER_PLAN.md](ENTERPRISE_AI_ASSURANCE_13_OWNER_PLAN.md). Its earlier inventory digest is historical; use the registry above for this implementation.
- Verifier executable bundle SHA-256: `b0596d006dfc1853498c30a8173546d0ee6613e24b69f54cc848eea37159eabc`.

The 14 canonical enterprise packages live under skill-packages. Identical source-owned files are installed in both `C:/Users/vijay/.codex/skills/<skill-id>` and `C:/Users/vijay/.agents/skills/<skill-id>`. The existing Codex lifecycle installation is updated. Registry records pin entrypoint and package hashes and reviewed installed hashes. Distribution preserved mirror-only files and archived prior lifecycle trees and registry bytes under skill-fleet/backups/enterprise-*. A package replacement is staged and verified before rename; batch exceptions restore swapped trees. A process/host crash is not a distributed filesystem transaction—validate parity before resuming after an interrupted installation.

## Owner skills

| Owner | Installed skill | Primary responsibility |
| --- | --- | --- |
| 0 | enterprise-ai-discovery | Inventory AI dependencies, boundaries, hidden routes and composed autonomy. |
| 1 | enterprise-ai-quality | Business quality, subgroup outcomes, usefulness and deferral. |
| 2 | enterprise-llm-assurance | Grounding, context, instructions, leakage and model behavior. |
| 3 | enterprise-agentic-assurance | Authority, tool effects, retries, restart and cumulative exposure. |
| 4 | enterprise-frontier-assurance | Capability changes, evaluation sensitivity and long-horizon failure. |
| 5 | enterprise-ai-threat-modeling | Attack paths, trust boundaries and independent enforcement. |
| 6 | enterprise-quantum-safe-assurance | Cryptographic inventory, replay, agility and migration evidence. |
| 7 | enterprise-advanced-capability-assurance | Advanced capability and adversarial misuse exposure. |
| 8 | enterprise-ai-regulatory-assurance | Applicable duties, decision records and composed risk. |
| 9 | enterprise-ai-data-lifecycle | Provenance, retention, deletion and restoration boundaries. |
| 10 | enterprise-ai-independent-challenge | Independent challenge, evidence integrity and binding vetoes. |
| 11 | enterprise-ai-vendor-assurance | Provider dependencies, opaque routing and exit/fallback exposure. |
| 12 | enterprise-human-ai-operations | Human workload, intervention, monitoring and recovery. |

Each package includes a substantive owner method, evidence and unresolved-risk instructions, and three local oracle tests. The protected catalog has 26 initial cases with metric predicates. Those cases are a regression foundation; they are not an exhaustive Fortune 500 campaign or proof of actual model behavior. Product-specific approved campaigns, raw observations and valid human/domain oracles remain necessary.

## Implemented behavior

| Area | Executable implementation and boundary |
| --- | --- |
| Identity and admission | Closed JSON schemas, strict duplicate/nonfinite rejection, immutable subject/profile/verifier identity, thirteen applicability dispositions and one selected repair engine. Owners 4/7 share the frontier ON/UNKNOWN or autonomy >= 2 predicate. |
| Evidence | Ed25519 verification against operator-pinned trust; issuer role/scope, raw content hashes, complete declared trial sets, freshness, generation, current revocation and semantic case outcomes. A collector must truthfully attest the complete trial set; local software cannot discover undisclosed remote trials. |
| Repair | Persisted attempts, repair digest/history, prior failures, fresh post-repair observations and independent closure. Re-signing pre-repair observations cannot establish a retest. |
| Risk | Separate knowledge, evidence, treatment, acceptance and decision consequences. Unknown exposure, known-unaddressed items, expired acceptance and inherited risk debt remain visible. |
| Independent challenge | Principal and organizational-unit checks, full manifest binding, expiry, veto and explicit veto resolution. Real institutional independence depends on the trust administrator and evidence collection. |
| Recovery | Signed suspend/cancel/resume and reviewed assurance-run continuation. Continuing preserves cumulative budgets, deadlines, prior failures and unresolved risk across generations. |
| Effects | Transactional ActionGateway reference with shared budgets, concurrent reservations, idempotency, revocation, unknown-outcome accounting and separately authorized compensation. It is not a remote provider integration or OS sandbox. |
| Help and schedules | Durable help drafts, authenticated delivery/acknowledgement/response receipts, deadlines, dead letters, finite scheduler ticks and leases. No email, ticket transport or persistent scheduler service is installed. |
| Model evolution | Dated capability comparison, stale/deprecated/unknown route detection, benchmark prerequisites and fallback review. Output is an advisory candidate for authorized review; no automatic model promotion. |
| Decisions and reports | Deterministic GO/NO_GO/ESCALATE, scoped permissions and bounded expiry; complete raw JSON and escaped HTML exports. No deployment authority. |
| Lifecycle integration | Admitted enterprise plans carry enterprise_assurance. The completion path invokes the current verifier and requires subject/goal/criteria/engine binding and ENTERPRISE proof. Local successes and saved GO prose cannot clear the gate. Scheduled completion uses that same path. |
| Fleet | Discovery preserves existing policy and reviewed hashes; 14 packages are registered; portable and installed validation are separate; actual fixture execution receipts include registry, source and gate-file hashes. CI workflow is provided. |

Enterprise applicability is an admitted requirements/risk decision, not a classifier that can infer undisclosed enterprise use. The mandatory lifecycle policy requires the binding where applicable. Organization-controlled admission must prevent removing it or misclassifying the product.

## Verification evidence

- [Final fleet receipt](../output/enterprise-fleet-completion-receipt.json): **PASS: 347 tests across 23 suites**. It checks all 118 canonical entries and declared installations, then executes the package fixture suites and fleet tests.
- Runtime: 51 tests passed, including forged evidence, stale model evidence, subject changes, false success, dropped trials, recursive engines, revoked issuers, role conflicts, cumulative budgets, unknown effects, compensation failure, dead letters and continuation debt.
- Thirteen owner packages: 39 oracle tests.
- Lifecycle: 76 tests passed after adding four enterprise completion regressions. The four new tests also passed from the actual personal Codex installation.
- [Three-product receipt](../output/enterprise-final-demo/receipt.json): restricted knowledge assistant, insurance decision support and an agentic workflow. Each supplies all 13 fixture owner reports, receives scoped fixture GO, then correctly returns NO_GO when an unaddressed risk is introduced. All three retain live_release NO_GO.
- [Independent final report](../output/enterprise-forward-test/report-final.md): five demonstrated defects were repaired across two independent review passes. These concerned pre-repair evidence reuse, observation cutoff laundering, supporting-evidence expiry, risk-attestation expiry and risk loss on repeated continuation. Prior reports and reproductions are retained alongside the final report.
- Graphify refreshed the 55-file Python surface: 593 nodes, 1,739 edges, 45 explicitly unresolved references and zero dangling endpoints. [Graph diagnostics](../output/enterprise-final-graph/diagnostics.json). Structural coverage does not establish correctness.

Fleet receipts are signed with ephemeral local test keys and explicitly state authority none. Their embedded public keys do not establish organizational provenance. The configured GitHub workflow has not been run on hosted CI in this task.

## Known unaddressed activation requirements

| Requirement | Accountable enterprise role | Current consequence / evidence needed |
| --- | --- | --- |
| Protected trust, workload identity, signing and current revocation | Security/platform owner | ENTERPRISE evidence cannot be established by fixture keys. Supply administered issuers, protected collectors and revocation/time evidence. |
| Real product enforcement and remote effect semantics | Product/security/SRE owners | A report cannot stop a deployed product. Prove credential/network restrictions, last controllable dispatch, provider idempotency, unknown effects and stop acknowledgement. |
| Protected retention, holds and external history anchors | Records/data/security owners | SQLite hash chains can be rewritten by a privileged local writer. Supply controlled storage and independent retention/anchor evidence. |
| Incident/help delivery and supervised scheduler | Operations owner | Drafts and finite ticks do not deliver help or wake a process. Supply authorized transports, heartbeat supervision, retry/dead-letter and recovery evidence. |
| Real provider/frontier campaigns | Owners 2, 4, 7 and 11 | No provider credentials or live probes were used. Supply authorized workloads, complete raw trials, private challenges, failure rates, uncertainty and current provider evidence. |
| Approved risk appetite and domain/legal judgments | Business risk owner and Owner 8 | Synthetic thresholds and local signatures are not enterprise approval or legal certification. Supply actual profile approvals and domain decisions. |
| Authentic independent challenge | Owner 10 / second line | Thirteen personas are not thirteen independent authorities. Supply administered principals, conflict checks and independently collected challenge evidence. |
| Cross-version lifecycle ledger transition | Lifecycle operator | Existing ledgers pin their runner bytes. Old ledgers remain blocked under the new runner. Same-engine limit migration exists; automatic cross-version engine migration does not. Preserve old state and backed-up runner for a reviewed transition; do not rewrite its digest. |
| Unknown and untestable behavior | Named product risk owner | Finite testing cannot rule out hidden capability, deception, shadow assets or correlated institutional failures. Record exposure, interim controls, review dates and operational restrictions. |

These requirements are deliberately visible. They are not recorded as fixed, delivered, deployed or independently approved.

## Copy-paste prompt

```text
Use product-lifecycle-loop as the sole lifecycle conductor and
enterprise-ai-assurance-loop for a 13-owner enterprise AI assessment of
[repository/product/workflows]. Load the authoritative LoopsOS skill-fleet
registry and lifecycle_policy 1.1.0. Select exactly one repair delivery engine.

Start with discovery and an explicit subject, applicability matrix, approved
profile, budget and parent acceptance criteria. Add the enterprise_assurance
binding to the frozen lifecycle progress plan when enterprise assurance applies.
Use each applicable owner's method; preserve every missing, failed, stale,
untestable and known-unaddressed item. Plan product-specific frontier campaigns
beyond the initial regression catalog.

Run authorized local checks, reproduce defects, repair within scope, retest and
obtain independent challenge. Keep help drafts separate from actual delivery.
If external proof or authority is missing, complete independent local work and
export exact blockers, accountable owners, interim controls and required evidence.
Re-evaluate the current verifier at parent completion. Export the scoped decision,
full risk register, evidence manifest and remediation backlog. Do not deploy,
call providers, spend money or contact others without existing explicit authority.
```

## Local verification commands

Use an approved Python 3.12+ environment with PyYAML and the enterprise package's requirements.txt. From the LoopsOS workspace:

```text
python skill-fleet/fleet.py validate --registry skill-fleet/registry.json
python skill-fleet/run_gate.py --installed --output output/my-fleet-receipt.json
python skill-packages/enterprise-ai-assurance-loop/scripts/assurance.py identity
python skill-packages/enterprise-ai-assurance-loop/scripts/local_demo.py --output output/my-new-demo
```

The demo output directory must be new. This task used a workspace-local dependency directory at output/enterprise-assurance-deps; it did not install global dependencies or change an enterprise runtime environment.
