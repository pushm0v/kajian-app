"""Audio file storage via MinIO (or any S3-compatible object store), using
boto3's S3 client — MinIO is API-compatible with S3, so no MinIO-specific
SDK is needed.

Design: the API never proxies raw audio bytes through itself. Instead it
mints short-lived presigned URLs and hands them to the Flutter app, which
uploads/downloads directly to/from the object store. This keeps the API
server's own bandwidth/CPU out of the (potentially large, 90-minute
recording) file transfer path entirely.
"""

from __future__ import annotations

import boto3
from botocore.client import Config as BotoConfig

from .. import config

_client = boto3.client(
    "s3",
    endpoint_url=config.S3_ENDPOINT_URL,
    aws_access_key_id=config.S3_ACCESS_KEY,
    aws_secret_access_key=config.S3_SECRET_KEY,
    region_name=config.S3_REGION,
    use_ssl=config.S3_USE_SSL,
    config=BotoConfig(signature_version="s3v4"),
)


def ensure_bucket() -> None:
    """Creates the configured bucket if it doesn't already exist. Called
    once at API startup — safe to call repeatedly (no-ops if present)."""
    existing = {b["Name"] for b in _client.list_buckets().get("Buckets", [])}
    if config.S3_BUCKET not in existing:
        _client.create_bucket(Bucket=config.S3_BUCKET)


def object_key_for_session(user_id: str, session_id: str) -> str:
    """Deterministic object key so re-uploads for the same session overwrite
    cleanly, and admin tooling can locate a session's audio without a DB
    lookup if needed. Keyed by user first so per-user exports/cleanup (e.g.
    account deletion) can be done with a single prefix listing."""
    return f"{user_id}/{session_id}.m4a"


def presigned_upload_url(object_key: str) -> str:
    return _client.generate_presigned_url(
        "put_object",
        Params={"Bucket": config.S3_BUCKET, "Key": object_key},
        ExpiresIn=config.PRESIGNED_URL_TTL_SECONDS,
    )


def presigned_download_url(object_key: str) -> str:
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": config.S3_BUCKET, "Key": object_key},
        ExpiresIn=config.PRESIGNED_URL_TTL_SECONDS,
    )


def delete_object(object_key: str) -> None:
    _client.delete_object(Bucket=config.S3_BUCKET, Key=object_key)


def download_to_path(object_key: str, dest_path: str) -> None:
    """Downloads an object to a local path — used server-side when proxying
    a session's audio to an ASR worker for /transcribe (the worker needs
    the actual file, not just a URL the app could reach)."""
    _client.download_file(config.S3_BUCKET, object_key, dest_path)
