# Agent

## Agent Architecture Pattern

**Chosen:** Prompt Chaining (#1) within a LangGraph StateGraph, with Exception Handling and Recovery (#12).

The analysis task has a fixed, ordered sequence of steps with clear data dependencies between them (schema → plan → computation → answer → chart), making prompt chaining the correct pattern. There is no branching based on input type in Phase 1 (CSV only), and no need for a ReAct tool-calling loop — the pandas operations are deterministic given the plan. LangGraph is used because it provides built-in conditional error routing and explicit state typing, which the existing skeleton already wires. The base ReAct pattern is upgraded to Planning + Prompt Chaining because the agent's "tool use" is not open-ended — it executes a fixed sequence of well-defined transforms.

Phases 3+ will layer in Reflection (#4) for plan quality and Memory (#8) for multi-turn conversation history per dataset.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|---|---|---|---|
| `plan_analysis` | Google Gemini | `gemini-2.5-flash` | Structured JSON output required; Flash is fast and cost-efficient for planning |
| `generate_answer` | Google Gemini | `gemini-2.5-flash` | Natural language generation; Flash quality is sufficient for data narration |

Model is env-configurable via `AGENT_LLM_MODEL`; defaults to `gemini-2.5-flash`.

**Fallback behaviour:** Each LLM-calling node wraps the call in a try/except. On any exception (4xx, 5xx, timeout, invalid JSON), the node sets `state["error"]` and the conditional edge routes to `handle_error`. `plan_analysis` retries once before erroring (the plan must be valid JSON; a single retry catches transient malformed responses). No other nodes retry. The user sees the error message in the browser; no crash, no 5xx.

**Prompt strategy:**
- `plan_analysis`: system prompt from `src/prompts/analysis_plan.md` (describes output JSON schema); user message = schema summary + question. Expects a JSON response with keys `{ pandas_ops: [...], chart_type: str, chart_columns: [...] }`. Validated with `json.loads()` after extraction; retried once on parse failure.
- `generate_answer`: system prompt from `src/prompts/answer.md` (instructs concise plain-English narration); user message = question + computed_data summary. Plain text response; no JSON parsing.

---

## Tools & Tool Calling

The agent does not use LLM function-calling (tool_use) protocol. The LLM produces structured text that the nodes parse and execute deterministically. Tool-style operations are implemented as Python functions called directly by nodes.

| Tool name | Description | Inputs | Output | Side-effects |
|---|---|---|---|---|
| `parse_csv` | Load CSV from disk into pandas DataFrame | `dataset_path: str` | `(df: DataFrame, schema_summary: str)` | None |
| `compute_schema_summary` | Extract column names, dtypes, shape, sample rows | `df: DataFrame` | `schema_summary: str` (≤ 20 cols, 5 rows) | None |
| `execute_pandas_ops` | Run a list of pandas operations from the plan | `df: DataFrame, ops: list[dict]` | `computed_data: dict` | None |
| `build_plotly_figure` | Construct Plotly figure dict from computed_data and plan | `computed_data: dict, plan: dict` | `chart_json: str` (JSON) or `None` | None |
| `persist_dataset` | Write DatasetRow to SQLite | `filename, row_count, column_names, dataset_path` | `dataset_id: str` | DB write |
| `persist_analysis` | Write AnalysisRow to SQLite | `dataset_id, question, answer, chart_json, status, error` | `analysis_id: str` | DB write |

**Tool selection strategy:** Fixed sequence — nodes call specific tools in order; no LLM-based tool selection.

**Tool failure handling:** Each tool call is wrapped in the enclosing node's try/except. Failure sets `state["error"]`; graph routes to `handle_error`.

---

## Agent State

```python
from typing import TypedDict

class AgentState(TypedDict, total=False):
    # Identity
    run_id: str            # set at graph entry by run_analysis(); UUID string

    # Dataset context (populated by ingest_csv or set before graph entry for analysis runs)
    dataset_id: str        # UUID of the DatasetRow in the datasets table
    dataset_path: str      # absolute path: data/uploads/<dataset_id>.csv

    # Input
    question: str          # the user's natural-language question

    # Pipeline data (populated progressively by nodes)
    schema_summary: str    # column names, dtypes, shape, sample rows — built by ingest_csv
    analysis_plan: dict    # parsed JSON from plan_analysis: {pandas_ops, chart_type, chart_columns}
    computed_data: dict    # result of execute_analysis: {result_label: value_or_series, ...}

    # Output (populated by generate_answer and generate_chart)
    answer_text: str       # plain-English answer from generate_answer
    chart_json: str | None # Plotly figure JSON string from generate_chart; None if no chart

    # Control
    error: str | None      # set by any node on fatal failure; triggers handle_error edge
    status: str            # "pending" | "completed" | "failed"
```

---

## Nodes / Steps

### `ingest_csv`

**Reads from state:** `dataset_path`, `dataset_id`

**Writes to state:** `schema_summary`

**LLM call:** No

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | `pd.read_csv(dataset_path)` | Fatal — set `state["error"]`; route to handle_error |
| SQLite | Update `DatasetRow.row_count` and `column_names_json` if not yet set | Fatal — set `state["error"]` |

**Behaviour:** Reads the CSV file from disk using pandas. Computes `schema_summary`: a text block with column names, inferred dtypes, dataset shape (rows × cols), and up to 5 sample rows as a markdown table. Caps at 20 columns (takes first 20 if wider) and 5 rows to keep the downstream prompt bounded. Writes `schema_summary` to state. This node runs on both the initial upload path (where DatasetRow already exists) and on re-analysis of an existing dataset.

---

### `plan_analysis`

**Reads from state:** `schema_summary`, `question`

**Writes to state:** `analysis_plan`

**LLM call:** Yes — `gemini-2.5-flash`, system prompt `src/prompts/analysis_plan.md`, structured JSON response.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | Generate analysis plan JSON | Retry once; on second failure set `state["error"]` |

**Behaviour:** Calls Gemini with the schema summary and question. Expects a JSON response with this schema:
```json
{
  "pandas_ops": [
    { "op": "groupby", "by": "region", "agg": {"revenue": "mean"} }
  ],
  "chart_type": "bar",
  "chart_columns": { "x": "region", "y": "revenue_mean" },
  "reasoning": "The question asks for average revenue by region..."
}
```
Extracts JSON from the response (handles markdown code fences). Validates with `json.loads()`. If the first attempt produces invalid JSON, retries once with the same prompt. Writes parsed dict to `state["analysis_plan"]`.

---

### `execute_analysis`

**Reads from state:** `dataset_path`, `analysis_plan`

**Writes to state:** `computed_data`

**LLM call:** No

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Re-reads CSV (if df not in state; always re-reads for correctness) | Fatal — set `state["error"]` |

**Behaviour:** Loads the CSV into a pandas DataFrame (fresh read — no in-memory caching between graph invocations). Interprets `analysis_plan["pandas_ops"]` as a sequence of pandas operations drawn from a safe whitelist: `groupby`, `agg`, `sort_values`, `head`, `describe`, `value_counts`, `filter`, `resample`. Each op is applied in sequence; the result of each op is stored in `computed_data` keyed by a descriptor string. Operations not on the whitelist are skipped with a warning logged (never executed). Final `computed_data` is a dict of `{label: serializable_value}` where values are Python scalars, lists, or dicts (DataFrames converted via `.to_dict(orient="records")`).

---

### `generate_answer`

**Reads from state:** `question`, `computed_data`, `schema_summary`

**Writes to state:** `answer_text`

**LLM call:** Yes — `gemini-2.5-flash`, system prompt `src/prompts/answer.md`, plain text response.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | Generate plain-English answer | Fatal — set `state["error"]` |

**Behaviour:** Calls Gemini with the original question, the schema summary (for column context), and the computed_data (serialized as compact JSON, limited to 4,000 characters to keep within token budget). The system prompt instructs the model to write a concise, factual, plain-English answer — 1–3 sentences, no markdown, no preamble. Response text is written directly to `state["answer_text"]`.

---

### `generate_chart`

**Reads from state:** `computed_data`, `analysis_plan`, `question`

**Writes to state:** `chart_json`

**LLM call:** No (pure Python/Plotly)

**External calls:** None

**Behaviour:** Constructs a Plotly `go.Figure` dict programmatically from `computed_data` and `analysis_plan["chart_type"]` / `analysis_plan["chart_columns"]`. Supported chart types: `bar`, `line`, `scatter`, `pie`, `histogram`. If `chart_type` is missing, unrecognized, or if `computed_data` lacks the expected columns, sets `chart_json = None` (the UI gracefully shows only the text answer). On success, serializes the Plotly figure to JSON via `plotly.io.to_json()` and writes the string to `state["chart_json"]`. Validates that the resulting string is parseable JSON before writing.

---

### `finalize`

**Reads from state:** `run_id`, `dataset_id`, `question`, `answer_text`, `chart_json`

**Writes to state:** `status = "completed"`

**LLM call:** No

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Upsert `AnalysisRow` with answer, chart_json, status=completed | Log error; do not re-raise (result already computed) |

**Behaviour:** Persists the completed analysis to the `analyses` table. Writes `status = "completed"` to state so the graph terminates cleanly.

---

### `handle_error`

**Reads from state:** `error`, `run_id`, `dataset_id`, `question`

**Writes to state:** `status = "failed"`

**LLM call:** No

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Upsert `AnalysisRow` with status=failed, error_message | Log only — do not raise |

**Behaviour:** Persists the failed analysis to the `analyses` table with `status = "failed"` and `error_message = state["error"]`. Logs the error with `run_id` context using structlog. Sets `state["status"] = "failed"`. The graph terminates. The API layer reads `state["error"]` and returns it in the response body — the user sees the error message in the browser.

---

## Graph / Flow Topology

```
START
  │
  ▼
ingest_csv ──(error)──────────────────────────────────────► handle_error ──► END
  │
  ▼
plan_analysis ──(error)───────────────────────────────────► handle_error
  │
  ▼
execute_analysis ──(error)────────────────────────────────► handle_error
  │
  ▼
generate_answer ──(error)─────────────────────────────────► handle_error
  │
  ▼
generate_chart ──(error)──────────────────────────────────► handle_error
  │
  ▼
finalize
  │
  ▼
END
```

**Conditional edges:**

| Source node | Condition | Target |
|---|---|---|
| `ingest_csv` | `state.get("error")` is not None | `handle_error` |
| `ingest_csv` | `state.get("error")` is None | `plan_analysis` |
| `plan_analysis` | `state.get("error")` is not None | `handle_error` |
| `plan_analysis` | `state.get("error")` is None | `execute_analysis` |
| `execute_analysis` | `state.get("error")` is not None | `handle_error` |
| `execute_analysis` | `state.get("error")` is None | `generate_answer` |
| `generate_answer` | `state.get("error")` is not None | `handle_error` |
| `generate_answer` | `state.get("error")` is None | `generate_chart` |
| `generate_chart` | `state.get("error")` is not None | `handle_error` |
| `generate_chart` | `state.get("error")` is None | `finalize` |

The edge function pattern used throughout:
```python
def _route(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "<next_node>"
```

---

## Memory & Context

| Scope | Mechanism | What is stored |
|---|---|---|
| Within a run | LangGraph `AgentState` (in-memory dict) | All in-progress data: schema, plan, computed_data, answer, chart |
| Across runs | SQLite `analyses` table | Completed analysis records: answer_text, chart_json, status |
| Dataset persistence | SQLite `datasets` table + local filesystem | Dataset metadata and uploaded CSV files |
| Conversation | Not in Phase 1 — deferred to Phase 3 | Multi-turn questions against the same dataset |

> **Assumed:** Conversation history (multi-turn memory per dataset session) is deferred to Phase 3. Phase 1 and Phase 2 are single-turn: one question → one answer per API call. The UI in Phase 1 shows only the latest result; prior results are accessible via `GET /analyses/{id}` but not displayed as a conversation thread.

**Context window management:** Schema summary is capped at 20 columns × 5 sample rows. Computed data passed to `generate_answer` is capped at 4,000 characters via `json.dumps(computed_data)[:4000]`. This keeps both Gemini calls well within the `gemini-2.5-flash` context window.

---

## Error Handling & Recovery

**Node-level:** Every node wraps its body in a try/except. On any exception: log with structlog at ERROR level (including `run_id`), set `state["error"] = str(exc)`, and return the mutated state. The conditional edge after each node checks `state.get("error")` and routes to `handle_error`.

**Graph-level (`handle_error` node):**
- Reads: `state["error"]`, `state.get("run_id")`, `state.get("dataset_id")`, `state.get("question")`
- Writes `AnalysisRow` to DB: `status = "failed"`, `error_message = state["error"]`
- Logs with structlog: `event="analysis.failed"`, `run_id=...`, `error=...`
- Sets `state["status"] = "failed"`
- Graph terminates at END

**Resume / retry strategy:** No resume from checkpoint in Phase 1. A failed run requires the user to submit the question again (new `POST /analyses`). Phase 3 may add LangGraph checkpointing for long-running analyses.

**Partial failure:** `generate_chart` failure (e.g., unsupported chart type) sets `chart_json = None` rather than `state["error"]` — this is a non-critical partial failure. The answer is still returned; only the chart is absent. The UI handles `chart_json == null` gracefully by showing only the text answer.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Node entry/exit | `event="node.start"/"node.end"`, `node_name`, `run_id` | structlog stdout |
| LLM calls | `event="llm.call"`, `model`, `prompt_chars`, `response_chars`, `latency_ms` | structlog stdout |
| Errors | `event="node.error"`, `node_name`, `run_id`, `error` | structlog ERROR |
| Run outcome | `event="analysis.completed"/"analysis.failed"`, `analysis_id`, `duration_ms` | structlog stdout |

---

## Concurrency Model

- **Run isolation:** Each `POST /analyses` invocation gets its own `run_id` and `AgentState`. The graph is invoked synchronously (`agentic_ai.invoke(initial_state)`) inside the FastAPI route handler. FastAPI handles HTTP concurrency; each request runs in its own thread (Uvicorn default worker model). Multiple concurrent analyses are independent.
- **Parallel nodes within a run:** No parallel nodes in Phase 1. All nodes execute sequentially. `generate_answer` and `generate_chart` are candidates for parallelization in Phase 3 (both read `computed_data`, neither writes a shared field).
- **Checkpointing:** None in Phase 1. Added in Phase 3 if multi-turn conversation requires run resumption.

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    ingest_csv,
    plan_analysis,
    execute_analysis,
    generate_answer,
    generate_chart,
    finalize,
    handle_error,
)
from graph.edges import (
    after_ingest,
    after_plan,
    after_execute,
    after_answer,
    after_chart,
)


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("ingest_csv", ingest_csv)
    g.add_node("plan_analysis", plan_analysis)
    g.add_node("execute_analysis", execute_analysis)
    g.add_node("generate_answer", generate_answer)
    g.add_node("generate_chart", generate_chart)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("ingest_csv")

    g.add_conditional_edges(
        "ingest_csv",
        after_ingest,
        {"plan_analysis": "plan_analysis", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "plan_analysis",
        after_plan,
        {"execute_analysis": "execute_analysis", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_analysis",
        after_execute,
        {"generate_answer": "generate_answer", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_answer",
        after_answer,
        {"generate_chart": "generate_chart", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_chart",
        after_chart,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
```
