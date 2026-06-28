from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Text, TIMESTAMP, Integer, Float, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    """The file library (Phase 1; management UI in Phase 4)."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False, default="csv")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sample_rows_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class Question(Base):
    """One asked question + its answer (Phase 1)."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    dataset_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    plan_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_numbers_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    result_table_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chart_spec_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    followups_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cost_guard_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class AnalysisStep(Base):
    """Per-step audit trail (code + bounded result) (Phase 1)."""

    __tablename__ = "analysis_steps"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    language: Mapped[str] = mapped_column(Text, nullable=False, default="sql")
    code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class CostRecord(Base):
    """Per-question cost (Phase 1; daily total in Phase 4)."""

    __tablename__ = "cost_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, index=True
    )
