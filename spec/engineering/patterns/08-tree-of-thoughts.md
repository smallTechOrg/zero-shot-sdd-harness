# Tree of Thoughts

**Category:** Loop & Reasoning  
**Status:** Extended

## Intent

Extend Chain of Thought to explore multiple reasoning paths simultaneously, evaluate each path, prune dead ends, and backtrack — enabling the LLM to solve problems that require forward planning or benefit from exploration of alternatives.

## When to use

- Problems with a large solution space where early choices constrain later options
- Creative tasks (writing, design, strategy) where multiple valid paths exist and the best must be selected
- Optimization or constraint-satisfaction problems
- Tasks where a single linear reasoning chain reliably fails (the LLM "gets stuck")

**Not worth the cost** for straightforward tasks where Chain of Thought or a simple ReAct loop suffices.

## How it works

At each reasoning step, generate K candidate "thoughts" (continuations), evaluate each for promise, expand the most promising ones, and abandon the rest.

```
Goal
  ├── Thought A (promising)
  │     ├── Thought A1 (promising) ──► expand further
  │     └── Thought A2 (pruned)
  ├── Thought B (pruned)
  └── Thought C (promising)
        ├── Thought C1 ──► solution found
        └── Thought C2 (pruned)
```

### Search strategies

| Strategy | Description | Use when |
|---|---|---|
| **BFS (Breadth-First)** | Expand all nodes at depth D before going deeper | Shallow trees, bounded problem size |
| **DFS (Depth-First)** | Follow one path to completion, backtrack on failure | Deep trees, early termination expected |
| **MCTS (Monte Carlo Tree Search)** | Sample paths to estimate value; balance exploration vs. exploitation | Complex games, planning under uncertainty |

### LATS (Language Agent Tree Search)

LATS applies MCTS to agents: each node in the tree is an `AgentState`. Evaluation at each node uses a reward model (LLM-as-Judge or heuristic score). The agent backtracks to the highest-value node and tries a different branch.

```
State 0 (root)
  ├── State 1a (tool_call A → result A)
  │     └── State 2a (tool_call B → error) ← low value, abandon
  └── State 1b (tool_call C → result C)
        └── State 2b (reasoning → FINAL ANSWER) ← high value, return
```

## Key components

1. **Thought generator** — given current state, produce K candidate next thoughts or tool calls
2. **Thought evaluator** — score each candidate (heuristic, LLM-as-Judge, or value model)
3. **Search controller** — selects which thought to expand next based on strategy
4. **Backtracker** — restores state to a previous node when a branch is pruned

## Variants

| Variant | Description |
|---|---|
| **Self-evaluation ToT** | LLM generates thoughts AND evaluates them in the same call |
| **External evaluator ToT** | Separate LLM call or reward model evaluates each thought |
| **Beam search** | Keep the top-B candidates at each depth level |
| **Iterative deepening** | Start with BFS at shallow depth, increase depth if no solution found |

## Related patterns

- [07-chain-of-thought.md](07-chain-of-thought.md) — ToT generalizes CoT to a tree structure
- [01-react-loop.md](01-react-loop.md) — LATS extends ReAct with tree search over agent states
- [11-llm-as-judge.md](11-llm-as-judge.md) — the evaluator component is often an LLM-as-Judge
- [12-self-consistency.md](12-self-consistency.md) — simpler alternative: multiple CoT paths, majority vote

## Implementation notes

- ToT is significantly more expensive than linear CoT or ReAct. Benchmark CoT and ReAct first; only adopt ToT if they demonstrably fail on the target task.
- The number of candidates K and the depth limit D together define the search space size (K^D). Keep K ≤ 5 and D ≤ 4 unless you have strong reasons to go deeper.
- State must be fully serializable for backtracking to work — every field in `AgentState` must be copyable without side effects.
- LATS is overkill for most production agents as of 2026. Use it for game-playing, constraint satisfaction, or complex multi-step planning where simpler approaches fail.
