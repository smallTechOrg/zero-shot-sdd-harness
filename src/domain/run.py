from __future__ import annotations

from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: str
    columns: list[dict]
    row_count: int


class QuestionRequest(BaseModel):
    question: str


class AnalysisResponse(BaseModel):
    run_id: str
    answer: str | None = None
    chart_base64: str | None = None
    chart_type: str | None = None
    executed_code: str | None = None
    node_trace: list[dict] | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
