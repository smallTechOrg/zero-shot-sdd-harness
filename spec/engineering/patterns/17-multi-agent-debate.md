# Multi-agent Debate

**Category:** Evaluation & Quality  
**Status:** Extended

## Intent

Multiple agents independently reason about the same problem, then challenge each other's conclusions — producing a more robust final answer through structured disagreement and consensus.

## When to use

- High-stakes decisions where a single agent's bias could cause harm
- Complex analytical tasks where multiple valid interpretations exist
- Red-teaming: one agent's role is to find holes in another's reasoning
- Creative decisions where multiple expert perspectives add value (e.g., product design, content review)
- Reducing hallucination: minority claims are challenged and must be justified

**Not worth the cost** for factual lookup tasks or operational tasks with clear correct answers.

## How it works

### Panel Review

```
Panel agent A ──► opinion A ──┐
Panel agent B ──► opinion B ──┼──► Aggregator ──► synthesized answer
Panel agent C ──► opinion C ──┘
```

Each panel agent reasons independently (no visibility into others' responses) and produces an assessment. The aggregator synthesizes them.

### Adversarial Debate

```
Round 1:
  Proposer ──► initial argument for position X

Round 2:
  Opposer ──► counter-argument against X (reads Proposer's argument)

Round 3:
  Proposer ──► rebuttal (reads Opposer's counter-argument)

Round N:
  Moderator ──► evaluates both positions ──► decides winner / nuanced synthesis
```

### Round-Robin Refinement

```
Agent 1 ──► draft
Agent 2 ──► reads draft, improves it ──► draft v2
Agent 3 ──► reads draft v2, improves it ──► draft v3
     ...
Final: draft vN returned
```

## Key components

1. **Isolation protocol** — in panel and adversarial variants, agents in the same round must not see each other's responses (prevent groupthink)
2. **Role definition** — each agent's system prompt defines its role (Proposer, Opposer, Reviewer, Devil's Advocate, etc.)
3. **Aggregator / Moderator** — the final arbiter; synthesizes or decides
4. **Termination condition** — number of rounds, consensus threshold, or Moderator decision

## Variants

| Variant | Description |
|---|---|
| **Panel Review** | N agents in parallel; independent opinions; aggregated |
| **Adversarial Debate** | Structured for/against rounds; moderated decision |
| **Socratic Dialogue** | One agent plays questioner, one plays answerer; questions probe for weaknesses |
| **Devil's Advocate** | One agent's role is always to challenge the current consensus |
| **Red Team / Blue Team** | Red team attacks the agent's output; Blue team defends; safety team evaluates |

## Related patterns

- [11-llm-as-judge.md](11-llm-as-judge.md) — the Moderator is an LLM-as-Judge
- [12-self-consistency.md](12-self-consistency.md) — panel review without debate is self-consistency with majority vote
- [16-orchestrator-worker.md](16-orchestrator-worker.md) — the orchestrator instantiates and coordinates the debating agents
- [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) — each debating agent is a sub-agent

## Implementation notes

- Strictly isolate agents within the same round. Pass previous-round outputs explicitly, not through shared state.
- The Moderator prompt must include the complete debate history and a clear instruction to decide — without explicit instruction the LLM often refuses to choose a winner.
- Keep round counts low (2–3 is typical). The quality improvement from additional rounds diminishes sharply after the first rebuttal.
- Debate produces significantly more LLM calls and tokens than a single-agent approach. Budget accordingly — this pattern is for high-value decisions only.
- Use consistent agent identifiers in the transcript (e.g., "Agent A", "Proposer", "Critic") so the Moderator can attribute claims correctly.
