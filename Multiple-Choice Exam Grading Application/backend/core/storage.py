from __future__ import annotations

import io
import time
from functools import lru_cache
from typing import Optional, Protocol

import cv2

from backend.core.config import (
    AWS_S3_BUCKET,
    AWS_S3_ENDPOINT_URL,
    AWS_S3_PRESIGN_EXPIRES_SECONDS,
    AWS_S3_PREFIX,
    AWS_S3_PUBLIC_BASE_URL,
    AWS_S3_REGION,
    RESULTS_DIR,
    STORAGE_BACKEND,
)


class StorageBackend(Protocol):
    def save_image(self, object_key: str, image) -> Optional[str]: ...


class LocalStorageBackend:
    def save_image(self, object_key: str, image) -> Optional[str]:
        if image is None:
            return None
        path = RESULTS_DIR / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)
        timestamp = int(time.time())
        url_path = object_key.replace("\\", "/")
        return f"/results/{url_path}?t={timestamp}"


class S3StorageBackend:
    def __init__(self) -> None:
        if not AWS_S3_BUCKET:
            raise RuntimeError("AWS_S3_BUCKET is required when STORAGE_BACKEND=s3")

        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - runtime dependency guard
            raise RuntimeError("boto3 is required for S3 storage") from exc

        self.bucket = AWS_S3_BUCKET
        self.prefix = AWS_S3_PREFIX
        self.public_base_url = AWS_S3_PUBLIC_BASE_URL
        self.client = boto3.client(
            "s3",
            region_name=AWS_S3_REGION or None,
            endpoint_url=AWS_S3_ENDPOINT_URL,
        )

    def save_image(self, object_key: str, image) -> Optional[str]:
        if image is None:
            return None

        success, encoded = cv2.imencode(".png", image)
        if not success:
          raise ValueError("Could not encode image for upload")

        key = f"{self.prefix}/{object_key}".replace("\\", "/").lstrip("/")
        body = io.BytesIO(encoded.tobytes())
        body.seek(0)
        self.client.upload_fileobj(
            body,
            self.bucket,
            key,
            ExtraArgs={"ContentType": "image/png"},
        )

        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{key}"

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=AWS_S3_PRESIGN_EXPIRES_SECONDS,
        )


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    if STORAGE_BACKEND == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()
