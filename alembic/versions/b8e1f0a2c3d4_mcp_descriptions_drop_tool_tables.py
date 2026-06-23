"""mcp: move tool descriptions onto data_sources, drop tool/tool_capability tables

Revision ID: b8e1f0a2c3d4
Revises: 57cfed820d74
Create Date: 2026-06-23 15:40:00.000000

The tool layer became MCP: a data source's tools are now served at runtime by its
per-source MCP server, so the `tools` / `tool_capabilities` tables are removed. The
only persisted tool metadata is the LLM-generated descriptions, which move onto
`data_sources` (so the server's tool description survives without re-calling the LLM).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e1f0a2c3d4'
down_revision: Union[str, None] = '57cfed820d74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PARAM_SCHEMA = '{"query": {"type": "string"}}'


def upgrade() -> None:
    # 1. Add the new description columns (nullable — safe with existing rows).
    with op.batch_alter_table('data_sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tool_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('capability_description', sa.Text(), nullable=True))

    # 2. Back-fill from the legacy tool / tool_capability rows before dropping them.
    op.execute(
        """
        UPDATE data_sources
        SET tool_description = (
            SELECT t.description FROM tools t
            WHERE t.data_source_id = data_sources.id
            ORDER BY t.created_at LIMIT 1
        )
        WHERE tool_description IS NULL
        """
    )
    op.execute(
        """
        UPDATE data_sources
        SET capability_description = (
            SELECT tc.description FROM tool_capabilities tc
            JOIN tools t ON tc.tool_id = t.id
            WHERE t.data_source_id = data_sources.id
            ORDER BY tc.created_at LIMIT 1
        )
        WHERE capability_description IS NULL
        """
    )

    # 3. Drop the legacy tables (no real FK constraints; child first regardless).
    op.drop_table('tool_capabilities')
    op.drop_table('tools')


def downgrade() -> None:
    # 1. Recreate the legacy tables.
    op.create_table(
        'tools',
        sa.Column('id', sa.Text(), primary_key=True, nullable=False),
        sa.Column('data_source_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_table(
        'tool_capabilities',
        sa.Column('id', sa.Text(), primary_key=True, nullable=False),
        sa.Column('tool_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('parameter_schema_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )

    # 2. Restore one tool + one run_query capability per data source from the columns.
    op.execute(
        """
        INSERT INTO tools (id, data_source_id, name, type, description, config_json, created_at)
        SELECT lower(hex(randomblob(16))), id, 'csv_query', 'csv_query',
               COALESCE(tool_description, ''), NULL, CURRENT_TIMESTAMP
        FROM data_sources
        """
    )
    op.execute(
        f"""
        INSERT INTO tool_capabilities (id, tool_id, name, description, parameter_schema_json, created_at)
        SELECT lower(hex(randomblob(16))), t.id, 'run_query',
               COALESCE(ds.capability_description, ''), '{_DEFAULT_PARAM_SCHEMA}', CURRENT_TIMESTAMP
        FROM tools t JOIN data_sources ds ON t.data_source_id = ds.id
        """
    )

    # 3. Drop the description columns.
    with op.batch_alter_table('data_sources', schema=None) as batch_op:
        batch_op.drop_column('capability_description')
        batch_op.drop_column('tool_description')
