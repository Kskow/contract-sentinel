from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from http import HTTPStatus

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class ContractStore(ABC):
    """Abstract store for reading and writing versioned contract documents.

    All keys are relative — implementations are responsible for any path
    prefixing. ``list_files`` returns keys ordered by recency (newest first)
    so callers can take the first element to resolve the latest contract
    without version parsing.
    """

    @abstractmethod
    def get_file(self, key: str) -> str:
        """Return the string content stored at *key*."""
        ...

    @abstractmethod
    def put_file(self, key: str, content: str) -> None:
        """Write *content* (UTF-8 string) to *key*, overwriting any existing value."""
        ...

    @abstractmethod
    def list_files(self, prefix: str) -> list[str]:
        """Return all keys that share *prefix*, ordered by last-modified descending."""
        ...

    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """Return True if an object exists at *key*, False otherwise."""
        ...


class S3ContractStore(ContractStore):
    """ContractStore implementation backed by AWS S3.

    boto3 is imported lazily inside ``__init__`` so this module loads safely
    without the s3 extra installed. All keys exposed to callers are relative —
    the ``path`` prefix is prepended internally for every S3 operation.
    """

    def __init__(
        self,
        bucket: str,
        path: str,
        region: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        endpoint_url: str | None = None,
    ) -> None:
        import boto3
        from botocore.exceptions import ClientError

        self._bucket = bucket
        self._path = path
        self._client: S3Client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            endpoint_url=endpoint_url,
        )
        self._client_error: type[BaseException] = ClientError

    def get_file(self, key: str) -> str:
        response = self._client.get_object(Bucket=self._bucket, Key=self._full_key(key))
        return response["Body"].read().decode("utf-8")

    def put_file(self, key: str, content: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=self._full_key(key),
            Body=content.encode("utf-8"),
        )

    def list_files(self, prefix: str) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        objects: list[Any] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._full_key(prefix)):
            objects.extend(page.get("Contents", []))

        objects.sort(key=lambda o: o["LastModified"], reverse=True)

        # Strip the path prefix so callers always receive relative keys.
        strip_len = len(self._path) + 1  # +1 for the "/" separator
        return [o["Key"][strip_len:] for o in objects]

    def file_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._full_key(key))
            return True
        except self._client_error as exc:
            if exc.response["Error"]["Code"] == HTTPStatus.NOT_FOUND.value:  # type: ignore[attr-defined]
                return False
            raise

    def _full_key(self, key: str) -> str:
        return f"{self._path}/{key}"
