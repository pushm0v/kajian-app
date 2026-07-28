"""Speaker voice-fingerprint library: speakers table (name + embedding
centroid), plus kajian_sessions.speaker_id (linking a session to a
confirmed profile) and kajian_sessions.pending_embedding (holding a
freshly-extracted, not-yet-confirmed embedding between /transcribe and
/speaker-confirm).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "speakers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("embedding", pg.ARRAY(sa.Float()), nullable=False),
        sa.Column("embedding_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_speakers_name", "speakers", ["name"])

    op.add_column(
        "kajian_sessions",
        sa.Column(
            "speaker_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("speakers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_kajian_sessions_speaker_id", "kajian_sessions", ["speaker_id"]
    )
    op.add_column(
        "kajian_sessions",
        sa.Column("pending_embedding", pg.ARRAY(sa.Float()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kajian_sessions", "pending_embedding")
    op.drop_index("ix_kajian_sessions_speaker_id", table_name="kajian_sessions")
    op.drop_column("kajian_sessions", "speaker_id")
    op.drop_index("ix_speakers_name", table_name="speakers")
    op.drop_table("speakers")
