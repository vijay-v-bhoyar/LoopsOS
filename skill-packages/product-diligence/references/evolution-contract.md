# Model evolution evidence contract

`model_evolution.py` is a read-only, standard-library evaluator for evidence of a
product's ability to adopt model improvements safely. It does not discover new
models, fetch pages, run evaluations, schedule work, authorize spending, mutate
the product, or deploy. The owning lifecycle, model gateway, evaluation, and
release systems perform those operations. This evaluator checks their supplied
receipts. It never returns execution authority.

## API and result

```python
from pathlib import Path
from model_evolution import evaluate

result = evaluate(manifest, base_dir=Path("/product/.diligence"))
```

API: `evaluate(manifest: dict, base_dir: Path | None = None,
now: datetime | None = None) -> dict`. `base_dir` is the manifest's directory;
omitting it uses the current working directory. `now` defaults to actual UTC;
an injected value must be timezone-aware and is intended for reproducible tests.
Production callers must not reuse a past assessment timestamp to evade expiry.

CLI: `python model_evolution.py /product/.diligence/manifest.json`. It prints JSON
and returns 0 for a qualified capability, 2 otherwise. Parse the JSON: exit 0
does not say that a candidate passed, nor that a release was approved.

- `status: EVIDENCE_MISSING`: required bytes or required values are absent.
- `status: NOT_READY`: supplied capability evidence is stale, inconsistent,
  malformed, has failed controls, or fails a requirement.
- `status: QUALIFIED`: the supplied capability evidence meets this structural
  contract; the product is eligible for review on that evidence.
- `candidate_decisions`: each distinct challenger has its own status, reasons,
  and, on success, qualifying improvement paths and evaluation hash.
- `capability_only: true`: no challenger is qualified. An explicit empty
  `candidates: []` is valid if the current pipeline is proven. Retaining the
  champion when a new model provides no measured benefit is a successful control
  outcome. Rejected candidates do not invalidate otherwise valid capability.
- `execution_authorized: false`: invariant at both result and candidate level.

Validation stops at the first capability failure and first failure per candidate;
re-run after repair to discover further failures. This is not an exhaustive risk
register. That remains the diligence sweep's job.

## Trust and identity boundary

Every configuration, control, evaluation, source, trace, and protocol receipt
contains a relative `path` and lowercase `sha256`. Paths resolve below the
manifest directory, including after symlink resolution; absolute or escaping
paths are rejected. Stage approved evidence beneath that directory and record
its hash. Missing files stay unknown, changed bytes invalidate the receipt.
JSON files reject duplicate keys and nonfinite constants.

`subject` has exactly `product`, `revision`, `environment`, and `configuration`,
all nonempty strings, and must match the manifest exactly. The caller supplies
the real source revision and deployed/configured identity; do not use descriptive
labels that collapse different builds. Control and evaluation proofs bind that
same subject. Config and proofs carry `observed_at` and `expires_at` as timezone
timestamps and must satisfy `observed_at <= actual_now < expires_at`.

Hashes prove which bytes were supplied. They do not authenticate their author,
prove semantic truth, establish that an HTTPS source is official, calculate the
reported statistical interval, verify a model's declared immutability, or verify
that tests actually ran. An independent reviewer must validate those claims and
the sampling, scoring, calibration, and trace provenance. The real release
executor must authenticate identity and enforce its own current policy, budget,
preauthorization, and rollback requirements. A forged but internally consistent
receipt is outside this evaluator's trust boundary; do not expose this output as
a production GO token.

## Required capability controls

Each of the eight controls has a supplied owner and hash-pinned JSON proof.
Every proof lists exactly all configured task IDs in `covered_tasks`; partial
task coverage cannot qualify the product. Every listed check must be literal
JSON `true`, representing supplied exercised evidence, not a proposed design.

| ID | Key | Required proof checks |
|---|---|---|
| E-01 | `task_routing` | `pins_enforced`, `capability_checks_exercised`, `provider_contract_tests_passed` |
| E-02 | `refresh_watch` | `discovery_exercised`, `deprecation_watch_exercised`, `owner_routing_exercised` |
| E-03 | `evaluation_pipeline` | `holdout_separation_exercised`, `trace_capture_exercised`, `grader_calibration_passed`, `contamination_checks_passed` |
| E-04 | `policy_enforcement` | `permissions_outside_model`, `privacy_outside_model`, `budget_outside_model`, `limits_exercised` |
| E-05 | `fallback_recovery` | `fallback_exercised`, `replay_idempotency_exercised`, `cancellation_exercised` |
| E-06 | `rollout_rollback` | `shadow_exercised`, `canary_exercised`, `rollback_exercised`, `stop_trigger_exercised` |
| E-07 | `product_outcomes` | `outcomes_measured`, `baseline_bound`, `regression_monitor_exercised` |
| E-08 | `release_authority` | `executor_identity_bound`, `preauthorization_scope_checked`, `approval_replay_prevented`, `review_separate_from_execution` |

The proof owner must match the control record owner. For E-02 it must also match
`refresh.owner`. Refresh requires a positive finite cadence, a last review time
no later than now, and a future next review within that cadence. At least one
fresh HTTPS source with actual captured bytes is required per configured model
provider. Source capture must precede or equal the declared review. Verify the
source's official provenance during intake; URLs alone do not establish it.

Tasks require a champion model with explicit provider, model ID, version,
`version_mutable: false`, actual configuration receipt/hash, and supported
capabilities. Version IDs need not contain dates. The supplied provider evidence
must establish immutability; don't assert false just to pass. Literal `latest`,
`auto`, and `default` are not accepted as version pins. For providers without a
stable version or reproducible deployment identity, record that limitation and
retain an unqualified automatic-upgrade posture until an adapter can control it.

## Manifest and proof examples

The following examples show shape; illustrative values and digest tokens must
be replaced by actual measured artifacts. The test suite constructs a complete
passing fixture with actual temporary file bytes; that fixture is test evidence,
never evidence about a real product.

```json
{
  "subject": {
    "product": "support-product",
    "revision": "full-source-revision",
    "environment": "staging",
    "configuration": "actual-product-config-digest"
  },
  "model_evolution": {
    "path": "evolution/config.json",
    "sha256": "REPLACE_WITH_ACTUAL_64_LOWERCASE_HEX_DIGEST"
  }
}
```

Receipt paths inside `evolution/config.json` still resolve from the **manifest
directory**, not the configuration file's directory. A control proof looks like:

```json
{
  "kind": "model-evolution/control-proof@1",
  "subject": {"product": "support-product", "revision": "full-source-revision", "environment": "staging", "configuration": "actual-product-config-digest"},
  "observed_at": "2026-09-19T10:00:00Z",
  "expires_at": "2026-09-20T10:00:00Z",
  "control": "policy_enforcement",
  "owner": "supplied-owner",
  "covered_tasks": ["support"],
  "checks": {"permissions_outside_model": true, "privacy_outside_model": true, "budget_outside_model": true, "limits_exercised": true}
}
```

Configuration fields:

```text
schema: product-diligence/model-evolution@1
subject: exact manifest subject
observed_at, expires_at: current validity window
controls: all eight keys -> {owner, evidence: {path, sha256}}
refresh:
  owner, cadence_hours, last_reviewed_at, next_review_at
  official_sources: [{provider, url, observed_at, expires_at,
                     artifact: {path, sha256}}]
tasks: one or more entries described below
candidates: explicit list; [] is allowed
```

Each task:

```json
{
  "id": "support",
  "champion": {
    "provider": "supplied-provider", "id": "supplied-model",
    "version": "supplied-immutable-version", "version_mutable": false,
    "configuration_sha256": "ACTUAL_TASK_CONFIG_HASH",
    "capabilities": ["json", "tools"]
  },
  "configuration": {"path": "evolution/task-config.json", "sha256": "ACTUAL_TASK_CONFIG_HASH"},
  "required_capabilities": ["json", "tools"],
  "evaluation_protocol": {
    "dataset": {"path": "evolution/holdout.jsonl", "sha256": "ACTUAL_DATASET_HASH"},
    "scorer": {"path": "evolution/scorer.py", "sha256": "ACTUAL_SCORER_HASH"},
    "configuration": {"path": "evolution/eval-config.json", "sha256": "ACTUAL_EVAL_CONFIG_HASH"}
  },
  "product_outcome": {"metric": "successful_resolution_rate", "direction": "higher"},
  "thresholds": {
    "min_samples": 200,
    "min_confidence_level": 0.95,
    "quality_noninferiority_margin": 0.01,
    "min_quality_uplift": 0.02,
    "min_cost_improvement_fraction": 0.15,
    "min_latency_improvement_fraction": 0.15,
    "max_cost_per_task": 0.10,
    "max_latency_p95_ms": 500,
    "min_product_outcome_improvement": 0
  }
}
```

These numbers are illustrative, **not defaults or recommendations**. The product
owner supplies every threshold. Costs must use one consistent supplied currency
and billing scope, quality must use one task-specific score with higher being
better, and sample units must match the paired statistical design. The evaluator
does not choose an adequate sample size. Unit/currency definitions belong in the
pinned evaluation configuration and independent review.

## Challenger evidence and decision

A candidate is `{id, task, model, configuration: {path, sha256}, evaluation:
{path, sha256}}`. `model` has the same fields as a champion; its actual
configuration receipt must match its configuration hash. The candidate must
differ by provider, ID, version, or configuration hash; a capabilities-list
reordering is not a new candidate.

The evaluation JSON contains:

```text
kind: model-evolution/paired-evaluation@1
subject, observed_at, expires_at
candidate_id, task: exact configured IDs
champion, challenger: exact model objects used in the comparison
dataset_sha256, scorer_sha256, configuration_sha256:
  exact task evaluation-protocol receipt digests
paired: true
trace: {path, sha256} of actual task traces
sample_count: positive integer
confidence_level: finite, at least the supplied minimum and below 1
confidence_method: nonempty description of the actual method
checks:
  safety_passed, compatibility_passed, capabilities_passed, holdout_passed,
  grader_calibration_passed, shadow_passed, canary_passed, rollback_passed,
  cancellation_passed: all literal true
quality:
  champion_mean, challenger_mean, delta_lower_bound, delta_upper_bound
cost: {champion_per_task, challenger_per_task}
latency: {champion_p95_ms, challenger_p95_ms}
product_outcome: {metric, champion, challenger}
```

The mean quality delta must lie inside the supplied interval, and its lower
bound must be at least the negative supplied noninferiority margin. At least
one improvement must hold: quality lower bound reaches `min_quality_uplift`, or
cost/latency relative reduction reaches its supplied minimum while quality
remains noninferior. Both hard challenger cost and latency ceilings apply on
every path. The named measured product outcome must improve by its supplied
minimum in the configured direction. Safety, compatibility, capability,
holdout, calibration, and exercised recovery/rollout checks are hard gates.

Comparison reports must use the same task, product subject, dataset, scorer,
evaluation configuration, and traceable paired examples. The evaluator checks
those bindings and numeric consistency; it does not recompute statistical
intervals from raw traces or verify exposure counts. Shadow/canary evidence may
come from an already authorized staged experiment; qualification never grants
permission to create that experiment or bypass an approval boundary.

Local test command: `python -B -m unittest test_model_evolution.py -v`.
