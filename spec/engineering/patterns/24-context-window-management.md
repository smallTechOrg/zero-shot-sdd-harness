# Context Window Management

**Category:** Tool & Resource Access  
**Status:** Extended

## Intent

Keep the content passed to the LLM on each `plan_action` call within a cost and reliability budget, by pruning, summarizing, or selectively including context as the agent accumulates history.

## When to use

- Any ReAct loop that may run more than 10–15 iterations
- RAG agents that retrieve long documents
- Code interpreter agents where code and output can be verbose
- Multi-turn conversational agents where the conversation history grows
- Agents that accumulate large tool results across a session

**The symptom:** `plan_action` starts producing worse results over time in a long run. The cause is usually context overload — the LLM is attending to too many tokens and the signal-to-noise ratio falls.

## How it works

The context passed to each `plan_action` call has several components:

```
System prompt        [fixed — usually 500–2000 tokens]
Available tools list [fixed per session — 200–2000 tokens depending on tool count]
User query           [fixed — usually 50–500 tokens]
tool_call_history    [GROWS — typically 200–500 tokens per entry]
```

Only `tool_call_history` grows. Manage it with one or more of the strategies below.

## Management strategies

### 1. Sliding window

Keep only the last N entries from `tool_call_history`:

```python
MAX_HISTORY_ENTRIES = 5
context_history = tool_call_history[-MAX_HISTORY_ENTRIES:]
```

**Pros:** Simple, constant context size.  
**Cons:** Older tool results are invisible — the LLM may repeat calls it already made.

### 2. Summarization

When `tool_call_history` exceeds a threshold, summarize the older entries and replace them:

```
[Summarizer LLM call]
  Input:  tool_call_history[:-3]  (all but the last 3 entries)
  Output: "Found weather data for London (18°C, cloudy). Stock price 
           API returned AAPL at $182.40. Initial news search found 
           3 relevant articles about tech earnings."

tool_call_history = [
    {"type": "summary", "content": "<above paragraph>"},
    *tool_call_history[-3:]  # keep last 3 verbatim for recency
]
```

**Trigger:** When total estimated tokens in `tool_call_history` exceeds a threshold (e.g., 4000 tokens).

**Pros:** Retains semantic content; natural context size.  
**Cons:** Adds one LLM call; summary may lose detail.

### 3. Selective inclusion

Only include tool call history entries that are relevant to the current goal state:

```python
def filter_relevant_history(history: list[dict], current_goal: str) -> list[dict]:
    # Always include: errors (self-correction context), last 2 entries (recency)
    # Optionally include: entries whose tool_name matches current execution plan
    ...
```

**Pros:** High precision; relevant content always present.  
**Cons:** Requires knowing what is relevant — non-trivial.

### 4. Structured compression

Strip verbose fields from tool results before adding to history:

```python
# Before compression
{"tool": "weather_api", "result": '{"city": "London", "temperature": 18, "condition": "cloudy", "humidity": 72, "wind_speed": 12, "wind_direction": "NW", "feels_like": 16, "uv_index": 3, ...}'}

# After compression
{"tool": "weather_api", "result": "London: 18°C, cloudy"}
```

**Pros:** Retains the key data; significant size reduction.  
**Cons:** Requires per-tool compression logic; important fields may be dropped.

## Token budget planning

Set a per-session token budget and track it:

| Component | Budget |
|---|---|
| System prompt + tools list | 2000 tokens |
| User query | 500 tokens |
| tool_call_history | 4000 tokens max |
| **Total** | **6500 tokens** (adjust per model and cost target) |

When `tool_call_history` approaches the budget, trigger summarization.

## Estimating token count

```python
def estimate_tokens(text: str) -> int:
    return len(text) // 4  # rough estimate: 1 token ≈ 4 characters
```

Use the LLM provider's tokenizer for precision (e.g., `tiktoken` for OpenAI models).

## Related patterns

- [01-react-loop.md](01-react-loop.md) — `tool_call_history` grows with every loop iteration; context management is the control valve
- [09-memory-patterns.md](09-memory-patterns.md) — summarization is how working memory transitions to episodic memory
- [10-rag.md](10-rag.md) — RAG-retrieved chunks are the most frequent source of context bloat; apply contextual compression before adding to context
- [19-checkpoint-resume.md](19-checkpoint-resume.md) — checkpointing the full (un-compressed) history enables debugging after summarization; always persist full history to DB, compress only what goes in the prompt

## Implementation notes

- Always persist the **full** `tool_call_history` to the database — never the summarized version. The summarized version goes into the LLM prompt; the full version goes to observability and audit.
- Measure context size in tokens, not characters or entries. The right trigger threshold depends on the model's context window and your cost targets.
- Implement summarization as a separate node in the agent graph, not inline in `plan_action`. This makes it testable and replaceable without touching the main loop.
- Test summarization by running long agents that would hit the context limit. Verify that performance (final answer quality) does not degrade significantly compared to a run with full history in context.
