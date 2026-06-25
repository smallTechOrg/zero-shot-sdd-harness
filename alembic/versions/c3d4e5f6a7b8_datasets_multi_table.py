"""datasets: multi-table dataset model — DatasetTableRow child + uri/last_synced_at/connection_error

Revision ID: c3d4e5f6a7b8
Revises: b8e1f0a2c3d4
Create Date: 2026-06-25 21:00:00.000000

A "tool" becomes a named multi-table DATASET. `data_sources` is reused as the Dataset row
(+ uri/last_synced_at/connection_error; per-source columns deprecated but kept nullable). Each
table moves to a new `dataset_tables` child. Existing single-CSV datasets are back-filled to ONE
child whose parquet_path is preserved at its existing location (no file moves).
"""
from typing import Sequence, Union
from urllib.parse import quote
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

from data_analysis_agent.tools.table_naming import sql_table_name

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b8e1f0a2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New dataset-level columns (nullable — safe with existing rows).
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("uri", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("connection_error", sa.Text(), nullable=True))

    # 2. New child: one row per table within a dataset.
    op.create_table(
        "dataset_tables",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("parquet_path", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_names_json", sa.Text(), nullable=True),
        sa.Column("schema_json", sa.Text(), nullable=True),
        sa.Column("capability_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_id", "table_name", name="uq_dataset_table"),
    )
    op.create_index("ix_dataset_tables_dataset_id", "dataset_tables", ["dataset_id"])

    # 3. Back-fill: one child per legacy dataset row, preserving its parquet_path (no file moves).
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, name, parquet_path, row_count, column_names_json, schema_json, "
        "capability_description, created_at FROM data_sources"
    )).mappings().all()
    for r in rows:
        bind.execute(
            sa.text(
                "INSERT INTO dataset_tables (id, dataset_id, table_name, source_filename, "
                "parquet_path, row_count, column_names_json, schema_json, capability_description, created_at) "
                "VALUES (:id, :dataset_id, :table_name, :source_filename, :parquet_path, :row_count, "
                ":column_names_json, :schema_json, :capability_description, :created_at)"
            ),
            {
                "id": str(uuid4()),
                "dataset_id": r["id"],
                "table_name": sql_table_name(r["name"] or "data"),
                "source_filename": r["name"],
                "parquet_path": r["parquet_path"],
                "row_count": r["row_count"],
                "column_names_json": r["column_names_json"],
                "schema_json": r["schema_json"],
                "capability_description": r["capability_description"],
                "created_at": r["created_at"],
            },
        )
        bind.execute(
            sa.text("UPDATE data_sources SET uri = :uri WHERE id = :id AND (uri IS NULL OR uri = '')"),
            {"uri": "parquet:///" + quote(r["name"] or "", safe=""), "id": r["id"]},
        )
    bind.execute(sa.text("UPDATE data_sources SET type = 'parquet' WHERE type = 'csv'"))


def downgrade() -> None:
    op.drop_index("ix_dataset_tables_dataset_id", table_name="dataset_tables")
    op.drop_table("dataset_tables")
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        batch_op.drop_column("connection_error")
        batch_op.drop_column("last_synced_at")
        batch_op.drop_column("uri")
    op.get_bind().execute(sa.text("UPDATE data_sources SET type = 'csv' WHERE type = 'parquet'"))
