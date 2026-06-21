# Constitutional AI

**Category:** Safety & Compliance  
**Status:** Extended

## Intent

Before returning a generated output, the agent evaluates it against a fixed set of principles ("the constitution") and revises any output that violates them — making compliance explicit, testable, and independent of the generation prompt.

## When to use

- Agents operating in domains with non-negotiable output constraints (financial advice, medical information, legal guidance, child safety)
- When output guidelines are stable and can be expressed as a finite list of principles
- When you need a systematic, auditable process for catching policy violations — not just "try to be safe"
- As a complement to guardrails: guardrails gate the pipeline; Constitutional AI runs inside the generation step

**Distinct from self-correction** ([05-self-correction.md](05-self-correction.md)): self-correction fixes execution errors (tool failures, bad parameters). Constitutional AI fixes principle violations in generated content.

## How it works

```
Generator (LLM)
  Input:  user query + context
  Output: draft response

     │
     ▼

Critique step (LLM — can be same model)
  For each principle in the constitution:
    "Does the draft response violate this principle?
     Principle: <principle text>
     Draft: <draft>
     Critique:"

  Output: list of violations (or "No violation" per principle)

     │
     ├──(all principles passed) ──────────────────────► return draft to user
     │
     └──(one or more violations)
          │
          ▼
     Revision step (LLM)
       Input:  draft + violations identified + revision instruction
       Output: revised response that addresses the violations

          │
          └──► (loop back to Critique step if configured for multi-pass)
```

## Constitution structure

A constitution is a numbered list of clear, verifiable principles:

```
1. Do not provide specific medical diagnoses. Instead, describe symptoms and recommend consulting a healthcare provider.
2. Do not name specific financial products or securities as "good" or "bad" investments.
3. Do not reveal the names or contact details of any individuals mentioned in the retrieved documents.
4. If uncertain about a factual claim, say so explicitly rather than presenting it as fact.
5. Do not generate instructions for activities that are illegal in the target jurisdiction.
```

Principles must be:
- **Specific enough to evaluate** — "be helpful" is not a principle; "do not suggest illegal alternatives to prescribed medications" is
- **Binary where possible** — either violated or not violated; graded violations are harder to critique reliably
- **Ordered by severity** — list the most critical principles first; the critique step applies them in order

## Variants

| Variant | Description |
|---|---|
| **Single-pass critique** | One critique call → one revision call. Sufficient for most cases. |
| **Iterative critique** | Critique → revise → critique again until all principles pass or max iterations reached. Higher compliance rate; higher cost. |
| **Parallel critique** | Evaluate each principle independently in parallel for lower latency. |
| **Binary gate** | Critique returns pass/fail; on fail, block the response entirely rather than revising. Higher safety; worse user experience. |
| **Soft guidance** | Critique scores violation severity (1–3); only block or revise high-severity violations. |

## Related patterns

- [14-guardrails.md](14-guardrails.md) — guardrails are a pre/post pipeline gate; Constitutional AI is built into the generation loop. Both are needed in high-stakes applications.
- [11-llm-as-judge.md](11-llm-as-judge.md) — the critique step IS an LLM-as-Judge evaluating the draft against each principle
- [05-self-correction.md](05-self-correction.md) — shares the "generate, evaluate, revise" structure but applies to principle violations, not execution errors
- [22-observability.md](22-observability.md) — log every critique decision: which principle was evaluated, what the critique said, and whether a revision was triggered

## Implementation notes

- Keep the constitution to ≤ 15 principles. Longer constitutions increase critique cost and dilute focus. If you need more, split the agent into specialized handlers, each with a smaller constitution.
- The critique step must be deterministic or near-deterministic (temperature = 0). Use a structured output format (JSON with principle ID + pass/fail + violation description) for reliable parsing.
- Validate the constitution itself before deploying: write test cases for each principle — inputs that should violate it, and inputs that should not. A principle that the LLM cannot reliably apply is worse than no principle.
- Do not confuse the constitution with the system prompt's instructions. Instructions shape what the agent generates. The constitution governs what is allowed to leave. They operate at different layers.
- When a revision is triggered, include the specific violated principle(s) in the revision prompt — not the full constitution. Focused revision prompts produce more targeted corrections.
