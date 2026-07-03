"""Pydantic schemas for conversation sessions (Phase 2)."""
from __future__ import annotations

from pydantic import BaseModel

from domain.run import RunSummary


class SessionCreate(BaseModel):
    dataset_id: str


class SessionOut(BaseModel):
    id: str
    dataset_id: str
    created_at: str | None = None  # ISO-8601 string
    runs: list[RunSummary] = []
