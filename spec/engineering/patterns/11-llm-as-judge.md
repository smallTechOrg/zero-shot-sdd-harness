# LLM-as-Judge

**Category:** Evaluation & Quality  
**Status:** Extended

## Intent

Use an LLM to evaluate the output of another LLM (or the same model), providing structured feedback or a quality score that drives automated quality gates or iterative refinement.

## When to use

- Automated quality assessment at scale (human review is too slow or expensive)
- Evaluating outputs on subjective dimensions: clarity, completeness, tone, factual consistency
- Driving an iterative refinement loop: generate → judge → improve → judge again
- A/B evaluation: comparing two candidate responses to pick the better one

**Do not use** for tasks with objective, verifiable correct answers — prefer deterministic tests or a reward model trained on human labels.

## How it works

### Evaluator pattern

```
Generator (LLM A)
  Input:  user query
  Output: candidate response

                │
                ▼

Judge (LLM B or same model)
  Input:  original query + candidate response + evaluation rubric
  Output: score (1–5) + structured feedback

                │
                ▼

Decision: accept if score ≥ threshold, else discard or refine
```

### Critic-Actor (Evaluator-Optimizer) pattern

```
Actor (LLM)
  Input:  goal
  Output: draft

     ◄──────────────────────────┐
     │                          │
     ▼                          │
Critic (LLM)                    │
  Input:  draft + rubric        │
  Output: critique + suggestions│
     │                          │
     ├──(below threshold) ──────┘ (Actor refines based on critique)
     │
     └──(above threshold) ──► final output
```

The loop exits when the Critic's score meets the threshold or a max iterations limit is reached.

## Evaluation rubric structure

A good judge prompt includes:
1. The task description (what was the Actor asked to do?)
2. The candidate output
3. A rubric with explicit dimensions and scoring guidance
4. An instruction to respond with a structured score

```
You are evaluating a draft email response. Score it on these dimensions:

Accuracy (1-5): Does it correctly address the customer's complaint?
Tone (1-5): Is it professional and empathetic?
Completeness (1-5): Does it address all points raised?

Respond as JSON:
{
  "accuracy": <1-5>,
  "tone": <1-5>,
  "completeness": <1-5>,
  "overall": <1-5>,
  "critique": "<2-3 sentences explaining the main weaknesses>"
}
```

## Variants

| Variant | Description |
|---|---|
| **Single-score judge** | One overall 1–10 score. Simple but less actionable. |
| **Multi-dimension rubric** | Score each quality dimension separately. More actionable feedback. |
| **Pairwise comparison** | Present two candidates; ask which is better and why. Avoids absolute calibration issues. |
| **Reference-based** | Provide a gold-standard reference answer; judge measures similarity. Works for factual tasks. |
| **Self-judge** | Same model instance evaluates its own output. Cost-efficient; lower independence but still useful. |

## Related patterns

- [05-self-correction.md](05-self-correction.md) — self-correction handles execution errors; LLM-as-Judge handles quality failures
- [12-self-consistency.md](12-self-consistency.md) — run multiple generations, use a judge to pick the best (Best-of-N)
- [17-multi-agent-debate.md](17-multi-agent-debate.md) — the judge is the moderator that evaluates competing arguments
- [23-constitutional-ai.md](23-constitutional-ai.md) — principle-based evaluation is a specialized form of LLM-as-Judge

## Implementation notes

- Use a higher-capability model as the judge than the generator where budget allows — a stronger judge produces more reliable scores.
- Always include the original task description in the judge prompt. The judge cannot evaluate accuracy without knowing what the Actor was asked to do.
- Calibrate the judge: collect human ratings on a sample of outputs and verify the judge's scores correlate. An uncalibrated judge adds noise, not signal.
- Use pairwise comparison for early-stage product decisions where you are comparing two approaches. Switch to rubric-based scoring when you need to gate production outputs.
- A Critic-Actor loop without a max iteration cap will run until the judge is satisfied — which may never happen. Always set a ceiling (typically 3 cycles).
