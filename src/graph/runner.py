"""
Analyst runner — thin wrapper around the analyst_graph.

run_analyst_query() is the primary entry point used by the API layer.
"""
from graph.agent import analyst_graph
from graph.state import AnalystState


def run_analyst_query(
    session_id: str,
    dataset_table: str,
    question: str,
) -> AnalystState:
    """
    Run the analyst graph synchronously for a single question.

    Returns the final AnalystState dict.
    """
    initial: AnalystState = {
        "session_id": session_id,
        "dataset_table": dataset_table,
        "question": question,
        "error": None,
    }
    result: AnalystState = analyst_graph.invoke(initial)
    return result
