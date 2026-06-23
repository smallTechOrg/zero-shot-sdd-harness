import json

from sqlalchemy import select

from graph.agent import agentic_ai, analyst_graph
from graph.state import AgentState
from db.session import create_db_session, init_db
from db.models import RunRow, DatasetRow, QaTurnRow

from data.schema_summary import schema_summary, sample_rows
from data.audit import log_operation

_HISTORY_LIMIT = 3


def run_agent(input_text: str) -> str:
    init_db()

    with create_db_session() as session:
        run = RunRow(input_text=input_text)
        session.add(run)
        session.flush()
        run_id = run.id

    initial: AgentState = {"run_id": run_id, "input_text": input_text, "error": None}
    final = agentic_ai.invoke(initial)

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        run.status = final.get("status", "completed")
        run.output_text = final.get("output_text")
        run.error_message = final.get("error")

    return run_id


def _load_latest_table_name(session_id: str) -> str | None:
    with create_db_session() as session:
        ds = session.scalars(
            select(DatasetRow)
            .where(DatasetRow.session_id == session_id)
            .order_by(DatasetRow.created_at.desc())
        ).first()
        return ds.table_name if ds is not None else None


def _load_history(session_id: str) -> list[dict]:
    with create_db_session() as session:
        rows = session.scalars(
            select(QaTurnRow)
            .where(QaTurnRow.session_id == session_id)
            .where(QaTurnRow.status == "completed")
            .order_by(QaTurnRow.created_at.desc())
            .limit(_HISTORY_LIMIT)
        ).all()
    # Oldest first for natural reading order.
    return [
        {"question": r.question, "sql_text": r.sql_text, "answer_text": r.answer_text}
        for r in reversed(rows)
    ]


def run_analyst(session_id: str, question: str) -> dict:
    """Run the analyst graph for one question against the session's dataset.

    Returns {turn_id, status, answer_text, sql_text, result, error}.
    Raises ValueError if the session has no dataset (callers map to 404).
    """
    table_name = _load_latest_table_name(session_id)
    if table_name is None:
        raise ValueError("Session has no dataset.")

    schema = schema_summary(table_name)
    sample = sample_rows(table_name, n=5)
    history = _load_history(session_id)

    initial: AgentState = {
        "session_id": session_id,
        "table_name": table_name,
        "question": question,
        "schema": schema,
        "sample": sample,
        "history": history,
        "error": None,
    }
    final = analyst_graph.invoke(initial)

    status = final.get("status", "failed")
    answer_text = final.get("answer_text")
    sql_text = final.get("sql_text")
    result = final.get("result")
    error = final.get("error")

    with create_db_session() as session:
        turn = QaTurnRow(
            session_id=session_id,
            question=question,
            answer_text=answer_text,
            sql_text=sql_text,
            result_json=json.dumps(result) if result is not None else None,
            status=status,
            error_message=error,
        )
        session.add(turn)
        session.flush()
        turn_id = turn.id

    rows = (result or {}).get("rows", []) if result else []
    log_operation(
        session_id=session_id,
        operation="ask",
        question=question,
        sql_text=sql_text,
        rows_returned=len(rows),
        success=status == "completed",
        error_message=error,
    )

    return {
        "turn_id": turn_id,
        "status": status,
        "answer_text": answer_text,
        "sql_text": sql_text,
        "result": result,
        "error": error,
    }
