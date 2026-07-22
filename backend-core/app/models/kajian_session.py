"""Mirrors the Flutter app's lib/models/kajian_session.dart exactly, so the
API layer can serialize/deserialize without a translation step.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class SessionStatus(str, enum.Enum):
    recording = "recording"
    recorded = "recorded"
    transcribing = "transcribing"
    transcribed = "transcribed"
    summarizing = "summarizing"
    completed = "completed"
    error = "error"


class KajianSession(Base):
    __tablename__ = "kajian_sessions"

    # Client-generated UUID (the app already mints one on recording start),
    # kept as the primary key rather than a server-generated id, so the app
    # can reference a session before it's ever synced.
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Object key in MinIO/S3 (not a full URL — the API mints presigned URLs
    # on demand; see app/services/storage.py), null if audio was discarded.
    audio_object_key: Mapped[str | None] = mapped_column(String, nullable=True)

    locale_id: Mapped[str] = mapped_column(String, default="id_ID")
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.recorded
    )

    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa: F821
    transcript: Mapped[list["TranscriptSegment"]] = relationship(  # noqa: F821
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.start_ms",
    )
    note: Mapped["KajianNote | None"] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
