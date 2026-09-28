# Business work inside the lifecycle

Read the relevant playbook when the requested outcome involves revenue,
acquisition, engagement, or legal/privacy obligations. These are executable work
procedures for Codex to follow with real product inputs and tools, not claims
that billing, marketing accounts, or legal documents already exist.

Resolve delivery, research, design, and analytics owners as needed. No exact
`monetization`, `growth-gtm`, or `legal-doc` skill name is required if the
capability can be completed with available tools and verified sources. Do not
invent pricing, customer evidence, legal facts, or authority to contact people.

## Commercial definition, beginning in discovery

Establish the buyer and user, painful job, existing alternative, offer, success
measure, distribution hypothesis, willingness-to-pay evidence, and cost model.
Distinguish hypotheses from observed customer behavior. Prioritize the riskiest
assumption with a bounded experiment and a measurable acceptance threshold.

Write a compact business brief linked to the product vision and backlog. Useful
measures include activation, time to value, retention, paid conversion, revenue,
refunds, support load, gross margin, and provider/model cost per successful
outcome. Specify denominators, cohort/window, data sources, and uncertainty;
avoid substituting visits or model confidence for commercial validation.

Use `market-sizing` for cited market estimates, `moat-reviewer`/`idea-add-moat`
for defensibility, relevant data-analytics skills for metrics and experiments,
and `model-gateway`/`finops-model-economics` for scoped usage economics. These
overlap: choose one metric definition and owner, not competing spend ledgers.

## Monetization: billing, subscription state, entitlements

The authoring inventory found a cached `vercel:payments` skill covering Stripe
integration, but it was not in the active session catalog. Resolve current
availability before using it. Its presence would still not prove a product's
merchant configuration, entitlement enforcement, or payment behavior.

Inputs needed before dependent implementation: chosen billing provider, verified
merchant/project and test environment, approved offer/price/currency, supported
plans/trials, cancellation/refund rules, account-to-customer mapping, and the
product's access model. Draft reversible choices while waiting for missing
commercial decisions; do not activate a made-up live price.

Define the state contract first: checkout initiated, payment pending/succeeded/
failed, subscription active/past-due/cancelled/expired, refunds/disputes where
applicable, and the effect on access. Use current official provider docs. Build:

1. A server-owned product/price mapping and tenant/user-to-customer association.
2. Authorized checkout or account management with validated return URLs.
3. Signed webhook verification, event deduplication, replay protection, idempotent
   durable processing, and reconciliation with canonical provider state.
4. Server-enforced entitlements with explicit grace/revocation behavior and
   consistent UI state. A browser success redirect cannot grant paid access.
5. Auditable customer support, cancellation and refund paths, plus resource
   limits to keep provider costs within the accepted product economics.

Verify a vertical slice in the real provider test mode: checkout to verified
event to durable state to allowed access; failure and cancellation to the
correct denial; duplicate, delayed and out-of-order events; tenant isolation;
reconciliation after a lost response. Validate signature rejection and enforce
access at the service/API boundary. Record test-mode evidence as test-mode.

Live enablement, money movement, refunds, tax configuration and paid resources
need the applicable verified business inputs and authorization. A successful
test payment does not prove live settlement. Do not perform a live charge solely
to produce evidence without explicit authorization for that transaction.

## Acquisition, launch, and lifecycle engagement

Establish audience, positioning, offer, channel, budget if any, consent needs,
experiment duration, owner, success threshold and stopping rule. Inspect the
actual product journey before promising capabilities in copy.

Build the requested landing or acquisition surface with truthful claims,
accessible interaction, page metadata, crawl/indexing choices, performance,
working forms, abuse protection, and a measurable path to activation. Use the
active design/SEO/analytics tools relevant to the surface. Book/video metadata
skills have narrower scopes than general product SEO or a complete GTM plan.

Verify funnel events against real actions and distinguish test traffic. Measure
conversion by cohort/window with named denominators. For experiments, record
sample size and uncertainty; do not invent statistical significance.

For lifecycle messaging, specify consent and preferences, segmentation,
unsubscribe/suppression, retry/dedup behavior, and truthful templates. Drafts,
preview pages, and campaign setup can be prepared before any send or spend.
External messages, public publication and paid campaigns require applicable
explicit authorization. Do not contact prospects or users merely because a
backlog or skill proposes it.

## Legal and privacy deliverables

`legal-risk-register` and `compliance-mapping` can organize risk and evidence;
neither is proof of compliant terms or a substitute for drafting against actual
facts. Gather the entity/jurisdictions, audience and age rules, service behavior,
data categories/purposes, processors, retention/deletion, tracking, international
flows, payment terms, support/contact, AI limitations, and applicable contracts.
Keep unknowns explicit; do not fill them with invented business details.

For actual legal drafting, consult current authoritative sources and the
applicable specialist/counsel process. Draft terms, privacy/cookie notices,
consents or processor agreements only as required by the product. Link every
substantive operational promise to implemented behavior or a named gap. A
generated document is a draft; record review and acceptance separately.

Implement policy versioning and effective dates, consent/acknowledgment where
applicable, retrievable acceptance records, notices, preference controls, and
access/deletion/export behavior as required by the accepted design. Verify
missing or outdated required consent, record integrity, access controls, and
the actual rights workflow. Do not add a compulsory consent to optional
marketing simply to complete a checklist.

Publication follows the user's authorization and the product's applicable
review requirements. An approved document with unimplemented promises is a
product gap, not a completed legal layer.

## Business handoff

Report implemented behavior, experiments actually run, measured results,
assumptions, drafts/reviews, and live activation separately. Route remaining
work to the same product backlog with named owners. An app may be technically
running while revenue, acquisition, support, or legal obligations remain open;
whether those prevent launch depends on the product's actual launch contract.
