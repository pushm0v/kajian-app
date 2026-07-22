"""Pydantic request/response models for the API.

Field names match the Flutter app's JSON exactly (camelCase, matching
lib/models/*.dart's toJson()/fromJson()) rather than Python's snake_case
convention, so the app needs no key-renaming logic on either side of the
wire — this is a public API contract, not internal Python code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .models.kajian_session import SessionStatus

# The app's TranscriptSegment.id (and the request bodies that create one)
# is always a plain string, but the DB-generated primary key is a real
# uuid.UUID object — coerce it to str on the way out rather than typing
# these fields as `str` and having Pydantic reject the ORM's UUID value.
_IdStr = Annotated[str, BeforeValidator(str)]


class TranscriptSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: _IdStr
    text: str
    startMs: int = Field(validation_alias="start_ms", serialization_alias="startMs")
    endMs: int = Field(validation_alias="end_ms", serialization_alias="endMs")
    speaker: str | None = None
    isFinal: bool = Field(validation_alias="is_final", serialization_alias="isFinal")


class ScriptureReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    citation: str
    note: str | None = None


class KajianNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str
    keyPoints: list[str] = Field(validation_alias="key_points", serialization_alias="keyPoints")
    topics: list[str] = []
    references: list[ScriptureReferenceOut] = []
    actionItems: list[str] = Field(
        validation_alias="action_items", serialization_alias="actionItems"
    )
    generatedAt: datetime = Field(
        validation_alias="generated_at", serialization_alias="generatedAt"
    )


class KajianSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    speaker: str | None = None
    location: str | None = None
    createdAt: datetime = Field(validation_alias="created_at", serialization_alias="createdAt")
    durationMs: int = Field(validation_alias="duration_ms", serialization_alias="durationMs")
    localeId: str = Field(validation_alias="locale_id", serialization_alias="localeId")
    status: SessionStatus
    transcript: list[TranscriptSegmentOut] = []
    note: KajianNoteOut | None = None
    # True if audio was ever uploaded for this session — the app checks this
    # rather than getting a raw object key, since it must ask this API for
    # a fresh presigned URL each time it actually needs to play/re-process
    # the audio (see GET /sessions/{id}/audio-url). Not present on the ORM
    # model at all — deliberately defaulted here and always set explicitly
    # by _to_out() after model_validate(), rather than sourced via an alias,
    # since it's derived (audio_object_key is not None), not a real column.
    hasAudio: bool = False


class SessionCreateIn(BaseModel):
    id: str
    title: str
    speaker: str | None = None
    location: str | None = None
    createdAt: datetime
    durationMs: int = 0
    localeId: str = "id_ID"
    status: SessionStatus = SessionStatus.recorded


class SessionUpdateIn(BaseModel):
    title: str | None = None
    speaker: str | None = None
    location: str | None = None
    durationMs: int | None = None
    status: SessionStatus | None = None


class TranscriptSegmentIn(BaseModel):
    id: str
    text: str
    startMs: int
    endMs: int = 0
    speaker: str | None = None
    isFinal: bool = True


class TranscriptReplaceIn(BaseModel):
    segments: list[TranscriptSegmentIn]


class ScriptureReferenceIn(BaseModel):
    type: str
    citation: str
    note: str | None = None


class KajianNoteIn(BaseModel):
    summary: str
    keyPoints: list[str] = []
    topics: list[str] = []
    references: list[ScriptureReferenceIn] = []
    actionItems: list[str] = []


class AudioUploadUrlOut(BaseModel):
    uploadUrl: str
    objectKey: str


class AudioDownloadUrlOut(BaseModel):
    downloadUrl: str


class TranscribeRequestIn(BaseModel):
    model: str = "qwen"  # "qwen" | "whisper"


class SummarizeRequestIn(BaseModel):
    model: str | None = None
