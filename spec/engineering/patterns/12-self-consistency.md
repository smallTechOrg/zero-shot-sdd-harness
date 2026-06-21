# Self-Consistency / Best-of-N

**Category:** Evaluation & Quality  
**Status:** Extended

## Intent

Generate multiple independent candidate outputs for the same input, then aggregate or select the best one — trading inference cost for reliability.

## When to use

- Tasks with a single correct answer where the LLM is unreliable on a single pass (math, logic, factual reasoning)
- When you need higher confidence than any single generation provides
- Best-of-N when outputs can be scored and the best one can be identified programmatically or with a judge

**Not useful** for open-ended creative tasks where "correct" is subjective, or when cost is a hard constraint.

## Self-Consistency

Run the same prompt N times with a temperature > 0 (to introduce variation). Each run produces a different reasoning trace and answer. Take the majority answer.

```
Query ──► Run 1 (temp=0.7) ──► Answer: Paris
      ──► Run 2 (temp=0.7) ──► Answer: Paris
      ──► Run 3 (temp=0.7) ──► Answer: London
      ──► Run 4 (temp=0.7) ──► Answer: Paris
      ──► Run 5 (temp=0.7) ──► Answer: Paris

Majority vote: Paris (4/5) ──► final answer
```

Works because: the correct answer tends to have higher probability under the model's distribution and therefore appears more often across samples.

## Best-of-N

Generate N candidates and score each. Return the highest-scoring one.

```
Query ──► [Generate N candidates in parallel]
               │
               ▼
         [Score each candidate]
         Options:
           - Heuristic (string length, keyword presence, etc.)
           - Reward model trained on human preferences
           - LLM-as-Judge (see 11-llm-as-judge.md)
               │
               ▼
         Return highest-scoring candidate
```

Best-of-N is more powerful than self-consistency when:
- Correct answers are hard to identify by majority vote (subjective tasks)
- You have a reliable scorer
- Diversity of the candidates matters (use higher temperature)

## Key parameters

| Parameter | Guidance |
|---|---|
| N | 3 is the minimum meaningful sample; 5 is typical; 10+ only for high-stakes tasks |
| Temperature | 0.6–0.9 to introduce variation while keeping outputs on-task |
| Aggregation | Majority vote for factual tasks; LLM-as-Judge for quality tasks |
| Parallel vs serial | Generate all N in parallel for minimum latency (cost is the same) |

## Variants

| Variant | Description |
|---|---|
| **Mixture-of-prompts** | N runs with slightly different system prompts or few-shot examples, then aggregate. More diverse candidates. |
| **Iterative refinement + selection** | Generate N candidates, score, take the top K, refine them, score again. Combines with Critic-Actor. |
| **Ensemble routing** | Run the task through N different models; pick the best by judge score. |

## Related patterns

- [07-chain-of-thought.md](07-chain-of-thought.md) — self-consistency is applied to CoT outputs — the reasoning traces differ, the answer is aggregated
- [11-llm-as-judge.md](11-llm-as-judge.md) — Best-of-N uses LLM-as-Judge as the scorer
- [16-orchestrator-worker.md](16-orchestrator-worker.md) — the orchestrator fans out to N workers and selects the best result (architectural analog)

## Implementation notes

- Run all N generations in parallel — they are independent. Serial generation N-times is always worse (same cost, higher latency).
- For majority voting, normalize answers before comparing — strip whitespace, lowercase, handle abbreviation variants.
- Self-consistency improves accuracy 5–15% on reasoning benchmarks, but the improvement diminishes after N=7–10. Don't over-invest.
- Best-of-N with a strong judge model can approach human-level quality gates for many production tasks. It is the most practical quality mechanism after self-correction.
- Log all N candidates and their scores, not just the winner — they are valuable training signal for fine-tuning later.
