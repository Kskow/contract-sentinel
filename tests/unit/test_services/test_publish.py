from __future__ import annotations

import json
from unittest.mock import MagicMock, call, create_autospec

import marshmallow

from contract_sentinel.adapters.contract_store import ContractStore
from contract_sentinel.adapters.schema_parser import SchemaParser
from contract_sentinel.domain.schema import ContractField, ContractSchema, UnknownFieldBehaviour
from contract_sentinel.services.publish import FailedPublish, PublishReport, publish_contracts


class _MarshmallowClass(marshmallow.Schema):
    """Minimal class recognised by detect_framework as Marshmallow."""


class _OtherMarshmallowClass(marshmallow.Schema):
    """Another minimal class."""


def _field(name: str = "id", type_: str = "string") -> ContractField:
    return ContractField(name=name, type=type_, is_required=True, is_nullable=False)


def _schema(
    *,
    topic: str = "orders",
    role: str = "producer",
    version: str = "1.0.0",
    fields: list[ContractField] | None = None,
) -> ContractSchema:
    return ContractSchema(
        topic=topic,
        role=role,
        version=version,
        repository="test-repo",
        class_name="OrderSchema",
        unknown=UnknownFieldBehaviour.FORBID,
        fields=fields or [],
    )


def _canonical(schema: ContractSchema) -> str:
    """Return the exact JSON string that publish_contracts would write."""
    return json.dumps(schema.to_dict(), sort_keys=True)


def _empty_report() -> dict[str, list[str]]:
    return {"published": [], "updated": [], "unchanged": [], "failed": []}


def _store(
    *,
    exists: bool = False,
    stored_schema: ContractSchema | None = None,
    put_file_error: Exception | None = None,
) -> MagicMock:
    store = create_autospec(ContractStore)
    store.file_exists.return_value = exists
    if stored_schema is not None:
        store.get_file.return_value = _canonical(stored_schema)
    if put_file_error is not None:
        store.put_file.side_effect = put_file_error
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


class TestFailedPublishToDict:
    def test_serialises_key_and_reason(self) -> None:
        f = FailedPublish(key="orders/1.0.0/producer/svc_Schema.json", reason="connection refused")

        assert f.to_dict() == {
            "key": "orders/1.0.0/producer/svc_Schema.json",
            "reason": "connection refused",
        }


class TestPublishReportToDict:
    def test_serialises_counts_and_empty_failures(self) -> None:
        report = PublishReport(
            published=["a", "b"], updated=["c"], unchanged=["d", "e", "f"], failed=[]
        )

        assert report.to_dict() == {
            "published": ["a", "b"],
            "updated": ["c"],
            "unchanged": ["d", "e", "f"],
            "failed": [],
        }

    def test_serialises_failures(self) -> None:
        report = PublishReport(
            published=[],
            updated=[],
            unchanged=[],
            failed=[FailedPublish(key="orders/1.0.0/producer/svc_Schema.json", reason="timeout")],
        )

        assert report.to_dict() == {
            "published": [],
            "updated": [],
            "unchanged": [],
            "failed": [{"key": "orders/1.0.0/producer/svc_Schema.json", "reason": "timeout"}],
        }

    def test_zero_counts(self) -> None:
        assert PublishReport(published=[], updated=[], unchanged=[], failed=[]).to_dict() == (
            _empty_report()
        )


class TestPublishContracts:
    def test_returns_empty_report_when_no_classes(self) -> None:
        store = _store()

        result = publish_contracts(
            store=store,
            parser=_parser(_schema()),
            loader=lambda: [],
            config=_config(),
        )

        assert result.to_dict() == _empty_report()
        store.put_file.assert_not_called()

    def test_publishes_new_contract_when_key_does_not_exist(self) -> None:
        schema = _schema()
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
            "failed": [],
        }
        store.put_file.assert_called_once_with(schema.to_store_key(), _canonical(schema))

    def test_does_not_fetch_stored_content_when_key_is_new(self) -> None:
        store = _store(exists=False)

        publish_contracts(
            store=store,
            parser=_parser(_schema()),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        store.get_file.assert_not_called()

    def test_marks_contract_as_unchanged_when_hash_matches(self) -> None:
        schema = _schema()
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
            "failed": [],
        }
        store.put_file.assert_not_called()

    def test_updates_contract_when_content_hash_has_changed(self) -> None:
        current_schema = _schema(fields=[_field("id", "string")])
        stored_schema = _schema(fields=[_field("id", "integer")])
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
            "failed": [],
        }
        store.put_file.assert_called_once_with(
            current_schema.to_store_key(), _canonical(current_schema)
        )

    def test_counts_are_independent_across_multiple_schemas(self) -> None:
        new_schema = _schema(topic="orders")
        unchanged_schema = _schema(topic="payments")

        store = create_autospec(ContractStore)
        store.file_exists.side_effect = lambda key: "payments" in key
        store.get_file.return_value = _canonical(unchanged_schema)

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
            "failed": [],
        }

    def test_put_file_called_for_each_written_schema(self) -> None:
        s1 = _schema(topic="orders")
        s2 = _schema(topic="payments")

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
        schema = _schema()
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

    def test_write_phase_failure_stored_with_s3_key(self) -> None:
        schema = _schema()

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
            "failed": [{"key": schema.to_store_key(), "reason": "S3 unavailable"}],
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
            "failed": [{"key": "_MarshmallowClass", "reason": "unsupported field type"}],
        }
        store.put_file.assert_not_called()

    def test_parse_failure_aborts_write_phase(self) -> None:
        store = _store()
        good_schema = _schema(topic="orders")

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
            "failed": [{"key": "_OtherMarshmallowClass", "reason": "broken schema"}],
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
            "failed": [
                {"key": "_MarshmallowClass", "reason": "error A"},
                {"key": "_OtherMarshmallowClass", "reason": "error B"},
            ],
        }
        store.put_file.assert_not_called()

    def test_write_phase_continues_after_s3_error(self) -> None:
        failing_schema = _schema(topic="orders")
        good_schema = _schema(topic="payments")

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
            "failed": [{"key": failing_schema.to_store_key(), "reason": "timeout"}],
        }
