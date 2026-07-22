"""Mirrors lib/models/transcript_segment.dart."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("kajian_sessions.id", ondelete="CASCADE"), index=True
    )

    text: Mapped[str] = mapped_column(String)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)

    session: Mapped["KajianSession"] = relationship(back_populates="transcript")  # noqa: F821
