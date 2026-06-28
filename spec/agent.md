# Agent

> The LangGraph pipeline for answering a question over a profiled dataset. The privacy boundary (schema + aggregates only) and dialect-safe SQL-with-retry are first-class, named steps.

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Graph (LangGraph)** | Multi-step pipeline with conditional edges (the retry loop) and a named guard step. |

**Chosen:** **Graph (LangGraph)** composing **Planning (#6)** + **LLM-Generated Code Execution (#22, constrained to DuckDB SQL)** + **Exception Handling & Recovery (#12, the retry-on-SQL-error loop)** + **Guardrails (#18, the `privacy_guard` chokepoint)** + **Observability (#19, always on)**. Rationale: the task is not a single transform — it plans, writes executable SQL, runs it locally, observes errors, and recovers by regenerating SQL, then phrases. That bounded reason→act→observe→retry loop with an explicit guard is exactly a LangGraph graph with one conditional (retry) edge. We deliberately do NOT use multi-agent or reflection in Phase 1 — one planner/phraser LLM with a deterministic execution + guard is the smallest real agent. Conversation memory (#8) and a clarifying-question human-in-the-loop gate (#13) are later phases.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `plan` (plan + generate SQL) | Gemini | `gemini-3.1-pro-preview` | Needs solid SQL + reasoning over schema; one cheap call (schema only, small prompt). |
| `generate_sql` (retry regeneration) | Gemini | `gemini-3.1-pro-preview` | Same model; corrects SQL from the DuckDB error. |
| `phrase_answer` | Gemini | `gemini-3.1-pro-preview` | Phrases a concise answer from the small aggregate; small payload, low cost. |

> **Assumed:** A single model (`gemini-3.1-pro-preview`, the skeleton default — this is the ID the live Gemini API serves for the gemini-3.1-pro family) is used for all nodes — kept env-configurable via `AGENT_LLM_MODEL`. No per-node tiering in Phase 1 (resource-aware tiering is a later optimization); cost is already low because payloads are schema/aggregate-only.

**Fallback behaviour:** On a Gemini API error (network / rate-limit) the node sets `state["error"]` and routes to `handle_error`, which persists the run as `failed` with the message and returns it via the API envelope. SQL *execution* errors are NOT LLM errors — they drive the retry loop (regenerate SQL), not `handle_error`. Tests call the real Gemini API with the `.env` key; there is no offline stub path.

**Prompt strategy:** System/user split. `plan.md` and `generate_sql.md` instruct the model it is writing **DuckDB SQL**, list DuckDB date/time idioms (e.g. `date_diff('day', a, b)`, `strftime`, `date_trunc`), and explicitly forbid SQLite-isms (`julianday`, `strftime`-as-SQLite, `datetime()` SQLite forms). Output is **structured JSON** (`{"plan": str, "sql": str}` for plan; `{"sql": str}` for retry; `{"answer": str, "key_numbers": [...]}` for phrasing) parsed defensively. The `generate_sql` retry prompt is given the failed SQL and the exact DuckDB error text and asked to return corrected SQL only.

---

## Tools & Tool Calling

The "tool" is local DuckDB SQL execution. The LLM does not free-form pick tools; the graph forces the single execution path.

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `run_duckdb_sql` | Execute generated SQL locally against the dataset's DuckDB table. | `sql: str`, `dataset_path: str` | `{columns, rows}` (full, kept LOCAL) or raises on SQL error | Reads the local DuckDB file only; no external calls. |
| `extract_schema` | Read column names + DuckDB types + health summary. | `dataset_path` | schema dict | None. |
| `pick_chart` | Deterministic heuristic → chart type from the aggregate shape. | aggregate result | `{type, x, y}` | None. |

**Tool selection strategy:** Forced single path — the graph always runs `run_duckdb_sql` with the LLM-generated SQL; the LLM does not choose among tools.

**Tool failure handling:** `run_duckdb_sql` failure → set `sql_error`, increment `sql_attempts`, route to `generate_sql` (retry) until `MAX_SQL_RETRIES` (3), then `handle_error`. Schema/chart helpers raising → `handle_error`.

---

## Agent State

```python
class AnalystState(TypedDict, total=False):
    # Identity
    run_id: str                      # set at initialisation (question_runs PK)
    dataset_id: str                  # the profiled dataset being queried

    # Input
    question: str                    # the user's natural-language question
    schema: dict                     # column names + DuckDB types + health summary (NO rows)
    dataset_path: str                # local DuckDB file path

    # Pipeline data (populated progressively)
    plan: str                        # plan text from the plan node
    sql: str                         # current candidate DuckDB SQL
    sql_attempts: int                # incremented on each execution attempt (cap MAX_SQL_RETRIES)
    sql_error: str | None            # last DuckDB error text (drives retry); None on success
    result: dict                     # {columns, rows} — FULL result, kept local, NOT sent to LLM
    aggregate: dict                  # bounded summary (≤ AGG_ROW_CAP) — the ONLY result data sent to LLM
    trace: list                      # [{step, sql?, error?, ok, latency_ms}, ...] — the audit trail

    # Output
    answer: str                      # plain-English answer
    key_numbers: list                # the called-out figures
    chart: dict                      # {type, x, y} chosen by pick_chart
    cost_usd: float                  # summed from Gemini token usage this run

    # Control
    error: str | None                # fatal failure (LLM/API/guard) → handle_error
    status: str                      # "completed" | "failed"
```

Constants: `MAX_SQL_RETRIES = 3`, `AGG_ROW_CAP = 50`.

---

## Nodes / Steps

### `plan`
**Reads:** `question`, `schema`. **Writes:** `plan`, `sql`, `cost_usd`, `trace`.
**LLM call:** yes — Gemini, `plan.md` system prompt, **schema only** in the prompt. Returns `{plan, sql}` JSON.
**External calls:** Gemini — on failure set `error`, route `handle_error`.
**Behaviour:** Produces a short strategy and the first DuckDB SQL candidate. Appends a `plan` trace entry. Accumulates token cost.

### `privacy_guard`
**Reads:** the outgoing LLM payload (schema for plan; `aggregate` for phrasing). **Writes:** `aggregate` (truncated if needed), `error`, `trace`.
**LLM call:** no.
**Behaviour:** The single chokepoint enforcing "schema + bounded aggregates only to the LLM." Before the phrasing call it derives `aggregate` from `result`, capping at `AGG_ROW_CAP` rows and stripping anything that is not a schema field or an aggregate. If the payload cannot be reduced to a safe aggregate (e.g. a raw detail query of thousands of rows) it truncates to a summary and records `guard: truncated` in the trace. It never lets `result`'s full rows into an LLM prompt. (Invariant asserted by tests: no raw row value appears in any logged LLM input.)

### `generate_sql`
**Reads:** `question`, `schema`, `sql`, `sql_error`. **Writes:** `sql`, `cost_usd`, `trace`.
**LLM call:** yes — Gemini, `generate_sql.md`, given the failed SQL + the exact DuckDB error, returns corrected `{sql}`. **Schema + error only — no rows.**
**Behaviour:** The retry regeneration step. Only entered after a `execute_sql` failure. Appends a `retry` trace entry.

### `execute_sql`
**Reads:** `sql`, `dataset_path`, `sql_attempts`. **Writes:** `result`, `sql_error`, `sql_attempts`, `trace`.
**LLM call:** no.
**External calls:** DuckDB (local) — on error, set `sql_error`, increment `sql_attempts` (no `error`; the retry edge handles it).
**Behaviour:** Runs `run_duckdb_sql` locally. On success: `result` set, `sql_error=None`. On failure: capture the DuckDB error text (e.g. a Catalog Error for `julianday`), append an `execute` trace entry with the error.

### `phrase_answer`
**Reads:** `question`, `aggregate`, `plan`. **Writes:** `answer`, `key_numbers`, `cost_usd`, `trace`.
**LLM call:** yes — Gemini, `phrase_answer.md`, **only the bounded `aggregate`**. Returns `{answer, key_numbers}`.
**Behaviour:** Phrases the concise answer with the figures called out. Runs only after `privacy_guard` has set `aggregate`.

### `pick_chart`
**Reads:** `aggregate`. **Writes:** `chart`, `trace`.
**LLM call:** no.
**Behaviour:** Deterministic heuristic: one numeric measure over a categorical dimension → bar; over an ordered/time dimension → line; a small part-of-whole → pie; otherwise table-only. Picks ONE chart.

### `finalize`
**Reads:** all output fields. **Writes:** `status="completed"`.
**Behaviour:** Marks success. The runner persists the `question_runs` row (plan, sql, trace, result summary, chart, cost) after the graph returns.

### `handle_error`
**Reads:** `error`, `sql_error`, `sql_attempts`. **Writes:** `status="failed"`.
**Behaviour:** Terminal failure. The runner persists the failed run with the message (LLM error, or "SQL could not be corrected after N attempts: <last error>").

---

## Graph / Flow Topology

```
START
  │
  ▼
plan ──(error)──────────────► handle_error ──► END
  │
  ▼
privacy_guard ──(error)─────► handle_error
  │
  ▼
execute_sql
  │
  ├─(sql_error & attempts<MAX)─► generate_sql ──► execute_sql   (retry loop)
  │
  ├─(sql_error & attempts>=MAX)─► handle_error
  │
  └─(ok)──► privacy_guard(aggregate) ──► phrase_answer ──► pick_chart ──► finalize ──► END
```

> Implementation note: `privacy_guard` is invoked at two points (before `plan`'s payload conceptually, and to build `aggregate` before `phrase_answer`). In the compiled graph it is a single node placed on the post-execute path that builds `aggregate`; the pre-plan schema-only assertion is a cheap inline check inside `plan` plus the guard's logged invariant. The named node owns the result-data chokepoint.

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `plan` | `state["error"]` set | `handle_error` |
| `plan` | else | `privacy_guard` (then `execute_sql`) |
| `execute_sql` | `sql_error` and `sql_attempts < MAX_SQL_RETRIES` | `generate_sql` |
| `execute_sql` | `sql_error` and `sql_attempts >= MAX_SQL_RETRIES` | `handle_error` |
| `execute_sql` | success | `privacy_guard` → `phrase_answer` |
| `generate_sql` | always | `execute_sql` |
| `phrase_answer` | `state["error"]` set | `handle_error` |
| `phrase_answer` | else | `pick_chart` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph `AnalystState` | plan, sql, trace, result, aggregate, answer, cost |
| **Across runs** | SQLite (`datasets`, `question_runs`) | dataset schema/profile; every run's plan, sql, trace, result summary, chart, cost — tied to dataset |
| **Conversation** | none in Phase 1 (stub) | Turn history is **Phase 3** (`messages` table); Phase-1 questions are single-turn |

**Context window management:** Prompts are intrinsically small — schema (column metadata) and bounded aggregates (≤ 50 rows). No RAG / no summarization needed at Phase-1 scale. Multi-turn context (Phase 3) injects prior turns into the plan prompt.

---

## Human-in-the-Loop Checkpoints

None in Phase 1. A clarifying-question gate (ambiguous question → pause and ask) is **Phase 6** (#13). Phase 1 answers directly or fails with a clear message.

---

## Error Handling & Recovery

**Node-level:** Each node catches its own exceptions. LLM/guard failures set `state["error"]`. SQL execution failures set `state["sql_error"]` (not `error`) so the retry loop engages.

**Graph-level (`handle_error`):**
- Reads: `error` or the exhausted `sql_error` + `sql_attempts`.
- Runner updates DB: `question_runs.status="failed"`, `error_message`, `completed_at`.
- Logs with `run_id`. Terminates the graph.

**Resume / retry strategy:** The SQL retry loop is the core recovery: on a DuckDB error the exact error is fed back to `generate_sql` for corrected SQL, up to `MAX_SQL_RETRIES`. This is the explicit defense against dialect mistakes (e.g. `julianday` → Catalog Error → regenerate with a DuckDB date idiom). No cross-process checkpoint/resume in Phase 1 (runs are short).

**Partial failure:** If charting fails, the answer + table still return (chart omitted, trace notes it) — phrasing and the answer are the critical path; the chart degrades gracefully.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One trace per run, one entry per step (plan / guard / execute / retry / phrase / chart) with ok/error + latency | DB (`question_runs.trace`) + stdout structured log; surfaced in the UI "show its work" panel |
| **LLM calls** | model, prompt, output, prompt+completion tokens, latency, derived cost | structured log (stdout) + `question_runs.cost_usd` |
| **Privacy audit** | The exact LLM input payloads (must contain only schema + aggregates) | structured log — a test asserts no raw row value is present |
| **Run outcome** | status, total duration, error | DB + structured log |

> Observability is wired in Phase 1, not deferred. LangSmith is optional and off by default (local tool); structured stdout logging via the skeleton's `src/observability` is the baseline and is always on.

---

## Concurrency Model

- **Run isolation:** one question at a time per the single user; runs are scoped by `run_id` and a per-dataset DuckDB file. No 409 needed at this scale, but the API processes one `ask` synchronously.
- **Parallel nodes within a run:** none — the pipeline is sequential (the retry loop is inherently serial).
- **Checkpointing:** none (short runs, no human-in-the-loop in Phase 1).

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AnalystState)

graph.add_node("plan", plan)
graph.add_node("privacy_guard", privacy_guard)
graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_sql", execute_sql)
graph.add_node("phrase_answer", phrase_answer)
graph.add_node("pick_chart", pick_chart)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("plan")

graph.add_conditional_edges(
    "plan",
    lambda s: "handle_error" if s.get("error") else "privacy_guard",
    {"handle_error": "handle_error", "privacy_guard": "privacy_guard"},
)
# first guard pass routes straight to execution
graph.add_conditional_edges(
    "privacy_guard",
    after_guard,  # "handle_error" | "execute_sql" (pre-exec) | "phrase_answer" (post-exec, aggregate built)
    {"handle_error": "handle_error", "execute_sql": "execute_sql", "phrase_answer": "phrase_answer"},
)
graph.add_conditional_edges(
    "execute_sql",
    after_execute,  # "generate_sql" | "handle_error" | "privacy_guard"
    {"generate_sql": "generate_sql", "handle_error": "handle_error", "privacy_guard": "privacy_guard"},
)
graph.add_edge("generate_sql", "execute_sql")
graph.add_conditional_edges(
    "phrase_answer",
    lambda s: "handle_error" if s.get("error") else "pick_chart",
    {"handle_error": "handle_error", "pick_chart": "pick_chart"},
)
graph.add_edge("pick_chart", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```

`after_guard` uses a `state["phase"]` flag (`"pre"` → `execute_sql`; `"post"` → `phrase_answer`) set when the guard builds the aggregate. `after_execute` returns `generate_sql` while `sql_error` and `sql_attempts < MAX_SQL_RETRIES`, `handle_error` when exhausted, else `privacy_guard` (post-exec).
