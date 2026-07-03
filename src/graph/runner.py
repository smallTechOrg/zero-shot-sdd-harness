"""Synchronous run entry point for the data-analysis agent.

``run_analysis`` creates the ``running`` RunRow, invokes the compiled graph, and
returns the run_id. The graph's ``finalize``/``handle_error`` nodes persist the
final state — the caller re-loads the RunRow to build the API response.
"""
from graph.agent import agentic_ai
from graph.state import AgentState
from db.session import create_db_session, init_db
from db.models import RunRow


def run_analysis(dataset_id: str, question: str) -> str:
    """Run one analysis synchronously; returns the run_id."""
    init_db()

    with create_db_session() as session:
        run = RunRow(dataset_id=dataset_id, question=question, status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    initial: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "question": question,
        "error": None,
    }
    agentic_ai.invoke(initial)

    return run_id
