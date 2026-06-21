# Retrieval Augmented Generation (RAG)

**Category:** Tool & Resource Access  
**Status:** Extended

## Intent

Ground LLM responses in retrieved documents or knowledge, reducing hallucination and enabling the agent to answer questions about content it was not trained on.

## When to use

- Answering questions over a large, frequently-updated document corpus
- Domain-specific knowledge that post-dates the LLM's training cutoff
- Reducing hallucination on factual questions where retrieved evidence is authoritative
- Any time the answer is "in a document" rather than "in the LLM's weights"

## How it works

### Basic RAG

```
Query
  │
  ├──[Embed query] ──► embedding vector
  │
  ├──[Vector search] ──► top-K relevant chunks from the corpus
  │
  ├──[Assemble prompt] ──► system prompt + retrieved chunks + query
  │
  └──[LLM call] ──► answer grounded in retrieved content
```

Documents are ingested offline: split into chunks → embed each chunk → store in vector DB.

### Agentic RAG

Instead of one-shot retrieval, the agent decides when, what, and how many times to retrieve:

```
plan_action
  │
  ├──(needs more information) ──► invoke_tool("vector_search", query="...")
  │                               ──► observe results
  │                               ──► plan_action (with results in context)
  │                               ──► loop until enough context
  │
  └──(enough context) ──────────► FINAL ANSWER
```

The agent treats the vector store as a tool in the Tool Registry (type: `vector_search`). It calls the tool zero or more times, with different queries, until it has sufficient grounding.

## Key components

1. **Document ingester** — splits documents into chunks, embeds them, writes to vector DB
2. **Vector search tool** — takes a query string, returns top-K chunks with similarity scores and source metadata
3. **Prompt assembler** — concatenates retrieved chunks into a `[Context]` block before the user query
4. **Citation tracker** (optional) — records which chunks were used in the final answer for attribution

## Variants

| Variant | Description |
|---|---|
| **HyDE (Hypothetical Document Embeddings)** | Generate a hypothetical answer first, embed it, retrieve based on the hypothetical. Improves retrieval on obscure topics. |
| **Multi-hop RAG** | Retrieve → identify what's still missing → reformulate query → retrieve again. Repeat until sufficient. |
| **Re-ranking** | Retrieve many candidates (top-50), then re-rank by a cross-encoder or LLM relevance score, return top-K. More accurate than raw similarity. |
| **Contextual compression** | After retrieval, extract only the sentences relevant to the query from each chunk. Reduces prompt size. |
| **Hybrid search** | Combine dense vector search (semantic) with sparse keyword search (BM25). Best of both worlds. |
| **Parent-child chunking** | Index small child chunks for retrieval precision; return the full parent chunk for richer context. |

## Retrieval quality checklist

Before trusting retrieval results:
- Chunk size is appropriate for the document type (too large = noisy, too small = loses context)
- Embedding model is well-suited to the domain
- Similarity threshold is set to filter low-confidence results
- Source metadata (file name, page number, section) is stored alongside each chunk
- Retrieval is evaluated on a golden set of Q&A pairs before going to Phase 3

## Related patterns

- [02-tool-registry.md](02-tool-registry.md) — vector search registered as a `Data source` tool
- [01-react-loop.md](01-react-loop.md) — Agentic RAG is a ReAct loop where the primary tool is vector search
- [09-memory-patterns.md](09-memory-patterns.md) — semantic memory IS the vector store that RAG queries
- [07-chain-of-thought.md](07-chain-of-thought.md) — CoT is applied after retrieval to reason over the retrieved context
- [14-guardrails.md](14-guardrails.md) — output guardrail should check that the answer is consistent with retrieved context

## Implementation notes

- RAG does not guarantee factual accuracy — it guarantees that the LLM had access to the right documents. The LLM can still misinterpret or contradict them.
- Chunk overlap (e.g., 10–15% overlap between adjacent chunks) reduces the risk of splitting a key sentence across chunk boundaries.
- For production, always store source metadata with chunks. "Where did this come from?" is the first question users ask when they doubt an answer.
- Re-ranking adds one additional LLM call but significantly improves precision. Worth it for knowledge-heavy agents where retrieval quality is critical.
- Evaluate retrieval recall and precision separately from generation quality. A low recall score means the right chunks are not being retrieved — improve chunking or the query formulation. A low precision score means wrong chunks are retrieved — improve the similarity threshold or re-ranking.
