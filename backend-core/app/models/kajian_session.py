"""Mirrors the Flutter app's lib/models/kajian_session.dart exactly, so the
API layer can serialize/deserialize without a translation step.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, Float, ForeignKey, Integer, String
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
    # User-typed label, entered before/at recording start — kept even after
    # speaker_id is set below, since it's the original human-entered value
    # and the confirmed profile's name could later be renamed independently.
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    # Links to a confirmed voice profile (see models/speaker.py) once the
    # user confirms a suggested match, or an exact-name auto-match fires.
    # Null until confirmed — never set from an embedding match alone.
    speaker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True
    )
    # Set by transcribe_session (routers/processing.py) right after a fresh
    # /embed-speaker call, cleared once /sessions/{id}/speaker-confirm
    # consumes it (see routers/speakers.py). Exists so confirmation doesn't
    # need to re-download the audio and re-run CPU embedding extraction —
    # the embedding is computed once per transcription, used at most once.
    pending_embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float), nullable=True
    )
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
    speaker_profile: Mapped["Speaker | None"] = relationship(  # noqa: F821
        back_populates="sessions"
    )
