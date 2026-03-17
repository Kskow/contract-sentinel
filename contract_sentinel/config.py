from __future__ import annotations

import os


class Config:
    """Application configuration loaded from environment variables.

    AWS credentials are read from the standard ``AWS_*`` environment variables.
    Sentinel-specific settings use the ``SENTINEL_`` prefix, except ``S3_BUCKET``
    which is a global infrastructure variable shared across services.

    ``Config()`` is constructed *only* inside CLI command handlers — never at
    module import time, so importing any ``contract_sentinel`` module never
    triggers env-var reads or raises on missing variables.
    """

    def __init__(self) -> None:
        # AWS
        self.aws_access_key_id: str = self._require("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key: str = self._require("AWS_SECRET_ACCESS_KEY")
        self.aws_default_region: str = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.aws_endpoint_url: str | None = os.environ.get("AWS_ENDPOINT_URL")  # LocalStack Testing

        # Storage
        self.s3_bucket: str = self._require("S3_BUCKET")
        self.s3_path: str = os.environ.get("SENTINEL_S3_PATH", "contract_tests")

        # Repository
        self.name: str = self._require("SENTINEL_NAME")
        self.framework: str = os.environ.get("SENTINEL_FRAMEWORK", "marshmallow")

    @staticmethod
    def _require(key: str) -> str:
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value
