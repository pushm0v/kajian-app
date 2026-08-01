"""Generates structured kajian notes from a transcript.

Calls the self-hosted notes service (../backend-notes/), which runs a
quantized Qwen2.5-7B on GPU device 0 and returns the same JSON shape this
module used to get from the Anthropic API. The system prompt and schema
now live there (see its app/notes_model.py) — moving inference in-house
removed the API key requirement entirely and keeps transcripts on the
host, which matters for recordings of private study circles.

This module is now a thin proxy: it owns the URL/token, the timeout, and
the availability contract, not the prompt.
"""

from __future__ import annotations

import logging

import httpx

from .. import config

logger = logging.getLogger("kajian_core")


class NotesUnavailable(RuntimeError):
    """The summarizer can't be reached or isn't configured.

    Distinct from a genuine summarization *failure*: this means the
    feature is switched off or its backend is down, which must not fail
    the session. Transcription is the primary product here and has
    already been persisted by the time summarize runs — see
    routers/processing.py's _run_summarization, which leaves the session
    at status=transcribed rather than error when this is raised.
    """


_EMPTY_NOTES = {
    "summary": "",
    "keyPoints": [],
    "topics": [],
    "references": [],
    "actionItems": [],
}


def generate(transcript: str, title: str | None, model: str | None = None) -> dict:
    """Returns structured notes for `transcript`.

    `model` is accepted for signature compatibility with the previous
    Anthropic implementation (the app and dev-console still send it) but
    is ignored: the notes service serves whichever model it was
    configured with, and switching models is a deploy-time decision there,
    not a per-request one.

    Raises [NotesUnavailable] when the service is unreachable or still
    loading its model (503) — callers degrade rather than fail. Genuine
    errors (the model returning unparseable output, a 500) raise normally,
    since retrying those later doesn't help.
    """
    del model  # See docstring.

    if not transcript.strip():
        return dict(_EMPTY_NOTES)

    if not config.NOTES_BACKEND_URL:
        raise NotesUnavailable(
            "AI notes are not configured on this server (NOTES_BACKEND_URL is unset)."
        )

    headers = (
        {"Authorization": f"Bearer {config.NOTES_BACKEND_TOKEN}"}
        if config.NOTES_BACKEND_TOKEN
        else {}
    )

    logger.info(
        "Notes proxy: POST %s/summarize (transcript_chars=%d) ...",
        config.NOTES_BACKEND_URL, len(transcript),
    )
    try:
        # Generous timeout: a long transcript through a 7B in eager mode on
        # a shared GPU can take a couple of minutes. Still bounded, unlike
        # the ASR proxy calls — this runs inside a background job that
        # shouldn't hang indefinitely on a wedged worker.
        response = httpx.post(
            f"{config.NOTES_BACKEND_URL}/summarize",
            headers=headers,
            json={"transcript": transcript, "title": title},
            timeout=300.0,
        )
    except httpx.RequestError as e:
        raise NotesUnavailable(f"The notes service is unreachable: {e}") from e

    if response.status_code == 503:
        # The service is up but its model hasn't finished loading (or
        # failed to). Recoverable by retrying later, so it's an outage.
        raise NotesUnavailable(
            "The notes service is starting up. Try generating notes again shortly."
        )
    response.raise_for_status()
    return response.json()
