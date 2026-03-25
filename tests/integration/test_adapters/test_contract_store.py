from __future__ import annotations

import pytest

from contract_sentinel.adapters.contract_store import S3ContractStore


class TestS3ContractStore:
    def test_put_get_roundtrip(self, s3_store: S3ContractStore) -> None:
        content = '{"topic": "orders", "role": "producer"}'

        s3_store.put_file("orders/producer.json", content)

        assert s3_store.get_file("orders/producer.json") == content

    def test_file_exists_returns_true_after_put(self, s3_store: S3ContractStore) -> None:
        s3_store.put_file("orders/producer.json", "{}")

        assert s3_store.file_exists("orders/producer.json") is True

    def test_file_exists_returns_false_for_missing_key(self, s3_store: S3ContractStore) -> None:
        assert s3_store.file_exists("orders/nonexistent.json") is False

    def test_list_files_returns_all_keys_under_prefix(self, s3_store: S3ContractStore) -> None:
        s3_store.put_file("orders/v1.json", '{"version": "1"}')
        s3_store.put_file("orders/v2.json", '{"version": "2"}')

        keys = s3_store.list_files("orders/")

        assert set(keys) == {"orders/v1.json", "orders/v2.json"}

    def test_list_files_returns_empty_for_unknown_prefix(self, s3_store: S3ContractStore) -> None:
        assert s3_store.list_files("nonexistent/") == []

    def test_list_files_does_not_include_keys_outside_prefix(
        self, s3_store: S3ContractStore
    ) -> None:
        s3_store.put_file("orders/producer.json", "{}")
        s3_store.put_file("payments/producer.json", "{}")

        keys = s3_store.list_files("orders/")

        assert keys == ["orders/producer.json"]

    def test_put_is_idempotent(self, s3_store: S3ContractStore) -> None:
        s3_store.put_file("orders/producer.json", '{"version": "1"}')
        s3_store.put_file("orders/producer.json", '{"version": "2"}')

        assert s3_store.get_file("orders/producer.json") == '{"version": "2"}'

    def test_delete_file_removes_the_object(self, s3_store: S3ContractStore) -> None:
        s3_store.put_file("orders/producer.json", "{}")

        s3_store.delete_file("orders/producer.json")

        assert s3_store.file_exists("orders/producer.json") is False

    def test_raises_when_bucket_is_missing(self) -> None:
        with pytest.raises(ValueError, match="requires 'bucket'"):
            S3ContractStore(
                bucket=None,
                path="contract_tests",
                region="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            )

    def test_raises_when_aws_access_key_id_is_missing(self) -> None:
        with pytest.raises(ValueError, match="requires 'aws_access_key_id'"):
            S3ContractStore(
                bucket="test-bucket",
                path="contract_tests",
                region="us-east-1",
                aws_access_key_id=None,
                aws_secret_access_key="test",
            )

    def test_raises_when_aws_secret_access_key_is_missing(self) -> None:
        with pytest.raises(ValueError, match="requires 'aws_secret_access_key'"):
            S3ContractStore(
                bucket="test-bucket",
                path="contract_tests",
                region="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key=None,
            )
