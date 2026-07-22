# Core platform API — users, kajian sessions/transcripts/notes, audio
# storage. No GPU needed here at all (that's ../backend/ and
# ../backend-whisper/, which this service proxies /transcribe to).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY scripts ./scripts

EXPOSE 8080

# Applies any pending migrations, then starts the API. Safe to run on
# every container start — Alembic no-ops if already at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
