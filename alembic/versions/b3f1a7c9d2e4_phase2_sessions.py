"""phase2 sessions

Adds the ``sessions`` table (one session per dataset; conversation memory is
threaded from the session's completed runs). The ``runs`` table already carries
``session_id``/``tokens_used``/``cost_estimate_usd`` from the phase-1 migration,
so this revision only creates ``sessions``.

Revision ID: b3f1a7c9d2e4
Revises: 60300fe53bab
Create Date: 2026-07-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3f1a7c9d2e4"
down_revision: Union[str, None] = "60300fe53bab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sessions")
