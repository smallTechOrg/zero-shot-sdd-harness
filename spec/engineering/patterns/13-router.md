# Router / Intent Classifier

**Category:** Orchestration  
**Status:** Extended

## Intent

Classify an incoming request and route it to the appropriate specialist agent, tool, or handler — without routing logic leaking into each specialist.

## When to use

- When a single agent handles multiple distinct task types that have different tools, prompts, or execution paths
- When some tasks should bypass the full agent loop (e.g., a simple FAQ can be answered from a vector store; a complex analysis needs the full ReAct loop)
- When latency or cost matters and different task types have different acceptable LLM call counts
- When you need to partition tool access: one handler sees only data tools, another sees only action tools

## How it works

```
User query
     │
     ▼
Router
  ├──[Data lookup]    ──► vector_search handler (RAG, no tool loop)
  ├──[Calculation]    ──► code_interpreter handler (execute + return)
  ├──[Research task]  ──► full ReAct loop agent
  ├──[Action request] ──► action agent (with HITL gate if irreversible)
  └──[Unknown intent] ──► clarification handler (ask user)
```

The router itself does NOT execute the task. It classifies and delegates.

## Router implementation approaches

### 1. Keyword / rule-based

```python
if "book" in query or "schedule" in query:
    return "action_handler"
elif "what is" in query or "explain" in query:
    return "rag_handler"
else:
    return "react_loop_agent"
```

Fast, zero LLM cost. Brittle on edge cases.

### 2. Semantic router

Embed a set of canonical example queries for each intent class. At runtime:
1. Embed the incoming query
2. Compute cosine similarity to each intent centroid (or example)
3. Route to the highest-similarity intent

Low latency, no LLM call, handles paraphrasing. Requires upfront curation of example queries per intent.

### 3. LLM router

Ask a small, fast LLM (or the same model with a brief prompt) to classify the intent:

```
Classify the user's intent. Choose one of:
  data_lookup | calculation | research | action | unknown

User query: "{query}"

Intent:
```

Most flexible. Adds one LLM call to every request. Use a small/fast model to minimize latency.

## Key components

1. **Intent taxonomy** — an explicit, named list of intent types this agent handles
2. **Router implementation** — one of: keyword, semantic, or LLM-based (or a combination)
3. **Default / fallback route** — what happens when classification is uncertain (`unknown` intent)
4. **Specialist handlers** — the distinct execution paths for each intent

## Variants

| Variant | Description |
|---|---|
| **Confidence threshold** | Only route if confidence > 0.8; else route to `clarification_handler` |
| **Multi-label routing** | Query spans multiple intents; send to multiple handlers in parallel and merge |
| **Cascaded routing** | Fast keyword check first; only invoke LLM router if keyword check is inconclusive |
| **Model-level routing** | Route to different LLM models (small/fast vs. large/slow) based on task complexity |

## Related patterns

- [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) — specialist handlers can be sub-agents
- [16-orchestrator-worker.md](16-orchestrator-worker.md) — the orchestrator role includes routing logic
- [15-human-in-the-loop.md](15-human-in-the-loop.md) — route ambiguous or high-stakes queries to human review
- [14-guardrails.md](14-guardrails.md) — guardrails run before (and after) the router

## Implementation notes

- Define the intent taxonomy in the spec before writing any routing code. Intent classes that aren't named don't get routed.
- Log every routing decision with the query, intent, confidence, and destination. Routing errors are the most common source of unexplained agent behaviour.
- Keep the number of intents small initially (3–5). More intents mean harder to classify and more specialist handlers to maintain.
- The `unknown` / fallback route must always do something sensible — ask for clarification or route to a general-purpose handler. Never silently drop the query.
- Semantic router example libraries: `semantic-router` (Python), but evaluate whether the library's embedding model matches your use case before adopting.
