from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Integer, Text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DatasetRow(Base):
    """A profiled CSV the user uploaded and can query.

    The raw data lives in a local DuckDB file (``duckdb_path``); only the
    schema/profile JSON summaries are stored here in SQLite.
    """

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    duckdb_path: Mapped[str] = mapped_column(Text, nullable=False)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON strings (Text): column schema and the profile/health summary.
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    profile_json: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ready")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    question_runs: Mapped[list["QuestionRunRow"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class QuestionRunRow(Base):
    """One natural-language question answered over a dataset — the audit record."""

    __tablename__ = "question_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(
        Text, ForeignKey("datasets.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON strings (Text): step trace, bounded result table, chart spec, key numbers.
    trace_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_numbers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    dataset: Mapped["DatasetRow"] = relationship(back_populates="question_runs")
