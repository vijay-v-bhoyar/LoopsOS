# Adaptive product review

Apply these checks to the product, not to the reviewing model's marketing tier.
Use the executable [evolution contract](evolution-contract.md) for JSON evidence.
The practices below are a design synthesis of [current sources](current-sources.md),
not a claim that a provider guarantees safe upgrades.

## Ask whether capability gains reach the customer

For each critical journey record: user outcome, task contract, current model and
provider/platform, version semantics, prompt and tool schemas, retrieval/index,
memory policy, allowed actions, quality floor, latency/cost limits and failure path.
Keep model adapters replaceable while preserving provider-specific capabilities;
a lowest-common-denominator wrapper can discard the feature being evaluated.

Build an opportunity register alongside the risk register. Each opportunity needs
an observed limitation, proposed capability, expected outcome, baseline, experiment,
owner (or unknown), acceptance criteria, cost boundary and next decision. Examples
include simpler orchestration, better long-document accuracy, reliable structured
actions, improved multilingual/voice/image journeys, or cheaper routing at the
same quality. None is a default requirement for every product.

## Discover -> compare -> decide -> roll out -> learn

1. **Discover with provenance.** Watch official model/API/SDK/tool release and
   deprecation sources, plus the product's production failures. Record checked
   time, URL, relevant claim, affected task, freshness deadline and owner. Distinguish
   published, preview, account-accessible, evaluated and deployed. Never derive
   version mutability from a model name alone. An alias change, provider behavior
   drift or dependency retirement can trigger review without an application commit.
2. **Check compatibility.** Validate region/account availability, data-handling
   constraints, tools, JSON schemas, streaming, reasoning parameters, modalities,
   context behavior, SDK/API versions, rate limits and supported fallback. New
   embeddings require retrieval/index migration evaluation, not a string swap.
3. **Run bounded experiments.** Fix the product revision, representative dataset,
   held-out cohort, scorer, confidence method and thresholds before comparing.
   Start with a controlled model-only comparison; evaluate prompt/architecture
   changes as separately identified configurations. Include positive, negative,
   abuse, timeout, retry, cancellation, cross-tenant and distribution-shift cases.
4. **Make a product decision.** Require either supported quality gain, or preserved
   quality with meaningful cost/latency gain, while all hard limits pass. Report
   sample size and uncertainty; inspect critical cohorts separately. Avoid
   promoting on a provider benchmark or an overall mean that hides regressions.
   A small or inconclusive sample calls for more evidence within budget, not GO.
5. **Apply existing release policy.** Bind candidate/model, prompt/tool/retrieval
   configuration, dataset/scorer, result artifacts, expiry, target and rollback
   configuration into a proposal. The release executor validates identity and
   authority, then performs shadow/canary/promotion with real receipts. Shadow
   traffic must not duplicate side effects; use isolation or recorded tool results.
6. **Observe actual outcomes.** Monitor task success, severe failures, cost per
   successful task (including retries and human work), latency, customer completion
   and recovery. Define sample/observation windows, stop thresholds, accountable
   recipient and a still-supported rollback route. Feed failures into the next
   test corpus without exposing private data or contaminating the held-out set.

## Bound the automation

Choose permissions per product: discovery only, sandbox evaluation, prepared
change proposals, or policy-authorized canary/promotion. Record total experiment
spend, wall time, attempts, parallelism and data access limits. A model cannot
change those limits or its graders to improve its own score. Escalate authority
gaps to the policy owner; do not route them to a more privileged model.

For an active service, show scheduler last/next run and failure delivery, actual
credential scope, durable candidate/effect IDs, retry reconciliation, current
budget use and cancellation behavior. A document containing a cadence is not a
running monitor. If no scheduler or deployment adapter exists, produce the exact
implementation work and mark activation incomplete. Use the existing lifecycle
conductor rather than nesting several independent infinite loops.

## Challenge the upgrade process itself

- Does a stronger model gain tool permissions, data reach or spending authority?
- Are injection and poisoning tests run against retrieved content, tool/MCP output,
  memories, uploaded media and cross-agent messages that are actually in scope?
- Can a model/agent alter the acceptance suite, grader, thresholds or release policy?
- Are judge preferences calibrated against task outcomes and independently checked?
- Do timeouts, refusal shifts, truncated outputs, compaction and fallback change
  application invariants? Is replay safe and are canceled effects reconciled?
- Could an automatic alias switch bypass the evaluated configuration? Could a
  retired incumbent also make the advertised rollback target unusable?
- Are the model's new capabilities blocked by stale prompts or hardcoded workflows?
  Conversely, does removing a workaround remove a real business rule?
- Is improvement visible to users and commercially useful, or only a better demo?

## Deliver a decision that can be acted on

For each candidate or opportunity report the task, baseline, exact change,
measured benefit, uncertainty, failed constraints, remaining evidence, next owner,
and permitted next action. Keep business moat grounded in customer workflow,
rights-cleared data, integrations and measured value. Technical model portability
alone is not defensibility. Review the assessment machinery when providers retire
eval, prompt, orchestration or observability services; keep portable copies of the
contracts and artifacts required to reproduce the decision.
