import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data_analyst.api._common import api_error, ok
from data_analyst.audit.logger import AuditLogger
from data_analyst.config.settings import get_settings
from data_analyst.db.models import SessionRow, MessageRow, DatasetRow
from data_analyst.db.session import get_session
from data_analyst.domain.query import QueryRequest, QueryResponse
from data_analyst.duckdb_engine import engine as duckdb_engine
from data_analyst.llm.client import get_gemini_client
from data_analyst.llm.sql_extractor import extract_sql
from data_analyst.llm.token_budget import build_prompt, check_budget

router = APIRouter()
_MAX_RESULT_ROWS = 500


def _serialize_results(rows: list[dict]) -> list[dict]:
    """Convert DuckDB result rows to JSON-safe dicts (datetime, Decimal → str)."""
    safe_rows = []
    for row in rows:
        safe_row = {}
        for k, v in row.items():
            if v is None or isinstance(v, (str, int, float, bool)):
                safe_row[k] = v
            else:
                safe_row[k] = str(v)
        safe_rows.append(safe_row)
    return safe_rows


@router.post("/sessions/{session_id}/query")
def query_session(
    session_id: str,
    body: QueryRequest,
    db: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    audit = AuditLogger(settings.resolved_data_dir)

    # Validate session
    session_row = db.get(SessionRow, session_id)
    if session_row is None:
        raise api_error("session_not_found", f"Session {session_id} not found", 404)

    # Validate datasets exist
    datasets = db.query(DatasetRow).filter_by(session_id=session_id).all()
    if not datasets:
        raise api_error("no_datasets", "No datasets uploaded for this session", 400)

    # Re-register datasets in DuckDB (handles process restarts)
    duckdb_engine.reregister_session_datasets(datasets)

    # Fetch schemas
    schemas = []
    for ds in datasets:
        try:
            cols = duckdb_engine.get_table_schema(ds.table_name)
            schemas.append({"table_name": ds.table_name, "columns": cols})
        except Exception:
            pass

    # Fetch last 10 turns of history
    history_rows = (
        db.query(MessageRow)
        .filter_by(session_id=session_id)
        .order_by(MessageRow.created_at.desc())
        .limit(10)
        .all()
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_rows)
    ]

    # Build prompt and check budget
    prompt = build_prompt(schemas=schemas, history=history, question=body.question)
    within_budget, estimated_tokens = check_budget(prompt, settings.token_budget_hard_cap)

    if not within_budget:
        audit.log(
            event_type="query_rejected",
            session_id=session_id,
            payload={
                "reason": "token_budget_exceeded",
                "estimated_tokens": estimated_tokens,
                "hard_cap": settings.token_budget_hard_cap,
                "question": body.question,
            },
        )
        raise api_error(
            "token_budget_exceeded",
            f"Estimated prompt tokens ({estimated_tokens}) exceeds hard cap ({settings.token_budget_hard_cap})",
            422,
        )

    # Generate SQL
    client = get_gemini_client()
    try:
        raw_sql, token_usage = client.generate_sql(prompt)
    except Exception as exc:
        raise api_error("llm_error", f"LLM call failed: {exc}", 503)

    # Extract and validate SQL
    try:
        sql = extract_sql(raw_sql)
    except ValueError as exc:
        raise api_error("invalid_sql", str(exc), 422)

    # Execute SQL
    try:
        results = duckdb_engine.execute_query(sql)
    except Exception as exc:
        raise api_error("sql_exec_error", f"SQL execution failed: {exc}", 422)

    truncated = len(results) > _MAX_RESULT_ROWS
    results = results[:_MAX_RESULT_ROWS]
    results = _serialize_results(results)

    # Generate prose answer
    try:
        answer = client.generate_answer(body.question, sql, results)
    except Exception:
        answer = f"Query executed successfully. Returned {len(results)} row(s)."

    # Persist messages
    user_msg = MessageRow(
        session_id=session_id,
        role="user",
        content=body.question,
    )
    db.add(user_msg)
    db.flush()

    asst_msg = MessageRow(
        session_id=session_id,
        role="assistant",
        content=answer,
        sql=sql,
        results_preview=json.dumps(results[:10], default=str),
        token_usage=json.dumps(token_usage),
    )
    db.add(asst_msg)
    db.flush()

    # Audit log
    audit.log(
        event_type="llm_call",
        session_id=session_id,
        payload={"question": body.question, "estimated_prompt_tokens": estimated_tokens},
        token_usage=token_usage,
    )
    audit.log(
        event_type="sql_exec",
        session_id=session_id,
        payload={"sql": sql, "row_count": len(results), "truncated": truncated},
    )

    return ok(QueryResponse(
        message_id=asst_msg.id,
        session_id=session_id,
        question=body.question,
        sql=sql,
        results=results,
        answer=answer,
        token_usage=token_usage,
        row_count=len(results),
        truncated=truncated,
    ).model_dump())
