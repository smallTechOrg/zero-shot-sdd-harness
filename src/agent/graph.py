import json as _json
import time
import uuid as _uuid
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.db.connection import get_db


class AnalystState(TypedDict):
    question: str
    session_id: str
    datasets: list[str]
    history: list[dict]   # [{"role": "user"|"assistant", "content": str}]
    plan: str
    sql: str
    intent: str          # "table" | "chart"
    x_col: str
    y_col: str
    raw_rows: list
    columns: list[str]
    response: dict


def plan_node(state: AnalystState) -> dict:
    """LLM plans what to do — returns intent + SQL."""
    from src.integrations.llm import get_llm_client

    llm = get_llm_client()

    history_text = ""
    for msg in state.get("history", [])[-6:]:  # last 3 turns
        history_text += f"{msg['role'].upper()}: {msg['content']}\n"

    datasets_info = ", ".join(state["datasets"]) if state["datasets"] else "none"
    prompt = (
        f"{history_text}"
        f"Datasets available: {datasets_info}\n"
        f"User question: {state['question']}\n"
        "Return JSON with keys: intent (table|chart), sql, "
        "and for chart: x_col, y_col."
    )
    raw = llm.complete(prompt, system="You are a senior data analyst.")
    parsed = _json.loads(raw)
    return {
        "intent": parsed.get("intent", "table"),
        "sql": parsed.get("sql", ""),
        "plan": raw,
        "x_col": parsed.get("x_col", ""),
        "y_col": parsed.get("y_col", ""),
    }


def query_data_node(state: AnalystState) -> dict:
    """Execute the SQL against DuckDB and return raw rows."""
    conn = get_db()
    start = time.monotonic()
    try:
        df = conn.execute(state["sql"]).fetchdf()
        duration_ms = int((time.monotonic() - start) * 1000)
        rows_affected = len(df)

        # Write audit log
        conn.execute(
            """INSERT INTO audit_log (id, session_id, query_text, rows_affected, duration_ms)
               VALUES (?, ?, ?, ?, ?)""",
            [str(_uuid.uuid4()), state["session_id"], state["sql"], rows_affected, duration_ms],
        )

        # Convert to native Python types (JSON round-trip)
        records = _json.loads(df.to_json(orient="split"))
        return {
            "raw_rows": records["data"],
            "columns": records["columns"],
        }
    finally:
        conn.close()


def respond_node(state: AnalystState) -> dict:
    """Format the response based on intent."""
    if state["intent"] == "chart":
        cols = state["columns"]
        x_col = state.get("x_col") or (cols[0] if cols else "x")
        y_col = state.get("y_col") or (cols[1] if len(cols) > 1 else "y")

        x_idx = cols.index(x_col) if x_col in cols else 0
        y_idx = cols.index(y_col) if y_col in cols else (1 if len(cols) > 1 else 0)

        response = {
            "type": "chart",
            "plotly_spec": {
                "data": [
                    {
                        "type": "bar",
                        "x": [r[x_idx] for r in state["raw_rows"]],
                        "y": [r[y_idx] for r in state["raw_rows"]],
                        "name": y_col,
                    }
                ],
                "layout": {
                    "title": state["question"],
                    "xaxis": {"title": x_col},
                    "yaxis": {"title": y_col},
                },
            },
        }
    else:
        cols = state["columns"]
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        rows = [
            "| " + " | ".join(str(v) for v in row) + " |"
            for row in state["raw_rows"]
        ]
        table = "\n".join([header, sep] + rows)
        response = {"type": "table", "markdown": table}
    return {"response": response}


def build_graph():
    g = StateGraph(AnalystState)
    g.add_node("plan", plan_node)
    g.add_node("query_data", query_data_node)
    g.add_node("respond", respond_node)
    g.set_entry_point("plan")
    g.add_edge("plan", "query_data")
    g.add_edge("query_data", "respond")
    g.add_edge("respond", END)
    return g.compile()


analyst_graph = build_graph()
