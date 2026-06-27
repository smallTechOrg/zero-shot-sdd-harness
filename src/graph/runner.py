from graph.agent import agentic_ai
from graph.legacy_agent import legacy_agentic_ai
from graph.state import DataAnalysisState, AgentState
from db.session import create_db_session, init_db
from db.models import RunRow


def run_analysis(upload_id: str, analysis_type: str, params: dict, analysis_id: str) -> dict:
    """Run the data-analysis graph synchronously and return the final state summary."""
    initial: DataAnalysisState = {
        "run_id": analysis_id,
        "upload_id": upload_id,
        "analysis_type": analysis_type,
        "params": params,
        "question": params.get("question"),
        "error": None,
    }
    final = agentic_ai.invoke(initial)
    return {
        "status": final.get("status", "completed"),
        "summary": final.get("summary"),
        "chart_json": final.get("chart_json"),
        "table": final.get("table"),
        "error": final.get("error"),
    }


def run_agent(input_text: str) -> str:
    """Legacy /runs endpoint — runs the original transform-text agent."""
    init_db()

    with create_db_session() as session:
        run = RunRow(input_text=input_text)
        session.add(run)
        session.flush()
        run_id = run.id

    initial: AgentState = {"run_id": run_id, "input_text": input_text, "error": None}
    final = legacy_agentic_ai.invoke(initial)

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        run.status = final.get("status", "completed")
        run.output_text = final.get("output_text")
        run.error_message = final.get("error")

    return run_id
