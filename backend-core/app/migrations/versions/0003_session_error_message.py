"""kajian_sessions.error_message: set when a background transcribe/
summarize job fails, so the client polling GET /sessions/{id} can show
what went wrong.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kajian_sessions",
        sa.Column("error_message", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kajian_sessions", "error_message")
