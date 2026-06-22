from typing import Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class QueryResponse(BaseModel):
    message_id: str
    session_id: str
    question: str
    sql: str
    results: list[dict[str, Any]]
    answer: str
    token_usage: dict
    row_count: int
    truncated: bool = False
