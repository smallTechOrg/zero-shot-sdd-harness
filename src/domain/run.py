from typing import Any

from pydantic import BaseModel


class RunRequest(BaseModel):
    dataset_id: str
    question: str
    session_id: str | None = None
    run_id: str | None = None  # client-supplied id for live-progress correlation


class KeyNumber(BaseModel):
    label: str
    value: str


class RunOut(BaseModel):
    run_id: str
    dataset_id: str
    status: str
    answer_text: str | None = None
    narrative: str | None = None
    key_numbers: list[KeyNumber] = []
    chart: dict[str, Any] = {}
    table: list[dict[str, Any]] = []
    code: str = ""
    attempts: int = 0
    error: str | None = None
    session_id: str | None = None
    tokens_used: int | None = None
    cost_estimate_usd: float | None = None
    created_at: str | None = None  # ISO-8601 string


class RunSummary(BaseModel):
    run_id: str
    question: str
    status: str
    created_at: str | None = None  # ISO-8601 string
    tokens_used: int | None = None
    cost_estimate_usd: float | None = None
