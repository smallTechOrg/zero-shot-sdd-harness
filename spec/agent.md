# Agent

## Agent Architecture Pattern

**Chosen: Graph (LangGraph).** The analyst flow is a fixed multi-step pipeline with one conditional fan-out to error handling at each step (generate → validate → execute → format). LangGraph is already wired in the skeleton; this replaces the single `transform_text` node with the analyst nodes.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `generate_sql` | Gemini | `gemini-2.5-flash` | Fast, cheap; SQL generation from a compact schema is well within Flash's ability |
| `format_answer` | Gemini | `gemini-2.5-flash` | Prose summarization of a small result set; latency matters more than peak quality |

Model is env-configurable via `AGENT_LLM_MODEL` (blank → provider default `gemini-2.5-flash`). `validate_sql` and `execute_sql` make NO LLM call.

**Fallback behaviour:** On a Gemini API error (network/rate-limit/auth), the node catches the exception, sets `state["error"]`, and routes to `handle_error`. The API returns the turn with `status="failed"` and the error message. No offline stub — tests call the real Gemini API via `.env`.

**Prompt strategy:** System/user split via `LLMClient().call_model(prompt, system=...)`. `generate_sql` uses `src/prompts/analyst.md` as the system prompt; the user message contains ONLY the compact schema summary + a 5-row sample + recent Q&A context + the question. Output is parsed as a single SQL statement (fenced code block stripped). `format_answer` receives the question + the SQL + the (small) result rows and returns prose.

---

## Tools & Tool Calling

This graph does not use LLM tool-calling; nodes call deterministic Python helpers directly.

| Helper | Description | Inputs | Output | Side-effects |
|--------|-------------|--------|--------|--------------|
| `assert_read_only` | Reject any non-read SQL | sql | sql or raises | none |
| `run_read_only` | Execute on read-only connection | sql | `{columns, rows}` | reads SQLite only |
| `log_operation` | Append audit row | fields | none | DB write to `audit_log` |
| `schema_summary` / `sample_rows` | Build token-economical context | table_name | schema / sample | reads SQLite only |

**Tool selection strategy:** Fixed pipeline order; no LLM routing.

**Tool failure handling:** `assert_read_only` raising → `state["error"]` set in `validate_sql`, audit-logged as `operation="blocked"`, route to handle_error. `run_read_only` raising → `state["error"]`, audit-logged as failed `query`, route to handle_error.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    turn_id: str            # set at initialisation (runner)
    session_id: str         # set at initialisation
    table_name: str         # the dataset's data table, set at initialisation

    # Input / context (set at initialisation by the runner)
    question: str
    schema: list[dict]      # [{name, type}] from schema_summary()
    sample: dict            # {columns, rows} from sample_rows()
    history: list[dict]     # recent prior turns [{question, answer_text}]

    # Pipeline data
    sql_text: str | None    # written by generate_sql, validated by validate_sql
    result: dict | None     # {columns, rows} written by execute_sql

    # Output
    answer_text: str | None # written by format_answer
    status: str             # "completed" | "failed" (handle_error/finalize)

    # Control
    error: str | None       # set by any node on failure
```

---

## Nodes / Steps

### `generate_sql`
**Reads:** `question`, `schema`, `sample`, `history`. **Writes:** `sql_text`, `error`.
**LLM call:** yes — Gemini, system = `analyst.md`, user = compact context; output parsed to one SQL string.
**External calls:** Gemini → on failure set `error` (fatal).
**Behaviour:** Produces a single read-only SQL query for the question against `table_name` using only the schema + sample (never full data).

### `validate_sql`
**Reads:** `sql_text`, `session_id`, `question`. **Writes:** `error`.
**LLM call:** no.
**External calls:** `assert_read_only` (raises → `error`); `log_operation(operation="blocked")` on rejection.
**Behaviour:** The security boundary. Rejects any non-read query before it reaches the executor.

### `execute_sql`
**Reads:** `sql_text`, `session_id`, `question`. **Writes:** `result`, `error`.
**LLM call:** no.
**External calls:** `run_read_only` (read-only connection); `log_operation(operation="query")` with rows_returned + success/error.
**Behaviour:** Runs the validated SQL on a read-only connection and captures the (small) result set.

### `format_answer`
**Reads:** `question`, `sql_text`, `result`. **Writes:** `answer_text`, `error`.
**LLM call:** yes — Gemini; input is the question + SQL + the small result rows; output is analyst prose.
**External calls:** Gemini → on failure set `error`.
**Behaviour:** Writes a concise senior-analyst answer grounded in the result rows.

### `finalize`
Sets `status="completed"`. No external calls.

### `handle_error`
Sets `status="failed"`. (The runner persists `error` onto the QaTurn.)

---

## Graph / Flow Topology

```
START
  ▼
generate_sql ──(error)──► handle_error ──► END
  ▼ (ok)
validate_sql ──(error/blocked)──► handle_error
  ▼ (ok)
execute_sql ──(error)──► handle_error
  ▼ (ok)
format_answer ──(error)──► handle_error
  ▼ (ok)
finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| generate_sql | `state.get("error")` | handle_error |
| generate_sql | else | validate_sql |
| validate_sql | `state.get("error")` | handle_error |
| validate_sql | else | execute_sql |
| execute_sql | `state.get("error")` | handle_error |
| execute_sql | else | format_answer |
| format_answer | `state.get("error")` | handle_error |
| format_answer | else | finalize |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | schema, sample, sql, result, answer |
| Across runs | SQLite (`qa_turns`, `sessions`, `datasets`) | full Q&A history, dataset schema |
| Conversation | recent `qa_turns` loaded into `history` | last N (default 3) `{question, answer_text}` pairs |

**Context window management:** Token economy is the core constraint. The prompt NEVER contains full table data — only the compact schema summary, a 5-row sample, and the last 3 Q&A pairs. The format step receives only the (already small) result set.

---

## Human-in-the-Loop Checkpoints

None. The read-only guard makes execution safe without approval.

---

## Error Handling & Recovery

**Node-level:** Each node wraps its work in try/except; fatal errors set `state["error"]` and routing sends to `handle_error`.

**Graph-level (handle_error node):**
- Reads: `state.error`, `state.turn_id`
- The runner persists: `qa_turns.status="failed"`, `error_message`, after the graph returns
- Terminates the graph

**Resume / retry strategy:** None in v1 — a failed ask is retried by re-asking (a new turn).

**Partial failure:** None — any node error aborts the turn (no degraded partial answer).

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Audit | Every ingest/query/blocked op | `audit_log` table (the required full audit log) |
| Turn outcome | status, error, sql, result | `qa_turns` table |
| Logs | Node errors with turn_id | stdout (structured) |

---

## Concurrency Model

- **Run isolation:** per-turn `turn_id` scoping; SQLite single-writer is fine for a local single user. No global lock needed (reads are read-only).
- **Parallel nodes within a run:** none — strictly sequential pipeline.
- **Checkpointing:** none (no human-in-the-loop, turns are short).

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (generate_sql, validate_sql, execute_sql,
                         format_answer, finalize, handle_error)

def _build_graph():
    g = StateGraph(AgentState)
    for name, fn in [("generate_sql", generate_sql), ("validate_sql", validate_sql),
                     ("execute_sql", execute_sql), ("format_answer", format_answer),
                     ("finalize", finalize), ("handle_error", handle_error)]:
        g.add_node(name, fn)

    g.set_entry_point("generate_sql")

    def gate(next_node):
        return lambda s: "handle_error" if s.get("error") else next_node

    g.add_conditional_edges("generate_sql", gate("validate_sql"),
                            {"validate_sql": "validate_sql", "handle_error": "handle_error"})
    g.add_conditional_edges("validate_sql", gate("execute_sql"),
                            {"execute_sql": "execute_sql", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_sql", gate("format_answer"),
                            {"format_answer": "format_answer", "handle_error": "handle_error"})
    g.add_conditional_edges("format_answer", gate("finalize"),
                            {"finalize": "finalize", "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```

The runner (`src/graph/runner.py`) creates a `QaTurn` row, builds the initial state (loading schema/sample/history via the Slice A helpers), invokes `agentic_ai`, then persists `answer_text`/`sql_text`/`result`/`status`/`error_message` back onto the turn.
