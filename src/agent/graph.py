import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.db.connection import get_db


class AnalystState(TypedDict):
    question: str
    session_id: str
    datasets: list[str]
    plan: str
    sql: str
    intent: str          # "table" | "chart"
    raw_rows: list
    columns: list[str]
    response: dict


def plan_node(state: AnalystState) -> dict:
    """LLM plans what to do — returns intent + SQL."""
    from src.integrations.llm import get_llm_client

    llm = get_llm_client()
    datasets_info = ", ".join(state["datasets"]) if state["datasets"] else "none"
    prompt = (
        f"Datasets available: {datasets_info}\n"
        f"User question: {state['question']}\n"
        "Return JSON with keys: intent (table|chart), sql, "
        "and for chart: x_col, y_col."
    )
    raw = llm.complete(prompt, system="You are a senior data analyst.")
    parsed = json.loads(raw)
    return {
        "intent": parsed.get("intent", "table"),
        "sql": parsed.get("sql", ""),
        "plan": raw,
    }


def query_data_node(state: AnalystState) -> dict:
    """Execute the SQL against DuckDB and return raw rows."""
    conn = get_db()
    try:
        df = conn.execute(state["sql"]).fetchdf()
        return {
            "raw_rows": df.values.tolist(),
            "columns": list(df.columns),
        }
    finally:
        conn.close()


def respond_node(state: AnalystState) -> dict:
    """Format the response based on intent."""
    if state["intent"] == "chart":
        response = {
            "type": "chart",
            "plotly_spec": {
                "data": [
                    {
                        "type": "bar",
                        "x": [r[0] for r in state["raw_rows"]],
                        "y": [r[1] for r in state["raw_rows"]],
                    }
                ],
                "layout": {"title": state["question"]},
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
