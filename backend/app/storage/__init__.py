from __future__ import annotations

import io
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.config import settings


def safe_filename(original: str) -> str:
    """Generate a safe, unique filename for storage."""
    name, ext = os.path.splitext(original)
    safe_name = re.sub(r"[^\w\-_]", "_", name)[:64]
    return f"{safe_name}_{uuid4().hex[:8]}{ext}"


class StorageBackend(ABC):
    """Abstract file storage backend."""

    @abstractmethod
    def save(self, content: bytes, filename: str) -> tuple[str, str]:
        """
        Save content and return (storage_path, safe_name).
        storage_path is the internal path used to retrieve the file.
        """
        ...

    @abstractmethod
    def read(self, storage_path: str) -> bytes: ...

    @abstractmethod
    def delete(self, storage_path: str) -> bool: ...

    @abstractmethod
    def exists(self, storage_path: str) -> bool: ...

    @abstractmethod
    def get_url(self, storage_path: str) -> str: ...


class LocalStorage(StorageBackend):
    """Local filesystem storage."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or settings.storage.local_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, filename: str) -> tuple[str, str]:
        safe_name = safe_filename(filename)
        file_path = self.base_path / safe_name
        file_path.write_bytes(content)
        return str(file_path), safe_name

    def read(self, storage_path: str) -> bytes:
        path = Path(storage_path)
        if not path.is_absolute():
            path = self.base_path / path
        return path.read_bytes()

    def delete(self, storage_path: str) -> bool:
        path = Path(storage_path)
        if not path.is_absolute():
            path = self.base_path / path
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, storage_path: str) -> bool:
        path = Path(storage_path)
        if not path.is_absolute():
            path = self.base_path / path
        return path.exists()

    def get_url(self, storage_path: str) -> str:
        """Return a local file:// URL or relative path."""
        return f"file://{Path(storage_path).absolute()}"


class S3Storage(StorageBackend):
    """S3-compatible object storage (MinIO, AWS S3, DigitalOcean Spaces, etc.)."""

    def __init__(
        self,
        endpoint: str | None = None,
        region: str | None = None,
        bucket: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        force_path_style: bool | None = None,
    ):
        self.endpoint = endpoint or settings.storage.s3_endpoint
        self.region = region or settings.storage.s3_region
        self.bucket = bucket or settings.storage.s3_bucket
        self.access_key = access_key or settings.storage.s3_access_key
        self.secret_key = secret_key or settings.storage.s3_secret_key
        self.force_path_style = force_path_style if force_path_style is not None else settings.storage.s3_force_path_style
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            session = boto3.Session(
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )
            extra_kwargs = {}
            if self.endpoint:
                extra_kwargs["endpoint_url"] = self.endpoint
            if self.force_path_style:
                extra_kwargs["config"] = Config(
                    s3={"addressing_style": "path"}
                )
            self._client = session.client("s3", **extra_kwargs)
            # Ensure bucket exists
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass  # Bucket already exists
        return self._client

    def save(self, content: bytes, filename: str) -> tuple[str, str]:
        safe_name = safe_filename(filename)
        key = f"uploads/{safe_name}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key, safe_name

    def read(self, storage_path: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_path)
        return response["Body"].read()

    def delete(self, storage_path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_path)
            return True
        except Exception:
            return False

    def exists(self, storage_path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_path)
            return True
        except Exception:
            return False

    def get_url(self, storage_path: str) -> str:
        if self.endpoint:
            return f"{self.endpoint}/{self.bucket}/{storage_path}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{storage_path}"


def create_storage() -> StorageBackend:
    """Factory: create the appropriate storage backend based on config.
    
    - If S3 endpoint + credentials are configured: use S3Storage
    - Otherwise: use LocalStorage (default for development)
    """
    if settings.storage.is_s3:
        return S3Storage()
    return LocalStorage()
