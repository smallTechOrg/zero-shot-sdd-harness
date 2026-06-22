# Agent Graph

> **Spec status:** Filled in for the **Senior Data Analyst Agent** (`data-analyst`), v0.1, a **LangGraph** project. Last updated 2026-06-22. This file is a CRITICAL BLOCKER for tech-design approval and must stay accurate.

The agent implements the narrow core loop: **plan → generate_sql → execute_sql → summarize → finalize**, with a `handle_error` branch. Token economy is enforced node-by-node: the LLM only ever sees **schema + a few cached sample rows**, and all aggregation happens in DuckDB.

---

## State

```python
class AgentState(TypedDict):
    # Identity / inputs
    session_id: int
    question: str                       # the user's NL question
    audit_entry_id: int | None          # set when the op is logged

    # Context injected before the LLM is called (token-economy payload)
    # one entry per relevant dataset: {name, duckdb_table, schema, sample_rows}
    dataset_contexts: list[dict]        # schema + <= N sample rows ONLY
    relevant_tables: list[str]          # chosen by plan; subset of available tables
    complexity: str                     # "routine" | "complex" -> model selection

    # Pipeline data (populated progressively)
    generated_sql: str | None           # from generate_sql
    result_columns: list[str] | None     # from execute_sql (DuckDB)
    result_rows: list[list] | None       # from execute_sql (already aggregated)
    row_count: int | None
    duration_ms: int | None
    answer_text: str | None             # from summarize
    retried: bool                       # guards the single regenerate-on-error retry

    # Control
    error: str | None                   # set by any node on fatal failure
```

---

## Nodes

### `node_plan`

**Reads from state:** `session_id`, `question`, `dataset_contexts`

**Writes to state:** `relevant_tables`, `complexity`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini (`gemini-2.5-flash`) | Given the question + **schemas only** (no sample rows needed here), choose which datasets are relevant and classify routine vs. complex | fatal (set `error`) |

**Behaviour:** Uses the cached schemas of the session's datasets to decide which tables the question touches and whether it is routine (→ `gemini-2.5-flash`) or complex (→ `gemini-2.5-pro`). Narrowing `relevant_tables` here keeps later prompts small. **Token note:** sends schemas only — the cheapest signal sufficient to plan; this is a light `gemini-2.5-flash` call (or heuristic+`gemini-2.5-flash`) and never includes sample rows or data.

### `node_generate_sql`

**Reads from state:** `question`, `dataset_contexts` (filtered to `relevant_tables`), `complexity`

**Writes to state:** `generated_sql`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini (`gemini-2.5-flash` if routine, `gemini-2.5-pro` if complex) | schema + ≤ N sample rows for the relevant tables + question → a single **read-only** SQL statement | fatal (set `error`) |

**Behaviour:** Builds the compact prompt — for each relevant dataset, its schema + the ≤ N cached sample rows — and asks the model for one read-only DuckDB SQL statement. **Token note:** this is the only node that sends sample rows, and only for relevant tables; raw datasets and full result sets are never included. The generated SQL is validated as read-only before it can run.

### `node_execute_sql`

**Reads from state:** `generated_sql`, `session_id`

**Writes to state:** `result_columns`, `result_rows`, `row_count`, `duration_ms`; **also writes the audit log** (see below); may set `error`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| DuckDB | Execute the read-only SQL; measure duration; return columns + (already-aggregated) rows | On SQL error: if `not retried`, set `retried=True` and route back to `node_generate_sql` once; otherwise set `error` |
| SQLite metadata DB | Write `AuditLogEntry` (nl_prompt, generated_sql, row_count, duration_ms, status, error_message) | best-effort: log to stdout on write failure, do not crash the run |

**Behaviour:** Runs the SQL in DuckDB — **this is where aggregation happens**, in the database, not the model. Records the audit entry for the operation (success or error). On a SQL failure, allows exactly one regenerate-and-retry by routing back to `generate_sql`; a second failure is fatal. **Token note:** no LLM call here; the full result set stays in the database/process and is never sent to the model.

### `node_summarize`

**Reads from state:** `question`, `result_columns`, `result_rows`, `row_count`

**Writes to state:** `answer_text`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini (`gemini-2.5-flash`) | question + a **truncated** view of the already-aggregated result → short NL answer | fatal (set `error`) |

**Behaviour:** Produces the natural-language answer. **Token note:** sends only a truncated slice of the (already small, aggregated) result — never the full result set; the exact table shown to the user is rendered separately from DuckDB output, not from the model's text.

### `node_finalize`

See dedicated section below.

### `node_handle_error`

See dedicated section below.

---

## Edge Topology

```
START
  │
  ▼
node_plan ──(error)──────────────► node_handle_error ──► END
  │
  ▼
node_generate_sql ──(error)──────► node_handle_error ──► END
  │  ▲
  ▼  │ (one retry: execute failed and not retried)
node_execute_sql ─┴(error & retried)─► node_handle_error ──► END
  │
  ▼ (success)
node_summarize ──(error)─────────► node_handle_error ──► END
  │
  ▼
node_finalize ──► END
```

Conditional edge after `node_execute_sql`:
- `error` set **and** `retried` is True → `node_handle_error`
- `error` set **and** `retried` is False → back to `node_generate_sql` (the single retry; `execute_sql` sets `retried=True`)
- no `error` → `node_summarize`

---

## Error Handler Node (`node_handle_error`)

- Reads: `state.error`, `state.session_id`, `state.question`, `state.generated_sql`
- Updates DB: ensures an `AuditLogEntry` with `status="error"` and `error_message` exists for the failed op (if `execute_sql` didn't already write one — e.g. a `generate_sql`/`summarize` failure).
- Sets `answer_text` to a friendly, user-facing failure message (no stack trace).
- Logs the error with `session_id` context to stdout.
- Terminates the graph (returns to the API, which renders the friendly message and a persisted assistant `Message`).

---

## Finalize Node (`node_finalize`)

- Reads: `state.session_id`, `state.question`, `state.answer_text`, `state.generated_sql`, `state.result_columns`, `state.result_rows`
- Persists the assistant `Message` (answer_text + generated_sql + result_table_json) so history survives restarts.
- Bumps `Session.updated_at`.
- Returns the answer + result table + audit_entry_id to the API layer.
- Logs a one-line run summary (session_id, row_count, duration_ms).

---

## Graph Assembly (`agent/graph.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("plan", node_plan)
graph.add_node("generate_sql", node_generate_sql)
graph.add_node("execute_sql", node_execute_sql)
graph.add_node("summarize", node_summarize)
graph.add_node("finalize", node_finalize)
graph.add_node("handle_error", node_handle_error)

graph.set_entry_point("plan")

graph.add_conditional_edges(
    "plan",
    lambda s: "handle_error" if s.get("error") else "generate_sql",
)
graph.add_conditional_edges(
    "generate_sql",
    lambda s: "handle_error" if s.get("error") else "execute_sql",
)
graph.add_conditional_edges(
    "execute_sql",
    lambda s: (
        "handle_error" if s.get("error") and s.get("retried")
        else "generate_sql" if s.get("error")   # one retry
        else "summarize"
    ),
)
graph.add_conditional_edges(
    "summarize",
    lambda s: "handle_error" if s.get("error") else "finalize",
)

graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

compiled_graph = graph.compile()
```

---

## Concurrency Model

- **One question at a time per request** — each `/ask` runs one graph invocation synchronously. No background run queue in v0.1.
- **No parallel nodes** — the loop is strictly sequential (plan → generate_sql → execute_sql → summarize → finalize).
- **Checkpointing:** none in v0.1. Durability comes from the metadata DB (messages + audit log are written by `execute_sql`/`finalize`), not from a LangGraph checkpointer. (A `SqliteSaver` could be added later if multi-step investigations land — see Future Phases.)
