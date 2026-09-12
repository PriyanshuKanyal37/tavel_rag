"""Cloudflare R2. Keys are DERIVED from the content hash, never stored in Postgres.

A presigned URL expires in 15 minutes, so writing one into a row stores garbage.
Signing is local HMAC -- no network call -- so we mint a fresh one per request.
"""
import functools
import mimetypes

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from backend import config


@functools.lru_cache(maxsize=1)
def client():
    config.require("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    return boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        region_name="auto",
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


# ---- the naming convention. Both the writer and the reader call these,
# ---- so the two can never drift apart.
def original_key(sha1: str, ext: str) -> str:
    return f"originals/{sha1}{ext}"


def page_key(sha1: str, page: int) -> str:
    return f"pages/{sha1}/p{page:03d}.png"


def thumb_key(sha1: str, page: int) -> str:
    return f"thumbs/{sha1}/p{page:03d}.jpg"


def crop_key(sha1: str, fact_id: int) -> str:
    return f"crops/{sha1}/f{fact_id}.png"


def put(key: str, data: bytes, content_type: str | None = None) -> str:
    client().put_object(
        Bucket=config.R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type or mimetypes.guess_type(key)[0] or "application/octet-stream",
    )
    return key


def exists(key: str) -> bool:
    try:
        client().head_object(Bucket=config.R2_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def put_if_absent(key: str, data: bytes, content_type: str | None = None) -> bool:
    """Content-hash naming means the same bytes always land on the same key,
    so re-uploading is a no-op. Returns True if it actually wrote."""
    if exists(key):
        return False
    put(key, data, content_type)
    return True


def presign(key: str, ttl: int | None = None) -> str:
    return client().generate_presigned_url(
        "get_object",
        Params={"Bucket": config.R2_BUCKET, "Key": key},
        ExpiresIn=ttl or config.PRESIGN_TTL,
    )


def count(prefix: str = "") -> int:
    p = client().get_paginator("list_objects_v2")
    return sum(page.get("KeyCount", 0) for page in p.paginate(Bucket=config.R2_BUCKET, Prefix=prefix))
