from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO

import boto3
from botocore.client import Config

from app.config import get_settings


class Storage:
    """Thin wrapper around the S3-compatible object store (MinIO in dev)."""

    def __init__(self) -> None:
        s = get_settings()
        self._bucket = s.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
            config=Config(signature_version="s3v4"),
        )

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra)

    def get_bytes(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    @contextmanager
    def open_stream(self, key: str) -> Iterator[BytesIO]:
        data = self.get_bytes(key)
        yield BytesIO(data)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_get_url(self, key: str, expires_in: int = 600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )


def content_addressed_key(prefix: str, data: bytes, suffix: str = "") -> str:
    digest = hashlib.sha256(data).hexdigest()
    safe_suffix = suffix if suffix.startswith(".") or not suffix else f".{suffix}"
    return f"{prefix.rstrip('/')}/{digest[:2]}/{digest}{safe_suffix}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
