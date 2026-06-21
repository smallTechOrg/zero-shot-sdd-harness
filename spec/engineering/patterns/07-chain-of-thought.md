# Chain of Thought

**Category:** Loop & Reasoning  
**Status:** Extended

## Intent

Prompt the LLM to reason step-by-step before producing an answer, making complex reasoning explicit and more reliable.

## When to use

- Multi-step arithmetic or logic problems
- Tasks that require synthesizing several pieces of information
- Any time intermediate reasoning steps are needed to reach a correct final answer
- As the "reason" portion inside a ReAct loop's `plan_action` step

**Not needed** for simple lookup tasks where the answer is directly in the LLM's training data or retrieved context.

## How it works

Include a reasoning instruction in the prompt:

```
Think through this step by step before answering.

Question: A customer's invoice total is $245.00. They paid $100 upfront
and a 15% discount applies to the remainder. How much do they still owe?

Reasoning:
  Step 1: Remaining after upfront payment: $245 - $100 = $145
  Step 2: 15% discount on remainder: $145 × 0.15 = $21.75
  Step 3: Amount owed: $145 - $21.75 = $123.25

Answer: The customer still owes $123.25.
```

The LLM uses the reasoning trace to arrive at a more accurate answer. The trace can be kept in the response or stripped before returning to the user.

## Variants

| Variant | Description |
|---|---|
| **Zero-shot CoT** | Add "Let's think step by step" or "Think through this carefully" to the prompt. No examples needed. |
| **Few-shot CoT** | Provide 2–5 worked examples with full reasoning traces before the actual question. Higher accuracy, more tokens. |
| **Self-ask** | LLM breaks the question into sub-questions and answers each before synthesizing ("What do I need to know first? ... What next?...") |
| **Structured scratchpad** | Designate a specific XML or YAML block for reasoning to make it parseable (`<thinking>...</thinking>`, `<answer>...</answer>`) |

## CoT in a ReAct loop

Chain of Thought is the reasoning component inside a ReAct loop's `plan_action` call:

```
plan_action system prompt:
  "Before producing an execution plan, reason through what information you already
   have, what is still missing, and which tool call would be most useful next.
   Format your reasoning as:
   <thinking>
   ...
   </thinking>
   Then produce your execution plan below."
```

The `<thinking>` block is parsed out and logged to `tool_call_history` as a reasoning record. The execution plan is parsed from the remainder.

## Related patterns

- [01-react-loop.md](01-react-loop.md) — CoT is applied inside `plan_action` as the "Reason" step
- [08-tree-of-thoughts.md](08-tree-of-thoughts.md) — extends CoT to multiple parallel reasoning branches
- [12-self-consistency.md](12-self-consistency.md) — run CoT multiple times and take majority vote for higher accuracy
- [06-plan-and-execute.md](06-plan-and-execute.md) — the Planner step benefits greatly from CoT

## Implementation notes

- Include explicit instructions about the reasoning format in the system prompt, not the user message — so it applies on every call.
- Use `<thinking>` tags (or your project's chosen delimiter) consistently. Parse and strip them from the final response shown to users.
- Longer reasoning traces improve accuracy but increase latency and cost. Tune the level of detail for the task.
- For math/numeric tasks, CoT is almost always required — LLMs that skip reasoning steps produce far more arithmetic errors.
- CoT does not replace tool use for factual lookups. Use CoT for reasoning over retrieved information; use tools for retrieving the information itself.
