"""Audio object storage on an S3-compatible bucket (R2 in production, minio locally)."""

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@lru_cache
def _client(endpoint: str, key_id: str, secret: str, region: str) -> "S3Client":
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class AudioStorage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._public_base = settings.s3_public_base_url.rstrip("/")
        self._s3 = _client(
            settings.s3_endpoint_url,
            settings.s3_access_key_id,
            settings.s3_secret_access_key,
            settings.s3_region,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._s3.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    async def get(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self._s3.get_object, Bucket=self._bucket, Key=key)
        return await asyncio.to_thread(obj["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._s3.delete_object, Bucket=self._bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f"{self._public_base}/{key}"
