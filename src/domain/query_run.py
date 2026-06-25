from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class QueryRun(BaseModel):
    """Public read shape of a `QueryRunRow` (one question -> one answer)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str | None = None
    session_id: str | None = None
    question: str
    answer: str | None = None
    status: str
    error_message: str | None = None
    action_history: list[Any] | None = None
    iteration_count: int
    tokens_input: int
    tokens_output: int
    prompt_breakdown: dict[str, Any] | None = None
    dataset_ids_json: list[str] | None = None
    selector_reasoning: str | None = None
    created_at: datetime
    updated_at: datetime
