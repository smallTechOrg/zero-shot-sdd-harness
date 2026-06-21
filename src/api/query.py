from fastapi import APIRouter
from pydantic import BaseModel

from src.agent.graph import analyst_graph
from src.db.connection import get_db

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    session_id: str = "default"


@router.post("/")
async def query(req: QueryRequest):
    conn = get_db()
    rows = conn.execute("SELECT name FROM datasets").fetchall()
    conn.close()
    datasets = [r[0] for r in rows]

    result = analyst_graph.invoke(
        {
            "question": req.question,
            "session_id": req.session_id,
            "datasets": datasets,
            "plan": "",
            "sql": "",
            "intent": "table",
            "raw_rows": [],
            "columns": [],
            "response": {},
        }
    )
    return result["response"]
