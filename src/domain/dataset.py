"""Pydantic request/response models for the datasets API surface (spec/api.md)."""
from typing import Any

from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    type: str


class DatasetResponse(BaseModel):
    """Shape returned by POST /datasets and GET /datasets/{id}."""

    id: str
    name: str
    row_count: int
    columns: list[ColumnSchema]
    profile: dict[str, Any]
    status: str


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    """Shape returned by POST /datasets/{id}/ask (completed or failed)."""

    run_id: str
    status: str
    answer: str | None = None
    key_numbers: list[dict[str, Any]] = []
    chart: dict[str, Any] | None = None
    table: dict[str, Any] | None = None
    plan: str | None = None
    sql: str | None = None
    trace: list[dict[str, Any]] = []
    cost_usd: float = 0.0
    error_message: str | None = None
