from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import boto3
import pytest

from contract_sentinel.adapters.contract_store import S3ContractStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def s3_bucket() -> Generator[str, None, None]:
    """Create a uniquely-named S3 bucket and delete all objects inside after the test."""
    s3_client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        endpoint_url="http://localstack:4566",
    )
    bucket_name = f"test-contracts-{uuid.uuid4().hex[:8]}"
    s3_client.create_bucket(Bucket=bucket_name)

    yield bucket_name

    # Delete all objects before removing the bucket (S3 requires an empty bucket).
    response = s3_client.list_objects_v2(Bucket=bucket_name)
    for obj in response.get("Contents", []):
        s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
    s3_client.delete_bucket(Bucket=bucket_name)


@pytest.fixture()
def cli_env(s3_bucket: str) -> dict[str, str]:
    """Environment variable overrides for CLI integration tests.

    Wires the CliRunner invocation to the per-test LocalStack bucket so that
    Config() inside each command handler picks up the correct credentials and
    bucket name without touching the real environment.
    """
    return {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": "http://localstack:4566",
        "SENTINEL_NAME": "test-repo",
        "SENTINEL_S3_PATH": "contract_tests",
        "S3_BUCKET": s3_bucket,
    }


@pytest.fixture()
def s3_store(s3_bucket: str) -> S3ContractStore:
    """S3ContractStore pointed at the test bucket on LocalStack."""
    return S3ContractStore(
        bucket=s3_bucket,
        path="contract_tests",
        region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        endpoint_url="http://localstack:4566",
    )
