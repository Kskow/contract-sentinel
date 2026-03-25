from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from contract_sentinel.adapters.contract_store import S3ContractStore
from contract_sentinel.adapters.schema_parser import Marshmallow3Parser
from contract_sentinel.config import Config
from contract_sentinel.domain.errors import (
    MissingDependencyError,
    UnsupportedFrameworkError,
    UnsupportedStorageError,
)
from contract_sentinel.domain.framework import Framework
from contract_sentinel.factory import get_parser, get_store


class TestGetParser:
    def test_returns_marshmallow3_parser_for_marshmallow_framework(self) -> None:
        parser = get_parser(Framework.MARSHMALLOW, "my-service")

        assert isinstance(parser, Marshmallow3Parser)

    def test_marshmallow_parser_carries_the_supplied_repository(self) -> None:
        parser = get_parser(Framework.MARSHMALLOW, "order-service")

        assert isinstance(parser, Marshmallow3Parser)
        assert parser._repository == "order-service"

    def test_raises_unsupported_framework_error_with_descriptive_message(self) -> None:
        with pytest.raises(UnsupportedFrameworkError) as exc_info:
            get_parser("bogus", "my-service")  # type: ignore[arg-type]

        assert str(exc_info.value) == (
            "No adapter registered for framework 'bogus'. Supported frameworks: marshmallow."
        )

    def test_raises_missing_dependency_error_when_marshmallow_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "marshmallow", None)

        with pytest.raises(MissingDependencyError) as exc_info:
            get_parser(Framework.MARSHMALLOW, "my-service")

        assert str(exc_info.value) == (
            "framework 'marshmallow' requires the marshmallow extra.\n"
            "Install it with: pip install contract-sentinel[marshmallow]"
        )


@patch.dict(
    os.environ,
    {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "us-east-1",
        "S3_BUCKET": "test-bucket",
        "SENTINEL_NAME": "my-service",
    },
    clear=True,
)
class TestGetStore:
    def test_returns_s3_contract_store_for_s3_backend(self) -> None:
        config = Config()

        store = get_store(config)

        assert isinstance(store, S3ContractStore)

    def test_s3_store_is_wired_with_config_bucket_and_path(self) -> None:
        bucket_env = {"S3_BUCKET": "contracts-bucket", "SENTINEL_S3_PATH": "sentinel/v1"}
        with patch.dict(os.environ, bucket_env):
            config = Config()

        store = get_store(config)

        # Narrow the type so ty resolves private attributes on the concrete class.
        assert isinstance(store, S3ContractStore)
        assert store._bucket == "contracts-bucket"
        assert store._path == "sentinel/v1"

    def test_raises_unsupported_storage_error_with_descriptive_message(self) -> None:
        with patch.dict(os.environ, {"SENTINEL_STORE": "gcs"}):
            config = Config()

        with pytest.raises(UnsupportedStorageError) as exc_info:
            get_store(config)

        assert str(exc_info.value) == ("Unrecognised store 'gcs'. Valid options: 's3'.")

    def test_store_is_case_insensitive(self) -> None:
        with patch.dict(os.environ, {"SENTINEL_STORE": "S3"}):
            config = Config()

        store = get_store(config)

        assert isinstance(store, S3ContractStore)

    def test_raises_missing_dependency_error_when_boto3_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "boto3", None)
        config = Config()

        with pytest.raises(MissingDependencyError) as exc_info:
            get_store(config)

        assert str(exc_info.value) == (
            "store 's3' requires the s3 extra.\nInstall it with: pip install contract-sentinel[s3]"
        )
