"""Initial schema: users, kajian_sessions, transcript_segments,
kajian_notes, scripture_references.

Revision ID: 0001
Revises:
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("firebase_uid", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint("uq_users_firebase_uid", "users", ["firebase_uid"])
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"])

    # create_type=False: the enum type is created explicitly below (once),
    # rather than letting create_table's own dialect logic also try to
    # create it — doing both raises DuplicateObject.
    session_status = pg.ENUM(
        "recording",
        "recorded",
        "transcribing",
        "transcribed",
        "summarizing",
        "completed",
        "error",
        name="session_status",
        create_type=False,
    )
    session_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "kajian_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_object_key", sa.String(), nullable=True),
        sa.Column(
            "locale_id", sa.String(), nullable=False, server_default="id_ID"
        ),
        sa.Column(
            "status",
            session_status,
            nullable=False,
            server_default="recorded",
        ),
    )
    op.create_index(
        "ix_kajian_sessions_user_id", "kajian_sessions", ["user_id"]
    )

    op.create_table(
        "transcript_segments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("kajian_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_transcript_segments_session_id", "transcript_segments", ["session_id"]
    )

    op.create_table(
        "kajian_notes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("kajian_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "key_points",
            pg.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "topics", pg.ARRAY(sa.String()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "action_items",
            pg.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_kajian_notes_session_id", "kajian_notes", ["session_id"]
    )
    op.create_index("ix_kajian_notes_session_id", "kajian_notes", ["session_id"])

    op.create_table(
        "scripture_references",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "note_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("kajian_notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("citation", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_scripture_references_note_id", "scripture_references", ["note_id"]
    )


def downgrade() -> None:
    op.drop_table("scripture_references")
    op.drop_table("kajian_notes")
    op.drop_table("transcript_segments")
    op.drop_table("kajian_sessions")
    op.execute("DROP TYPE session_status")
    op.drop_table("users")
