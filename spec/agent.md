# Agent

## Agent Architecture Pattern

**Chosen:** Graph (LangGraph) with Tool-Use loop — a directed graph where one node calls Gemini 2.5 Flash with a bound SQL execution tool, and conditional edges route the result through query execution and response formatting before finalizing. This is the "Tool Use" pattern (#5 from `harness/patterns/agentic-ai.md`) wrapped in a LangGraph `StateGraph` for structured node-to-node state passing and explicit error routing.

Rationale: the task requires conditional routing (intent classification → data query vs. off-topic), an external tool call (DuckDB SQL execution with audit side-effects), and a finalize/error split — all of which are served by LangGraph's `StateGraph` with `add_conditional_edges`. A single-agent tool-use loop without LangGraph would not provide the structured state or explicit error-routing node needed for the audit log and streaming runner.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `classify_intent` | Google Gemini | `gemini-2.5-flash` | Low-latency classification; cheap — small structured output |
| `call_llm_with_tools` | Google Gemini | `gemini-2.5-flash` | Tool-use (function calling) to emit SQL; Flash is fast enough for analytical queries |
| `format_response` | Google Gemini | `gemini-2.5-flash` | JSON-mode call to generate narrative + ChartSpec from bounded query result |

All three nodes use the same model. Up to 3 Gemini calls per query turn: classify → SQL → format. The model is configurable via `AGENT_LLM_MODEL` env var; `GeminiProvider.DEFAULT_MODEL` is `gemini-2.5-flash`.

**Fallback behaviour:** On a Gemini API error (4xx/5xx/timeout), the node sets `state["error"]` with the exception message, and the conditional edge routes to `handle_error`. The runner yields an SSE `error` event to the client. No retry in Phase 1 (retry/backoff is Phase 2+ resilience work).

**Prompt strategy:**
- System prompt loaded from `src/prompts/analyst.md` — defines the agent persona (senior data analyst), the schema context injection format, and the constraint to use only the `execute_sql` tool to run queries (never generate data directly).
- Per-turn user message: `[SCHEMA CONTEXT]\n{schema_string}\n\n[QUESTION]\n{question}`
- Conversation history: last N messages (N≤10) prepended as prior turns to give the model continuity. History is fetched from SQLite `messages` table.
- Tool definition: `execute_sql` with a single `sql` string parameter. Gemini returns a function call; the graph executes it.
- Structured output: the `format_response` node uses a second Gemini call with JSON mode to produce the `RichResponseModel` (narrative text + chart spec).

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `execute_sql` | Execute a DuckDB SQL query against the session's registered datasets | `sql: str` — the SQL statement to run | `QueryResultModel` (columns: list[str], rows: list[list[Any]], row_count: int) | Writes `QueryLog` row to SQLite (timestamp, session_id, dataset_name, sql, row_count, latency_ms, error if any) |

**Tool selection strategy:** The LLM is given exactly one tool (`execute_sql`). The system prompt instructs it to always use this tool to answer data questions — never to generate data from memory. Classification happens in a prior node before the tool-calling node is reached, so the LLM in `call_llm_with_tools` is only ever asked data questions.

**Tool failure handling:** DuckDB errors (syntax error, column not found, etc.) are caught in `execute_query`; the error is written to the `QueryLog` and set on `state["query_error"]`. The conditional edge from `execute_query` routes to `handle_error` on fatal errors, or loops back for a clarification message on recoverable ones (e.g. column name typo).

> **Assumed:** In Phase 1, all DuckDB errors route to `handle_error` (no clarification retry loop). Retry-on-SQL-error is Phase 2 scope.

---

## Agent State

```python
class AnalystState(TypedDict, total=False):
    # Identity
    session_id: str           # set at invocation — SQLite session UUID
    message_id: str           # set at invocation — new message UUID for this turn

    # Input
    question: str             # user's natural-language question
    conversation_history: list[dict]  # last N messages [{role, content}] from SQLite

    # Pipeline data (populated progressively by nodes)
    intent: str               # "data_query" | "clarification" | "off_topic" — set by classify_intent
    schema_context: str       # compact schema string — set by build_schema_context
    datasets: list[dict]      # [{"name": str, "file_path": str, "columns": [...]}] — set by build_schema_context
    sql: str | None           # SQL from Gemini tool call — set by call_llm_with_tools
    query_result: dict | None # QueryResultModel as dict — set by execute_query
    query_log_id: str | None  # UUID of QueryLog row — set by execute_query

    # Output
    narrative: str | None     # markdown narrative text — set by format_response
    chart_spec: dict | None   # ChartSpec as dict — set by format_response; None if no chart
    rich_response: dict | None  # RichResponseModel as dict — set by format_response

    # Control
    error: str | None         # fatal error message — set by any node on unrecoverable failure
    query_error: str | None   # DuckDB execution error — set by execute_query (recoverable errors)
    status: str               # "running" | "completed" | "failed" — updated by finalize/handle_error
```

---

## Nodes / Steps

### `classify_intent`

**Reads from state:** `question`

**Writes to state:** `intent`

**LLM call:** Yes. Sends a short classification prompt to Gemini 2.5 Flash: "Classify this question as one of: data_query, clarification, off_topic. Reply with only the label." Returns a plain string label.

**External calls:** None beyond the LLM.

**Behaviour:** Determines how the graph should route the question. A `data_query` proceeds to `build_schema_context`. A `clarification` or `off_topic` skips SQL generation and routes to `format_response` with a canned text response (no tool call). Sets `state["intent"]`.

---

### `build_schema_context`

**Reads from state:** `session_id`

**Writes to state:** `schema_context`, `datasets`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | SELECT datasets WHERE session_id = ? | Fatal — sets state["error"] |

**Behaviour:** Loads all `Dataset` rows for the session from SQLite. For each dataset, reads the stored `columns_json` (column names + types) and `row_count`. Assembles a compact schema string:

```
Dataset: sales.csv (1234 rows)
  - date: DATE
  - region: VARCHAR
  - revenue: DOUBLE
```

The schema string is injected into the LLM prompt. Raw data rows are never loaded or included. Sets `state["datasets"]` as a list of dicts with `name`, `file_path`, `columns`, `row_count`. If no datasets exist for the session, sets `state["error"]` with "No datasets uploaded for this session."

---

### `call_llm_with_tools`

**Reads from state:** `question`, `schema_context`, `conversation_history`

**Writes to state:** `sql`

**LLM call:** Yes. Sends system prompt + schema context + conversation history + question to Gemini 2.5 Flash with the `execute_sql` function declaration. Expects the model to return a `FunctionCall` for `execute_sql` with a `sql` parameter.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | `generate_content` with tools | Fatal — sets state["error"] with API error message |

**Behaviour:** Constructs the full prompt by prepending the system prompt (from `src/prompts/analyst.md`), injecting the schema context block, and appending conversation history as prior turns. Calls `GeminiProvider.call_with_tools(prompt, tools=[execute_sql_tool])`. If the model returns a function call, extracts `sql`. If the model returns plain text instead (clarification case caught by intent but passed through), routes to `format_response` directly without a SQL string.

---

### `execute_query`

**Reads from state:** `sql`, `datasets`, `session_id`

**Writes to state:** `query_result`, `query_log_id`, `query_error`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| DuckDB (in-memory) | Open connection, register dataset views, execute SQL | Catches `duckdb.Error`; sets state["query_error"]; writes error to QueryLog |
| SQLite | INSERT QueryLog row | Non-fatal — logs warning if audit insert fails |

**Behaviour:** Opens a DuckDB in-memory connection. Registers each dataset from `state["datasets"]` as a named view using `duckdb.read_csv_auto(file_path)` (or the pandas-based path for Excel). Records start time. Executes `state["sql"]`. On success: captures column names, rows (capped at 500 rows), row_count, and latency_ms; writes `QueryLog` to SQLite; sets `state["query_result"]` and `state["query_log_id"]`. On DuckDB error: writes error to `QueryLog` with `error` field; sets `state["query_error"]`; does NOT set `state["error"]` (non-fatal in Phase 1 for SSE — routes to `handle_error` via conditional edge).

---

### `format_response`

**Reads from state:** `query_result`, `question`, `intent`, `query_error`, `narrative` (if off_topic path)

**Writes to state:** `narrative`, `chart_spec`, `rich_response`

**LLM call:** Yes (for data_query path). Sends a formatting prompt to Gemini 2.5 Flash with JSON output mode: "Given this SQL result, write a 2-3 sentence markdown summary and return a JSON object with keys: `narrative` (markdown string) and `chart_spec` (object with `type`, `labels`, `datasets` — or null if no chart is useful)."

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | `generate_content` with JSON response mode | Falls back to plain text narrative without chart_spec |

**Behaviour:**
- `data_query` path: calls Gemini with the query result (column names + rows only, no raw data context beyond what was returned). Auto-selects chart type: if result has 1 numeric column and ≤20 rows → bar; if result has a date/time column → line; if result has 2 columns (label, value) with ≤8 rows → pie; else no chart. Assembles `RichResponseModel`.
- `clarification` / `off_topic` path: sets a canned `narrative` text; `chart_spec` is None.
- `query_error` path: sets narrative to a user-friendly error message explaining the SQL failed and suggesting the user rephrase.

---

### `handle_error`

**Reads from state:** `error`, `query_error`, `session_id`, `message_id`

**Writes to state:** `status`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | UPDATE messages SET status='failed', error=state["error"] WHERE id=message_id | Log and continue |

**Behaviour:** Sets `state["status"] = "failed"`. Uses `state.get("error") or state.get("query_error")` as the error text to persist. Persists the error to the message record. The runner catches the error state and yields an SSE `error` event to the client.

---

### `finalize`

**Reads from state:** `rich_response`, `session_id`, `message_id`

**Writes to state:** `status`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | UPDATE messages SET status='completed', content=rich_response WHERE id=message_id | Log warning |

**Behaviour:** Sets `state["status"] = "completed"`. Persists the completed message content to SQLite.

---

## Graph / Flow Topology

```
START
  │
  ▼
classify_intent ──(error)──────────────────────────► handle_error ──► END
  │
  ▼
  ├──(intent == "off_topic" or "clarification")──► format_response
  │
  └──(intent == "data_query")──► build_schema_context ──(error)──► handle_error
                                          │
                                          ▼
                               call_llm_with_tools ──(error)──► handle_error
                                          │
                                          ▼
                                   execute_query ──(query_error)──► handle_error
                                          │
                                          ▼
                                   format_response ──(error)──► handle_error
                                          │
                                          ▼
                                       finalize
                                          │
                                          ▼
                                         END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `classify_intent` | `state.get("error")` | `handle_error` |
| `classify_intent` | `state["intent"] in ("off_topic", "clarification")` | `format_response` |
| `classify_intent` | `state["intent"] == "data_query"` | `build_schema_context` |
| `build_schema_context` | `state.get("error")` | `handle_error` |
| `build_schema_context` | no error | `call_llm_with_tools` |
| `call_llm_with_tools` | `state.get("error")` | `handle_error` |
| `call_llm_with_tools` | no error | `execute_query` |
| `execute_query` | `state.get("query_error")` | `handle_error` |
| `execute_query` | no error | `format_response` |
| `format_response` | `state.get("error")` | `handle_error` |
| `format_response` | no error | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph `AnalystState` TypedDict | All in-progress pipeline data for the current question |
| Across turns (conversation) | SQLite `messages` table | Per-session message list with role, content, status |
| Across sessions | SQLite `sessions` + `datasets` tables | Session metadata and dataset records (schema, file path) |
| Dataset files | Filesystem `data/uploads/<session_id>/` | Raw uploaded files read by DuckDB per-request |

**Context window management:** Conversation history is capped at the last 10 messages (5 user + 5 assistant turns) before injection into the prompt. If the schema context for all datasets exceeds 4000 characters, dataset schemas are truncated to the first 20 columns each with a `[...N more columns]` suffix. Raw data rows are never included.

---

## Human-in-the-Loop Checkpoints

Not applicable. The analyst agent runs fully autonomously per question. The only human interaction is the chat input itself.

---

## Error Handling & Recovery

**Node-level:** Each node wraps its logic in a try/except. Fatal errors set `state["error"]` and allow the conditional edge to route to `handle_error`. DuckDB execution errors set `state["query_error"]` (distinguished from fatal errors so the runner can emit a user-friendly message rather than a generic failure).

**Graph-level (handle_error node):**
- Reads: `state["error"]` or `state["query_error"]`, `state["session_id"]`, `state["message_id"]`
- Updates SQLite: message status → "failed", error text stored
- Logs structured error with session_id context via `structlog`
- Terminates graph; runner yields SSE `error` event

**Resume / retry strategy:** No resume from checkpoint in Phase 1. A failed question can be re-asked by the user. Each question is an independent graph invocation.

**Partial failure:** If `format_response` cannot produce a chart (Gemini JSON parse error), it falls back to text-only narrative without chart. This is the only graceful degradation in Phase 1.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Node entry/exit | Node name, session_id, timestamp | `structlog` structured log |
| LLM call | Model, token usage (if available from SDK), latency | `structlog` structured log |
| Tool call (execute_sql) | SQL text, dataset_name, row_count, latency_ms, error | SQLite `query_logs` table + structlog |
| Run outcome | status (completed/failed), session_id, message_id, total latency | SQLite `messages` table + structlog |

---

## Concurrency Model

- **Run isolation:** Each SSE request invokes `run_analyst()` as an independent generator. Multiple concurrent questions from the same session are not prevented in Phase 1 but are unlikely in single-user mode. Each invocation uses its own DuckDB in-memory connection and its own `AnalystState`.
- **Parallel nodes within a run:** None. The graph is sequential (linear path with conditional edges). No `Send` or `fanout` nodes.
- **Checkpointing:** No LangGraph checkpointer is used. Conversation history is loaded from SQLite at the start of each run (not from LangGraph's checkpointer).

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AnalystState
from graph.nodes import (
    classify_intent,
    build_schema_context,
    call_llm_with_tools,
    execute_query,
    format_response,
    handle_error,
    finalize,
)
from graph.edges import (
    after_classify,
    after_schema,
    after_llm,
    after_execute,
    after_format,
)


def _build_graph() -> StateGraph:
    g = StateGraph(AnalystState)

    g.add_node("classify_intent", classify_intent)
    g.add_node("build_schema_context", build_schema_context)
    g.add_node("call_llm_with_tools", call_llm_with_tools)
    g.add_node("execute_query", execute_query)
    g.add_node("format_response", format_response)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("classify_intent")

    g.add_conditional_edges(
        "classify_intent",
        after_classify,
        {
            "build_schema_context": "build_schema_context",
            "format_response": "format_response",
            "handle_error": "handle_error",
        },
    )
    g.add_conditional_edges(
        "build_schema_context",
        after_schema,
        {"call_llm_with_tools": "call_llm_with_tools", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "call_llm_with_tools",
        after_llm,
        {"execute_query": "execute_query", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_query",
        after_execute,
        {"format_response": "format_response", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "format_response",
        after_format,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


analyst_graph = _build_graph()
```

The `after_*` edge functions in `src/graph/edges.py` each return the appropriate target key by inspecting `state.get("error")`, `state.get("query_error")`, and `state.get("intent")`.
