"""initial: sessions, datasets, audit_log

Revision ID: 001
Revises:
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_table(
        'datasets',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('session_id', sa.Text(), nullable=False),
        sa.Column('table_name', sa.Text(), nullable=False, unique=True),
        sa.Column('original_filename', sa.Text(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_names', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('session_id', sa.Text(), nullable=False),
        sa.Column('dataset_table', sa.Text(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('sql_generated', sa.Text(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('datasets')
    op.drop_table('sessions')
