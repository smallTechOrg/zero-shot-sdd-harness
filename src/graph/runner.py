"""Runs the query pipeline for one NL question and persists the assistant message."""
import json

from graph.agent import agentic_ai
from graph.state import AgentState
from db.session import create_db_session
from db.models import RunRow, Message


def run_query(*, session_id: str, dataset_id: str, question: str) -> dict:
    """Invoke the agent graph for one question.

    Returns a dict: {message_id, answer, sql, result: {columns, rows}, row_count,
    status, error}. On failure status="failed" and error is set (message not persisted).
    """
    with create_db_session() as session:
        run = RunRow(input_text=question, status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "dataset_id": dataset_id,
        "question": question,
        "error": None,
    }
    final = agentic_ai.invoke(initial)

    status = final.get("status", "completed")
    error = final.get("error")
    answer = final.get("answer")
    sql = final.get("sql")
    columns = final.get("columns", [])
    rows = final.get("rows", [])
    row_count = final.get("row_count", len(rows))
    result = {"columns": columns, "rows": rows}

    message_id = None
    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        run.status = status
        run.output_text = answer
        run.error_message = error

        if not error:
            msg = Message(
                session_id=session_id,
                role="assistant",
                content=answer or "",
                sql=sql,
                result_json=json.dumps(result, default=str),
                dataset_id=dataset_id,
            )
            session.add(msg)
            session.flush()
            message_id = msg.id

    return {
        "message_id": message_id,
        "answer": answer,
        "sql": sql,
        "result": result,
        "row_count": row_count,
        "status": status,
        "error": error,
    }
