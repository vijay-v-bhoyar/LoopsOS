# Decision and reply contract

## Decision card

List all open gates and severities above the card, then present only the next eligible item.

Show:

- repository evidence and its limits;
- user-visible or operational consequence;
- why the item matters for the intended target environment;
- dependencies and uncertainty.

Offer two to four materially different, mutually exclusive repository-supported options plus `SKIP`. If only one defensible option exists, present it without inventing alternatives. When both are viable, distinguish the smallest safe fix from the durable fix; a phased sequence is one option, not several cosmetic variants.

Use:

| Option | Mechanism | Advantage | Disadvantage | Effort | Ongoing cost |
|---|---|---|---|---|---|

State uncertainty in effort and cost. Recommend one option and compare it with the next-best option using actual repository constraints.

Under the table include:

- failure mode addressed;
- scope boundaries;
- rollback or compensation method and limits;
- done criteria covering one coherent behavior or safety property, required commands, and relevant failure/abuse checks.

End exactly with:

```text
DO NOT IMPLEMENT UNTIL I CHOOSE.
```

After presenting the card, perform no command or edit until the user replies.

## Reply handling

- A number selects that option from the current card.
- `REC` selects the current recommendation.
- `SKIP` defers the item without changing gate severity or status.
- `REJECT` rejects the options. Regenerate once; after a second rejection ask which constraint was missed.
- `STATUS` reports the scorecard and blockers without implementation, then returns to the current decision.
- `REPRIORITIZE` updates backlog ordering and presents the next eligible decision.
- `STOP` ends work and produces the stop report.

Accept clear natural-language equivalents. Do not infer approval from discussion or ambiguous language. If the reply could select more than one option, ask one concise clarification and do nothing else.

## Blocking facts

Do not conduct a broad interview. Infer routine implementation details from repository evidence and use reversible defaults inside the selected slice.

Ask one focused `BLOCKING_FACT` question when a necessary fact cannot be established and different answers materially affect safety, authorization, identity, tenancy, privacy, retention, provider choice, spending, data handling, tool authority, or acceptance criteria.

Do not fabricate options for a factual question. An unanswered question is not approval. Once asked, perform no further commands or edits until answered.
