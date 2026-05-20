from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path

import boto3

from app.core.config import get_settings


@dataclass(slots=True)
class StorageBackend:
    def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str: ...

    def upload_file(self, source: Path, key: str, content_type: str | None = None) -> str: ...

    def download_file(self, key: str, destination: Path) -> None: ...

    def url_for(self, key: str) -> str: ...


@dataclass(slots=True)
class LocalStorageBackend(StorageBackend):
    root: Path
    public_base: str = ""

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return self.url_for(key)

    def upload_file(self, source: Path, key: str, content_type: str | None = None) -> str:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return self.url_for(key)

    def download_file(self, key: str, destination: Path) -> None:
        source = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    def url_for(self, key: str) -> str:
        if self.public_base:
            return f"{self.public_base.rstrip('/')}/{key}"
        return f"/storage/{key}"


@dataclass(slots=True)
class S3StorageBackend(StorageBackend):
    bucket: str
    client: object
    public_base: str = ""

    def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra_args)
        return self.url_for(key)

    def upload_file(self, source: Path, key: str, content_type: str | None = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ExtraArgs"] = {"ContentType": content_type}
        if content_type:
            self.client.upload_file(str(source), self.bucket, key, ExtraArgs={"ContentType": content_type})
        else:
            self.client.upload_file(str(source), self.bucket, key)
        return self.url_for(key)

    def download_file(self, key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))

    def url_for(self, key: str) -> str:
        if self.public_base:
            return f"{self.public_base.rstrip('/')}/{key}"
        return f"s3://{self.bucket}/{key}"


def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.s3_bucket and settings.s3_region and settings.storage_access_key and settings.storage_secret_key:
        client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
        )
        return S3StorageBackend(bucket=settings.s3_bucket, client=client, public_base=settings.cdn_base_url)

    return LocalStorageBackend(root=Path(settings.storage_root), public_base=settings.cdn_base_url)
