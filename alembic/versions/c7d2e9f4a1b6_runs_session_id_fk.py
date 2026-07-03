"""runs.session_id foreign key

Adds the missing ``runs.session_id`` -> ``sessions.id`` foreign key
(nullable) so the ORM model matches spec/data.md. The ``runs`` table was
created before ``sessions`` existed (phase-1 migration), so the constraint
could only be added once ``sessions`` was present (this revision runs after
the phase-2 sessions revision). SQLite cannot ALTER an existing table to add
a constraint, so this uses Alembic's batch mode to recreate the table with
the foreign key in place.

Revision ID: c7d2e9f4a1b6
Revises: b3f1a7c9d2e4
Create Date: 2026-07-03 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7d2e9f4a1b6"
down_revision: Union[str, None] = "b3f1a7c9d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "fk_runs_session_id_sessions"


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.create_foreign_key(
            _FK_NAME, "sessions", ["session_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
