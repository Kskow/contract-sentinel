from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, create_autospec

import marshmallow

from contract_sentinel.adapters.contract_store import ContractStore
from contract_sentinel.adapters.schema_parsers.parser import SchemaParser
from contract_sentinel.services.publish import (
    FailedOperation,
    OperationKind,
    PublishReport,
    publish_contracts,
)
from tests.unit.helpers import create_field, create_schema

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractSchema


class _MarshmallowClass(marshmallow.Schema):
    """Minimal class recognised by detect_framework as Marshmallow."""


class _OtherMarshmallowClass(marshmallow.Schema):
    """Another minimal class."""


def _canonical(schema: ContractSchema) -> str:
    """Return the exact JSON string that publish_contracts would write."""
    return json.dumps(schema.to_dict(), sort_keys=True)


def _empty_report() -> dict[str, object]:
    return {"published": [], "updated": [], "unchanged": [], "pruned": [], "failed": []}


def _store(
    *,
    exists: bool = False,
    stored_schema: ContractSchema | None = None,
    put_file_error: Exception | None = None,
    store_keys: list[str] | None = None,
    delete_file_error: Exception | None = None,
) -> MagicMock:
    store = create_autospec(ContractStore)
    store.file_exists.return_value = exists
    if stored_schema is not None:
        store.get_file.return_value = _canonical(stored_schema)
    if put_file_error is not None:
        store.put_file.side_effect = put_file_error
    store.list_files.return_value = store_keys or []
    if delete_file_error is not None:
        store.delete_file.side_effect = delete_file_error
    return store


def _parser(schema: ContractSchema, *extra: ContractSchema) -> MagicMock:
    parser_instance = create_autospec(SchemaParser)
    if not extra:
        parser_instance.parse.return_value = schema
    else:
        schemas = [schema, *extra]
        classes = [_MarshmallowClass, _OtherMarshmallowClass]
        schema_map = dict(zip(classes, schemas, strict=False))
        parser_instance.parse.side_effect = lambda cls: schema_map[cls]
    return MagicMock(return_value=parser_instance)


def _failing_parser(*side_effects: ContractSchema | Exception) -> MagicMock:
    parser_instance = create_autospec(SchemaParser)
    parser_instance.parse.side_effect = list(side_effects)
    return MagicMock(return_value=parser_instance)


def _config(name: str = "test-repo") -> MagicMock:
    cfg = MagicMock()
    cfg.name = name
    return cfg


class TestFailedOperationToDict:
    def test_serialises_operation_key_and_reason(self) -> None:
        f = FailedOperation(
            operation=OperationKind.PUBLISH,
            key="orders/producer/svc/Schema.json",
            reason="connection refused",
        )

        assert f.to_dict() == {
            "operation": "publish",
            "key": "orders/producer/svc/Schema.json",
            "reason": "connection refused",
        }

    def test_prune_operation_serialises_correctly(self) -> None:
        f = FailedOperation(
            operation=OperationKind.PRUNE,
            key="orders/producer/svc/OldSchema.json",
            reason="access denied",
        )

        assert f.to_dict() == {
            "operation": "prune",
            "key": "orders/producer/svc/OldSchema.json",
            "reason": "access denied",
        }


class TestPublishReportToDict:
    def test_serialises_counts_and_empty_failures(self) -> None:
        report = PublishReport(
            published=["a", "b"], updated=["c"], unchanged=["d", "e", "f"], pruned=[], failed=[]
        )

        assert report.to_dict() == {
            "published": ["a", "b"],
            "updated": ["c"],
            "unchanged": ["d", "e", "f"],
            "pruned": [],
            "failed": [],
        }

    def test_serialises_pruned_keys(self) -> None:
        report = PublishReport(
            published=[],
            updated=[],
            unchanged=[],
            pruned=["orders/producer/svc/OldSchema.json"],
            failed=[],
        )

        assert report.to_dict()["pruned"] == ["orders/producer/svc/OldSchema.json"]

    def test_serialises_failures_with_operationcreate_field(self) -> None:
        report = PublishReport(
            published=[],
            updated=[],
            unchanged=[],
            pruned=[],
            failed=[
                FailedOperation(
                    operation=OperationKind.PUBLISH,
                    key="orders/producer/svc/Schema.json",
                    reason="timeout",
                )
            ],
        )

        assert report.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [
                {
                    "operation": "publish",
                    "key": "orders/producer/svc/Schema.json",
                    "reason": "timeout",
                }
            ],
        }

    def test_zero_counts(self) -> None:
        assert (
            PublishReport(published=[], updated=[], unchanged=[], pruned=[], failed=[]).to_dict()
            == _empty_report()
        )


class TestPublishContracts:
    def test_returns_empty_report_when_no_classes(self) -> None:
        store = _store()

        result = publish_contracts(
            store=store,
            parser=_parser(create_schema()),
            loader=lambda: [],
            config=_config(),
        )

        assert result.to_dict() == _empty_report()
        store.put_file.assert_not_called()

    def test_publishes_new_contract_when_key_does_not_exist(self) -> None:
        schema = create_schema()
        store = _store(exists=False)

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [schema.to_store_key()],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [],
        }
        store.put_file.assert_called_once_with(schema.to_store_key(), _canonical(schema))

    def test_does_not_fetch_stored_content_when_key_is_new(self) -> None:
        store = _store(exists=False)

        publish_contracts(
            store=store,
            parser=_parser(create_schema()),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        store.get_file.assert_not_called()

    def test_marks_contract_as_unchanged_when_hash_matches(self) -> None:
        schema = create_schema()
        store = _store(exists=True, stored_schema=schema)

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [schema.to_store_key()],
            "pruned": [],
            "failed": [],
        }
        store.put_file.assert_not_called()

    def test_updates_contract_when_content_hash_has_changed(self) -> None:
        current_schema = create_schema(fields=[create_field("id", "string")])
        stored_schema = create_schema(fields=[create_field("id", "integer")])
        store = _store(exists=True, stored_schema=stored_schema)

        result = publish_contracts(
            store=store,
            parser=_parser(current_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [],
            "updated": [current_schema.to_store_key()],
            "unchanged": [],
            "pruned": [],
            "failed": [],
        }
        store.put_file.assert_called_once_with(
            current_schema.to_store_key(), _canonical(current_schema)
        )

    def test_counts_are_independent_across_multiple_schemas(self) -> None:
        new_schema = create_schema(topic="orders")
        unchanged_schema = create_schema(topic="payments")

        store = create_autospec(ContractStore)
        store.file_exists.side_effect = lambda key: "payments" in key
        store.get_file.return_value = _canonical(unchanged_schema)
        store.list_files.return_value = []

        result = publish_contracts(
            store=store,
            parser=_parser(new_schema, unchanged_schema),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [new_schema.to_store_key()],
            "updated": [],
            "unchanged": [unchanged_schema.to_store_key()],
            "pruned": [],
            "failed": [],
        }

    def test_put_file_called_for_each_writtencreate_schema(self) -> None:
        s1 = create_schema(topic="orders")
        s2 = create_schema(topic="payments")

        store = _store(exists=False)

        publish_contracts(
            store=store,
            parser=_parser(s1, s2),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        store.put_file.assert_has_calls(
            [
                call(s1.to_store_key(), _canonical(s1)),
                call(s2.to_store_key(), _canonical(s2)),
            ],
            any_order=False,
        )

    def test_parser_receives_detected_framework_and_config_name(self) -> None:
        schema = create_schema()
        parser = _parser(schema)

        publish_contracts(
            store=_store(exists=False),
            parser=parser,
            loader=lambda: [_MarshmallowClass],
            config=_config(name="my-service"),
        )

        assert parser.call_count == 1
        _framework, repo_name = parser.call_args.args
        assert repo_name == "my-service"

    def test_write_phase_failure_stored_with_s3_key_and_publish_operation(self) -> None:
        schema = create_schema()
        store = _store(exists=False, put_file_error=RuntimeError("S3 unavailable"))

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [
                {"operation": "publish", "key": schema.to_store_key(), "reason": "S3 unavailable"}
            ],
        }

    def test_parse_failure_uses_class_name_as_identifier(self) -> None:
        store = _store()

        result = publish_contracts(
            store=store,
            parser=_failing_parser(ValueError("unsupported field type")),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [
                {
                    "operation": "publish",
                    "key": "_MarshmallowClass",
                    "reason": "unsupported field type",
                }
            ],
        }
        store.put_file.assert_not_called()

    def test_parse_failure_aborts_write_phase(self) -> None:
        store = _store()
        good_schema = create_schema(topic="orders")

        result = publish_contracts(
            store=store,
            parser=_failing_parser(good_schema, ValueError("broken schema")),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [
                {"operation": "publish", "key": "_OtherMarshmallowClass", "reason": "broken schema"}
            ],
        }
        store.put_file.assert_not_called()

    def test_all_parse_errors_collected_before_aborting(self) -> None:
        store = _store()

        result = publish_contracts(
            store=store,
            parser=_failing_parser(ValueError("error A"), ValueError("error B")),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [
                {"operation": "publish", "key": "_MarshmallowClass", "reason": "error A"},
                {"operation": "publish", "key": "_OtherMarshmallowClass", "reason": "error B"},
            ],
        }
        store.put_file.assert_not_called()

    def test_write_phase_continues_after_s3_error(self) -> None:
        failing_schema = create_schema(topic="orders")
        good_schema = create_schema(topic="payments")

        def _put_side_effect(key: str, _content: str) -> None:
            if "orders" in key:
                raise RuntimeError("timeout")

        store = _store(exists=False)
        store.put_file.side_effect = _put_side_effect
        result = publish_contracts(
            store=store,
            parser=_parser(failing_schema, good_schema),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "published": [good_schema.to_store_key()],
            "updated": [],
            "unchanged": [],
            "pruned": [],
            "failed": [
                {"operation": "publish", "key": failing_schema.to_store_key(), "reason": "timeout"}
            ],
        }

    def test_removes_stale_key_for_renamed_class(self) -> None:
        schema = create_schema(class_name="OrderSchemaV2")
        stale_key = create_schema(class_name="OrderSchema").to_store_key()

        store = _store(
            exists=False,
            store_keys=[schema.to_store_key(), stale_key],
        )

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.pruned == [stale_key]
        store.delete_file.assert_called_once_with(stale_key)

    def test_removes_stale_key_when_topic_contains_slashes(self) -> None:
        # rsplit("/", 3) must correctly identify repository ownership even when
        # the topic itself contains slashes.
        schema = create_schema(topic="orders/created", class_name="OrderSchemaV2")
        stale_key = create_schema(topic="orders/created", class_name="OrderSchema").to_store_key()

        store = _store(
            exists=False,
            store_keys=[schema.to_store_key(), stale_key],
        )

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.pruned == [stale_key]
        store.delete_file.assert_called_once_with(stale_key)

    def test_does_not_prune_keys_owned_by_other_repositories(self) -> None:
        schema = create_schema()
        other_repo_key = create_schema(repository="other-repo").to_store_key()

        store = _store(
            exists=False,
            store_keys=[schema.to_store_key(), other_repo_key],
        )

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.pruned == []
        store.delete_file.assert_not_called()

    def test_prune_phase_is_skipped_when_write_phase_has_failures(self) -> None:
        schema = create_schema()
        stale_key = create_schema(class_name="OldOrderSchema").to_store_key()

        store = _store(
            exists=False,
            put_file_error=RuntimeError("S3 unavailable"),
            store_keys=[stale_key],
        )

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.pruned == []
        store.delete_file.assert_not_called()

    def test_prune_failure_appears_in_failed_list_with_prune_operation(self) -> None:
        schema = create_schema(class_name="OrderSchemaV2")
        stale_key = create_schema(class_name="OrderSchema").to_store_key()

        store = _store(
            exists=False,
            store_keys=[schema.to_store_key(), stale_key],
            delete_file_error=RuntimeError("permission denied"),
        )

        result = publish_contracts(
            store=store,
            parser=_parser(schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.pruned == []
        assert len(result.failed) == 1
        assert result.failed[0].operation == OperationKind.PRUNE
        assert result.failed[0].key == stale_key
        assert result.failed[0].reason == "permission denied"

    def test_prune_phase_is_skipped_when_parse_phase_has_failures(self) -> None:
        stale_key = create_schema(class_name="OldOrderSchema").to_store_key()
        store = _store(store_keys=[stale_key])

        result = publish_contracts(
            store=store,
            parser=_failing_parser(ValueError("broken")),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.pruned == []
        store.delete_file.assert_not_called()
