# Current source baseline

Verified against official documentation on **2026-09-19**. Revisit these live
sources when assessing an upgrade; this date does not make the contents permanent.
No model names, prices or availability promises below are default routing policy.

| Source | What it supports | Effect on this skill |
| --- | --- | --- |
| [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | Task-specific evaluation, representative data, calibrated scoring and evaluation across changes. | Require product comparisons and repeatable evidence. |
| [OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection) | Accuracy, latency and cost tradeoffs. | Accept cheaper/faster candidates only when quality and safety remain acceptable. |
| [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations) | Models and hosted API/platform surfaces can retire. Current notices include Evals, reusable prompt objects and Agent Builder retirement dates. | Store reproducible eval/prompt/decision artifacts in product-owned formats; refresh exact deadlines at use. |
| [OpenAI skills and prompts guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) | Concise routing, progressive disclosure and revisiting unnecessary scaffolding as models improve. | Keep this entrypoint concise; test simplification opportunities. |
| [OpenAI agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety) | Untrusted inputs can influence downstream actions; structured boundaries reduce risk. | Test tool/data boundaries outside the model. This is legacy platform documentation, not a recommendation to adopt Agent Builder. |
| [Anthropic model IDs and versions](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) | ID semantics differ; serving changes may affect behavior even with fixed weights. | Record provider-declared identity semantics and observe incumbents for drift. |
| [Anthropic deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations) | Retirements, migration requirements and platform-specific schedules. | Verify actual provider/platform and parameter compatibility before adoption. |
| [Google Gemini models](https://ai.google.dev/gemini-api/docs/models) | Stable, preview, latest and experimental lifecycles differ; moving aliases can change. | Separate discovery aliases from evaluated deployment identities. |
| [Google Gemini deprecations](https://ai.google.dev/gemini-api/docs/deprecations) | Retirement notices and replacements span different model capabilities. | Track embeddings, media and agent dependencies as well as text inference. |

These sources motivate the review method. They do not prove a particular product's
results, account entitlement, data handling, deployment or business value. New
sources should include their retrieval time, affected dependency and expiry in
the product's evidence bundle. Unreachable or contradictory sources remain an
explicit evidence gap.
