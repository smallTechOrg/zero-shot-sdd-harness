"""add_iteration_count_to_query_records

Revision ID: f3c81a2d9e04
Revises: daa92380e008
Create Date: 2026-06-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f3c81a2d9e04'
down_revision = 'daa92380e008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('query_records', sa.Column('iteration_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('query_records', 'iteration_count')
