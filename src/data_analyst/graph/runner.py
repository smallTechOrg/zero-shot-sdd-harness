from typing import Any

from data_analyst.graph.agent import compiled_graph
from data_analyst.graph.nodes import list_dataset_contexts
from data_analyst.graph.state import AgentState


def run_question(session_id: int, question: str) -> dict[str, Any]:
    """Run one NL question through the agent graph. Returns the answer payload."""
    initial: AgentState = {
        "session_id": session_id,
        "question": question,
        "dataset_contexts": list_dataset_contexts(session_id),
        "retried": False,
        "error": None,
    }
    final = compiled_graph.invoke(initial)
    return {
        "answer_text": final.get("answer_text"),
        "generated_sql": final.get("generated_sql"),
        "result_columns": final.get("result_columns") or [],
        "result_rows": final.get("result_rows") or [],
        "row_count": final.get("row_count"),
        "duration_ms": final.get("duration_ms"),
        "audit_entry_id": final.get("audit_entry_id"),
        "status": final.get("status", "completed"),
        "error": final.get("error"),
    }
