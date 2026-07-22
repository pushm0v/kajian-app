"""Mirrors lib/models/kajian_note.dart. keyPoints/topics/actionItems are
stored as Postgres text[] columns rather than a separate table each — they're
simple string lists with no independent identity or query needs of their own.
scripture_references gets its own table since each reference has structure
(type + citation + note) worth being able to filter/join on later (e.g. an
admin view listing all kajian that reference a specific ayah).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class KajianNote(Base):
    __tablename__ = "kajian_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("kajian_sessions.id", ondelete="CASCADE"), unique=True, index=True
    )

    summary: Mapped[str] = mapped_column(String, default="")
    key_points: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    action_items: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    session: Mapped["KajianSession"] = relationship(back_populates="note")  # noqa: F821
    references: Mapped[list["ScriptureReference"]] = relationship(
        back_populates="note_rel", cascade="all, delete-orphan"
    )


class ScriptureReference(Base):
    __tablename__ = "scripture_references"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kajian_notes.id", ondelete="CASCADE"), index=True
    )

    # "quran" or "hadith" — kept as a plain string (not a DB enum) since this
    # is client-supplied free-form data from an LLM response, not a fixed
    # set the schema needs to enforce.
    type: Mapped[str] = mapped_column(String)
    citation: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    note_rel: Mapped["KajianNote"] = relationship(back_populates="references")
