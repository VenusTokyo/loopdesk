"""Screenshot storage. Local disk by default, DigitalOcean Spaces in production.

Screenshots can contain whatever was on the user's screen, so they never go to
a third party: local disk in dev, a private Spaces bucket with signed URLs in
production.
"""
from __future__ import annotations

import base64
import binascii
import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from ..app.config import settings

log = logging.getLogger(__name__)
MAX_BYTES = 8 * 1024 * 1024


class Storage(Protocol):
    def put_png(self, data: bytes, key: str) -> str: ...


class LocalStorage:
    """Writes under ./data/screenshots, served by the app at /files."""

    name = "local"

    def put_png(self, data: bytes, key: str) -> str:
        path = settings.data_dir / "screenshots" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"{settings.public_base_url.rstrip('/')}/files/{key}"


class SpacesStorage:
    """Private bucket + time-limited signed URLs."""

    name = "spaces"

    def __init__(self) -> None:
        import boto3  # imported lazily so local runs need no boto3

        self.bucket = settings.spaces_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.spaces_region,
            endpoint_url=settings.spaces_endpoint,
            aws_access_key_id=settings.spaces_key,
            aws_secret_access_key=settings.spaces_secret,
        )

    def put_png(self, data: bytes, key: str) -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType="image/png", ACL="private"
        )
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=7 * 24 * 3600
        )


def get_storage() -> Storage:
    if settings.storage_backend == "spaces" and settings.spaces_bucket:
        try:
            return SpacesStorage()
        except Exception as exc:  # noqa: BLE001
            log.warning("Spaces unavailable (%s); using local storage", exc)
    return LocalStorage()


def save_screenshot(data_url: str | None) -> str | None:
    """Decode a `data:image/png;base64,...` payload and store it."""
    if not data_url:
        return None
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        log.warning("screenshot was not valid base64; dropping it")
        return None
    if not raw or len(raw) > MAX_BYTES:
        log.warning("screenshot rejected (%s bytes)", len(raw))
        return None

    day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"{day}/{uuid.uuid4().hex}.png"
    try:
        return get_storage().put_png(raw, key)
    except Exception as exc:  # noqa: BLE001 - a lost screenshot must not lose the report
        log.error("screenshot upload failed: %s", exc)
        return None
