from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok, api_error
from api.datasets import upsert_session
from db.session import get_session

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    dataset_table: str


@router.post("/query")
def run_query(
    body: QueryRequest,
    x_session_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    if not x_session_id:
        raise api_error("MISSING_SESSION", "X-Session-ID header is required", 400)

    # Validate that the dataset_table belongs to this session
    expected_prefix = x_session_id.replace("-", "_") + "_"
    if not body.dataset_table.startswith(expected_prefix):
        raise api_error(
            "FORBIDDEN",
            f"Table '{body.dataset_table}' does not belong to session '{x_session_id}'",
            403,
        )

    # Upsert session within the open ORM session
    upsert_session(x_session_id, session)

    # Commit + release the ORM session BEFORE running the graph.
    # The graph's audit_logger node opens its own session; if we hold the
    # FastAPI session open, SQLite will report "database is locked".
    session.commit()

    # Run analyst graph (synchronous — graph uses create_db_session internally)
    from graph.runner import run_analyst_query
    state = run_analyst_query(
        session_id=x_session_id,
        dataset_table=body.dataset_table,
        question=body.question,
    )

    if state.get("error"):
        raise api_error("QUERY_FAILED", state["error"], 502)

    return ok({
        "answer": state.get("answer", ""),
        "table": state.get("table") or [],
        "sql": state.get("sql", ""),
        "audit_id": state.get("audit_id", ""),
    })
