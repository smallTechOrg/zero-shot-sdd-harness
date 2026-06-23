# Agent

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Graph (LangGraph)** | Multi-step pipeline with a conditional error edge. |

**Chosen:** **Graph (LangGraph)** — a short prompt-chain (`generate_sql → execute_sql → compose_answer → finalize`) with one conditional error edge. It composes three catalogue patterns from [`harness/patterns/agentic-ai.md`](../harness/patterns/agentic-ai.md): **Prompt Chaining (#1)** for the ordered SQL→execute→answer steps, **Resource-Aware Optimization (#16)** for the token-economy mechanism (schema cache + sample + result-only prompting), and **Exception Handling & Recovery (#12)** for the error edge. A single tool-use loop is rejected because the steps are fixed and ordered, and we want each step's prompt input bounded for token economy — not the model freely deciding round-trips.

> Phase 5 (later) adds **Planning (#6)** + **Reflection (#4)** for senior-analyst mode. Not in Phase 1.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `generate_sql` | Google Gemini | `gemini-2.5-flash` (env `AGENT_LLM_MODEL`) | Fast, cheap; text-to-SQL over a tiny schema+sample prompt |
| `compose_answer` | Google Gemini | `gemini-2.5-flash` | Phrasing a formatted answer over a small result set |

Both calls go through `LLMClient().call_model(prompt, *, system=...)`. Never call the Gemini SDK directly.

**Fallback behaviour:** Production resilience only — on a Gemini error or rate-limit the calling node catches the exception, sets `state["error"]`, and routes to `handle_error`. No offline/stub path; tests call the real Gemini API with `AGENT_GEMINI_API_KEY` from `.env`.

**Prompt strategy:** System/user split via the `system=` argument. `generate_sql` system prompt = `src/prompts/text_to_sql.md` (rules: SQLite dialect, one read-only `SELECT`, reference only the given table name, return SQL only — no prose/markdown fences). User content = cached schema + ≤ 20-row sample + the question. `compose_answer` system prompt = `src/prompts/answer.md`. User content = the question + the result set (columns + rows, capped). Output is plain SQL (string) and plain formatted text respectively — no JSON-mode needed in Phase 1.

---

## Tools & Tool Calling

This flow uses **fixed-step nodes**, not LLM-chosen tools. The deterministic operations the nodes perform:

| Operation | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `validate_and_execute_sql` | Sandbox-validate + run read-only SELECT | sql, allowed table(s) | result columns + rows + row_count + duration | reads `ds_<id>`; writes `audit_log` |
| `write_audit` | Record an operation | op, sql, metadata, success/error | audit row id | writes `audit_log` |

**Tool selection strategy:** None — order is fixed by the graph. The LLM only emits SQL text and answer text.

**Tool failure handling:** Sandbox violation or SQL execution error → node records the failed `audit_log` entry, sets `state["error"]`, routes to `handle_error`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    query_id: str            # set at initialisation (queries row id)
    dataset_id: str          # set at initialisation
    table_name: str          # "ds_<dataset_id>", set at initialisation

    # Input
    question: str            # the user's NL question, from the trigger
    schema_text: str         # cached schema string, from the datasets row
    sample_text: str         # ≤20-row sample string, from the datasets row

    # Pipeline data (populated progressively by nodes)
    generated_sql: str       # set by generate_sql
    result_columns: list[str]  # set by execute_sql
    result_rows: list[list]    # set by execute_sql (capped)
    row_count: int             # set by execute_sql
    duration_ms: int           # set by execute_sql

    # Output
    answer_text: str         # set by compose_answer
    status: str              # "completed" | "failed", set by finalize/handle_error

    # Control
    error: str | None        # set by any node on fatal failure
```

> Note: `schema_text`/`sample_text` come from the cached fields on the `datasets` row — the agent never reads full dataset rows into state for the LLM.

---

## Nodes / Steps

### `generate_sql`

**Reads from state:** `question`, `schema_text`, `sample_text`, `table_name`

**Writes to state:** `generated_sql`, or `error`

**LLM call:** Yes. System = `src/prompts/text_to_sql.md`; user = schema + ≤20-row sample + question. Model `gemini-2.5-flash`. Output = a single SQL string (fences stripped).

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (via `LLMClient`) | generate SQL | fatal (set `error`) |

**Behaviour:** Builds the bounded prompt (NO full rows), asks Gemini for one read-only `SELECT` over `table_name`, strips any markdown fences, stores it in `generated_sql`.

### `execute_sql`

**Reads from state:** `generated_sql`, `table_name`, `dataset_id`, `query_id`

**Writes to state:** `result_columns`, `result_rows`, `row_count`, `duration_ms`, or `error`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQL sandbox + SQLite (`ds_<id>`) | validate (SELECT-only, table allow-list) + read-only execute | fatal (set `error`) |
| SQLite (`audit_log`) | write audit entry (op=`query`, exact SQL, row_count, columns, duration, success/error) | logged; non-fatal for the audit write itself |

**Behaviour:** Validates the SQL through `src/sql/sandbox.py`, executes read-only with a row cap, captures columns/rows/count/duration, and writes the `audit_log` entry (always — success OR error). On violation/error sets `state["error"]`.

### `compose_answer`

**Reads from state:** `question`, `result_columns`, `result_rows`, `row_count`

**Writes to state:** `answer_text`, or `error`

**LLM call:** Yes. System = `src/prompts/answer.md`; user = question + result set (columns + rows, capped — already small). Model `gemini-2.5-flash`. Output = formatted text.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (via `LLMClient`) | compose answer | fatal (set `error`) |

**Behaviour:** Phrases a senior-analyst-style formatted text answer grounded ONLY in the result set. Never re-queries or invents rows.

### `finalize`

**Reads from state:** all output fields, `query_id`

**Writes to state:** `status="completed"`

**Behaviour:** Marks the run completed. (The `queries` row persistence happens in the runner after `invoke`, see below.)

### `handle_error`

**Reads from state:** `error`, `query_id`

**Writes to state:** `status="failed"`

**Behaviour:** Terminal failure node — the runner persists `status=failed` and `error` to the `queries` row.

---

## Graph / Flow Topology

```
START
  │
  ▼
generate_sql ──(error)──► handle_error ──► END
  │
  ▼
execute_sql ──(error)──► handle_error ──► END
  │
  ▼
compose_answer ──(error)──► handle_error ──► END
  │
  ▼
finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `generate_sql` | `state.get("error")` | `handle_error` else `execute_sql` |
| `execute_sql` | `state.get("error")` | `handle_error` else `compose_answer` |
| `compose_answer` | `state.get("error")` | `handle_error` else `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | The single query's SQL, result, answer |
| **Across runs** | SQLite (`datasets`, `queries`, `audit_log`) | Datasets, full query/answer history, audit trail |
| **Conversation** | `queries` rows fetched by the UI on load | Past Q&A history (re-fetched, not re-prompted in Phase 1) |

**Context window management (the token-economy mechanism — CENTRAL):**
- The LLM NEVER receives full dataset rows.
- `generate_sql` sees only the **cached schema** (column names + types, computed once at ingest and stored on the `datasets` row) plus a **≤ 20-row sample** (also cached at ingest).
- `compose_answer` sees only the **query result set** (already small; capped to a row/char limit before prompting).
- Schemas/samples are cached at ingest so repeated questions on the same dataset cost zero extra schema-derivation work.

---

## Human-in-the-Loop Checkpoints

None in Phase 1. (Phase 5 senior-analyst mode may surface a plan for review — deferred.)

---

## Error Handling & Recovery

**Node-level:** Each node wraps its work in try/except; on failure it sets `state["error"]` and (for `execute_sql`) writes a failed `audit_log` entry.

**Graph-level (`handle_error` node):**
- Reads `state.error`, `state.query_id`
- Sets `status="failed"`; the runner persists `status` + `error` to the `queries` row
- Terminates the graph

**Resume / retry strategy:** No automatic resume in Phase 1 — a failed query is surfaced to the user, who can re-ask. (Gemini transient errors propagate as a failed query with the error visible in the audit panel.)

**Partial failure:** The flow is short and each step is required; there is no degraded partial answer — a failure routes to `handle_error` and the UI shows the error plus the audit entry.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Audit (first-class)** | Every ingest + query: timestamp, exact SQL, row_count, columns, duration_ms, success/error | `audit_log` table + `GET /audit` + UI panel |
| **LLM calls** | Implicit via node success/failure; errors recorded in audit + query row | `audit_log` / `queries.error` |
| **Run outcome** | `queries.status`, duration, error | `queries` table |

---

## Concurrency Model

- **Run isolation:** Per-request, scoped by `query_id`. SQLite is the single store; a query run is short and synchronous within its request.
- **Parallel nodes within a run:** None — the chain is strictly sequential.
- **Checkpointing:** None (no LangGraph checkpointer needed; persistence is the `queries`/`audit_log` rows written by the runner).

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_sql", execute_sql)
graph.add_node("compose_answer", compose_answer)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("generate_sql")

graph.add_conditional_edges(
    "generate_sql",
    lambda s: "handle_error" if s.get("error") else "execute_sql",
    {"execute_sql": "execute_sql", "handle_error": "handle_error"},
)
graph.add_conditional_edges(
    "execute_sql",
    lambda s: "handle_error" if s.get("error") else "compose_answer",
    {"compose_answer": "compose_answer", "handle_error": "handle_error"},
)
graph.add_conditional_edges(
    "compose_answer",
    lambda s: "handle_error" if s.get("error") else "finalize",
    {"finalize": "finalize", "handle_error": "handle_error"},
)

graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```

The runner (`src/graph/runner.py`) creates the `queries` row, loads cached `schema_text`/`sample_text` from the `datasets` row, invokes the graph, then persists `generated_sql`, result columns/rows, `answer_text`, `status`, and `error` back to the `queries` row.
