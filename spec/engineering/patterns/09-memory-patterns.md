# Memory Patterns

**Category:** Memory  
**Status:** Extended

## Intent

Give agents access to information beyond their immediate context window by typing memory into distinct stores with different write/read lifecycles and retrieval mechanisms.

## The four memory types

### 1. Working Memory (In-context)

**What it is:** Everything currently loaded into the LLM's context window: the system prompt, the user query, and `tool_call_history` from the current run.

**Lifecycle:** Created at run start, discarded at run end.

**Stored in:** `AgentState` — the fields passed to each `plan_action` call.

**Retrieval:** No retrieval needed — it's already in context.

**Limit:** The LLM's context window. See [24-context-window-management.md](24-context-window-management.md) for strategies when working memory grows too large.

---

### 2. Episodic Memory (Past runs)

**What it is:** A log of completed agent runs — what was asked, what tools were called, what the final answer was.

**Lifecycle:** Written at run completion; persists indefinitely.

**Stored in:** The application database (`run` and `tool_call_history` tables).

**Retrieval:** Queried by run_id, time range, user, or keyword search on goal/final_answer.

**Use cases:**
- "Continue where you left off" — load context from the last run
- Audit trail — surface reasoning trace in the UI
- Failure analysis — query runs where status = 'failed'

---

### 3. Semantic Memory (Knowledge base)

**What it is:** A vector store of documents, facts, or knowledge the agent can retrieve by semantic similarity.

**Lifecycle:** Written when documents are ingested; updated when documents change.

**Stored in:** A vector database (Chroma, Pinecone, pgvector, Qdrant, etc.).

**Retrieval:** Embed the current query → cosine similarity search → return top-K chunks.

**Use cases:**
- Product documentation, policy documents, technical reference
- "What does our policy say about X?" style questions
- Provides grounding to reduce hallucination on domain-specific questions

See [10-rag.md](10-rag.md) for the full RAG pattern built on top of semantic memory.

---

### 4. Procedural Memory (Learned patterns)

**What it is:** Stored plans, templates, or learned workflows that worked well in past runs.

**Lifecycle:** Written when a successful plan is identified as generalizable; updated when refined.

**Stored in:** Database table of plan templates; optionally a vector store for similarity-based retrieval.

**Retrieval:** Match current goal to stored plans by similarity or category.

**Use cases:**
- "Last time I was asked about flight bookings, this 3-step plan worked — reuse it"
- Reduce planning time for recurring task types
- Implement skills that improve with repeated use

---

## Memory Summarization

When working memory (tool_call_history) grows too large to fit in context, summarize and replace:

```
[Summarizer LLM call]
  Input:  full tool_call_history for this run so far
  Output: one paragraph summary of what was found, what failed, and what is still needed

tool_call_history = [{"type": "summary", "content": "<paragraph>"}]
                    + last 3 tool calls (kept verbatim for recency)
```

Apply summarization when `len(tool_call_history) > threshold` before the next `plan_action` call.

---

## Which memory to use when

| Need | Memory type |
|---|---|
| Data from the current run | Working memory (`AgentState`) |
| Results from a previous run | Episodic memory (DB query) |
| Facts, policies, documents | Semantic memory (vector search) |
| Reusable plans for common tasks | Procedural memory |
| Tool call history too long for context | Working memory + summarization |

---

## Related patterns

- [01-react-loop.md](01-react-loop.md) — working memory is `AgentState`; tool_call_history is its primary content
- [10-rag.md](10-rag.md) — RAG builds on semantic memory
- [19-checkpoint-resume.md](19-checkpoint-resume.md) — checkpointing persists working memory across restarts
- [24-context-window-management.md](24-context-window-management.md) — manages working memory size
- [22-observability.md](22-observability.md) — episodic memory IS the observability trace

## Implementation notes

- Most agents in 2026 need working memory + episodic memory by default. Semantic and procedural memory add capability but cost — only add them when a clear use case exists.
- Do not use a vector store as a substitute for a well-structured relational DB. Vector search is for unstructured similarity; SQL is for structured queries. Use both for what they are good at.
- Episodic memory is most valuable when surfaced in the UI — the "reasoning trace" that shows users what the agent did and why.
- Procedural memory works best for high-volume agents with many repeated task types. It adds meaningful complexity; defer until Phase 5 or later.
