# Per-application run contract

Read this reference at the start of a material assurance run. Complete fields from supplied or permitted evidence and leave unknown values explicit.

```yaml
application_id: "stable unique ID or unknown"
application_name: "name or unknown"
run_id: "unique run ID"
previous_run_id: null
assessment_time: "actual timestamp and timezone"
trigger: "initial | change | release | incident | scheduled | evidence_expiry"
mode: "ASSESS_AND_PLAN | VERIFY_APPROVED_SANDBOX | REMEDIATE_APPROVED_SCOPE"
requested_decision: "demo | external_beta | production | expansion | diligence"
product_purpose: "business problem and intended outcome"
personas_and_affected_people: []
critical_user_journeys: []
prohibited_uses_and_actions: []
scope:
  repositories_and_components: []
  commit_or_build_id: "unknown"
  environment: "unknown"
  deployment_and_configuration_version: "unknown"
  included_features: []
  excluded_features_with_reasons: []
  dependency_versions: []
  shared_platform_components: []
  source_access_constraints: []
data:
  classifications: []
  tenancy_and_identity_boundaries: "unknown"
  retention_deletion_and_residency_rules: "unknown"
agent:
  autonomy_level: "unknown"
  permitted_tools_and_scopes: []
  model_provider_and_version: "unknown"
  prompt_policy_and_tool_versions: "unknown"
  retrieval_and_memory_versions: "unknown"
  high_impact_actions_and_approvers: []
requirements:
  contractual_domain_and_regulatory_requirements: []
  quality_and_business_success_metrics: []
  reliability_latency_and_recovery_targets: []
  cost_and_capacity_limits: []
  approved_acceptance_thresholds: []
ownership:
  product_owner: "Owner unknown"
  technical_owner: "Owner unknown"
  security_or_risk_owner: "Owner unknown"
  release_authority: "Owner unknown"
  release_target: "Release target unknown"
execution:
  authorized_read_targets: []
  authorized_test_environments: []
  authorized_change_targets: []
  prohibited_actions: []
  analysis_pass_limit: 3
  fix_attempt_limit_per_finding: 2
  no_progress_cycle_limit: 1
  token_cost_time_and_tool_call_budgets: "not configured"
  approval_policy: "explicit approval for changes or side effects"
```

The numeric limits above are proposed defaults, not facts or permission. Respect stricter supplied limits. Stay in `ASSESS_AND_PLAN` until authorized execution targets and limits are known.

## Evidence ledger

For each artifact record:

```text
Evidence ID | Application | Artifact and locator | Version | Environment | Collection time | Sensitivity | Claims supported | Completeness | Conflicts | Expiry trigger
```

Evidence expires when a relevant model, prompt, policy, tool, permission, data pipeline, dependency, configuration, build, or deployment changes, or when its approved validity period ends.

Do not replace missing application evidence with generic web information about its technology stack. External references can inform a control expectation, but only application-specific evidence can prove the application state.

## Completeness and traceability

Maintain:

```text
Persona -> Journey -> Requirement -> Component -> Control -> Evidence -> Test -> Finding -> Remediation -> Decision
```

Report:

- Assessment coverage = applicable controls examined / applicable controls identified.
- Evidence sufficiency = applicable controls with sufficient current evidence / applicable controls identified.
- Verification coverage = applicable controls with completed required verification / applicable controls identified.

Publish numerator and denominator. These measures apply only to the declared scope and do not prove that every possible risk was discovered.

At intake exit, produce an evidence ledger, scope map, missing-evidence queue, initial coverage table, and decision limits caused by sparse or contradictory evidence.
