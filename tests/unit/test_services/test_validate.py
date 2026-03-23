from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, create_autospec

import marshmallow

from contract_sentinel.domain.rules.engine import PairViolations
from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField, ContractSchema, UnknownFieldBehaviour
from contract_sentinel.services.validate import (
    ContractReport,
    ContractsValidationReport,
    ValidationStatus,
    validate_local_contracts,
    validate_published_contracts,
)

if TYPE_CHECKING:
    import pytest

    from contract_sentinel.adapters.contract_store import ContractStore


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


def _store(*schemas: ContractSchema) -> ContractStore:
    from contract_sentinel.adapters.contract_store import ContractStore

    store = create_autospec(ContractStore)
    store.list_files.side_effect = lambda prefix: [
        s.to_store_key() for s in schemas if s.to_store_key().startswith(prefix)
    ]
    store.get_file.side_effect = lambda key: json.dumps(
        next(s.to_dict() for s in schemas if s.to_store_key() == key)
    )
    return store


def _parser(*schemas: ContractSchema) -> MagicMock:
    from contract_sentinel.adapters.schema_parser import SchemaParser

    parser_instance = create_autospec(SchemaParser)
    if len(schemas) == 1:
        parser_instance.parse.return_value = schemas[0]
    else:
        schema_list = list(schemas)
        classes = [_MarshmallowClass, _OtherMarshmallowClass]
        schema_map = dict(zip(classes, schema_list, strict=False))
        parser_instance.parse.side_effect = lambda cls: schema_map[cls]

    return MagicMock(return_value=parser_instance)


def _config(name: str = "test-repo") -> MagicMock:
    cfg = MagicMock()
    cfg.name = name
    return cfg


class TestContractReportToDict:
    def test_serialises_empty_pairs(self) -> None:
        report = ContractReport(
            topic="orders", version="1.0.0", status=ValidationStatus.PASSED, pairs=[]
        )

        assert report.to_dict() == {
            "topic": "orders",
            "version": "1.0.0",
            "status": "PASSED",
            "pairs": [],
        }

    def test_serialises_pairs_with_violations(self) -> None:
        report = ContractReport(
            topic="orders",
            version="1.0.0",
            status=ValidationStatus.FAILED,
            pairs=[
                PairViolations(
                    producer_id="orders-service/OrderSchema",
                    consumer_id="checkout-service/OrderSchema",
                    violations=[
                        Violation(
                            rule="TYPE_MISMATCH",
                            severity="CRITICAL",
                            field_path="id",
                            producer={"type": "string"},
                            consumer={"type": "integer"},
                            message=(
                                "Field 'id' is a 'string' in Producer"
                                " but Consumer expects a 'integer'."
                            ),
                        )
                    ],
                )
            ],
        )

        assert report.to_dict() == {
            "topic": "orders",
            "version": "1.0.0",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "orders-service/OrderSchema",
                    "consumer_id": "checkout-service/OrderSchema",
                    "violations": [
                        {
                            "rule": "TYPE_MISMATCH",
                            "severity": "CRITICAL",
                            "field_path": "id",
                            "producer": {"type": "string"},
                            "consumer": {"type": "integer"},
                            "message": (
                                "Field 'id' is a 'string' in Producer"
                                " but Consumer expects a 'integer'."
                            ),
                        }
                    ],
                }
            ],
        }


class TestContractsValidationReportToDict:
    def test_serialises_empty_reports(self) -> None:
        report = ContractsValidationReport(status=ValidationStatus.PASSED, reports=[])

        assert report.to_dict() == {"status": "PASSED", "reports": []}

    def test_serialises_nested_reports_and_pairs(self) -> None:
        report = ContractsValidationReport(
            status=ValidationStatus.FAILED,
            reports=[
                ContractReport(
                    topic="orders",
                    version="1.0.0",
                    status=ValidationStatus.FAILED,
                    pairs=[
                        PairViolations(
                            producer_id="orders-service/OrderSchema",
                            consumer_id="checkout-service/OrderSchema",
                            violations=[
                                Violation(
                                    rule="TYPE_MISMATCH",
                                    severity="CRITICAL",
                                    field_path="id",
                                    producer={"type": "string"},
                                    consumer={"type": "integer"},
                                    message=(
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )

        assert report.to_dict() == {
            "status": "FAILED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "FAILED",
                    "pairs": [
                        {
                            "producer_id": "orders-service/OrderSchema",
                            "consumer_id": "checkout-service/OrderSchema",
                            "violations": [
                                {
                                    "rule": "TYPE_MISMATCH",
                                    "severity": "CRITICAL",
                                    "field_path": "id",
                                    "producer": {"type": "string"},
                                    "consumer": {"type": "integer"},
                                    "message": (
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }


class TestValidateLocalContracts:
    def test_returns_passed_when_no_local_classes(self) -> None:
        result = validate_local_contracts(
            store=_store(),
            parser=_parser(_schema()),
            loader=lambda: [],
            config=_config(),
        )

        assert result.to_dict() == {"status": "PASSED", "reports": []}

    def test_returns_passed_for_compatible_pair(self) -> None:
        producer_schema = _schema(role="producer", fields=[_field("id", "string")])
        consumer_schema = _schema(role="consumer", fields=[_field("id", "string")])

        result = validate_local_contracts(
            store=_store(consumer_schema),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [],
                        }
                    ],
                }
            ],
        }

    def test_returns_failed_when_critical_severity_rule_found(self) -> None:
        producer_schema = _schema(role="producer", fields=[_field("id", "string")])
        consumer_schema = _schema(role="consumer", fields=[_field("id", "integer")])

        result = validate_local_contracts(
            store=_store(consumer_schema),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "FAILED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "FAILED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [
                                {
                                    "rule": "TYPE_MISMATCH",
                                    "severity": "CRITICAL",
                                    "field_path": "id",
                                    "producer": {"type": "string"},
                                    "consumer": {"type": "integer"},
                                    "message": (
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_returns_passed_when_warning_severity_rule_found(self) -> None:
        producer_schema = _schema(role="producer", topic="orders", version="1.0.0")

        result = validate_local_contracts(
            store=_store(),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": None,
                            "violations": [
                                {
                                    "rule": "COUNTERPART_MISMATCH",
                                    "severity": "WARNING",
                                    "field_path": "",
                                    "producer": {},
                                    "consumer": {},
                                    "message": (
                                        "Topic 'orders' version '1.0.0' has 1 producer(s)"
                                        " but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_topic_filter_skips_unmatched_topics(self) -> None:
        result = validate_local_contracts(
            store=_store(),
            parser=_parser(_schema(topic="payments")),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
            topics=["orders"],
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [],
        }

    def test_topic_filter_logs_warning_for_missing_topic(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="contract_sentinel.services.validate"):
            validate_local_contracts(
                store=_store(),
                parser=_parser(_schema()),
                loader=lambda: [],
                config=_config(),
                topics=["orders"],
            )

        assert caplog.record_tuples == [
            (
                "contract_sentinel.services.validate",
                30,
                "Topic 'orders' was requested but no local schema was found for it.",
            )
        ]

    def test_produces_separate_reports_for_different_groups(self) -> None:
        s1 = _schema(topic="orders", version="1.0.0", role="producer")
        s2 = _schema(topic="orders", version="2.0.0", role="producer")

        result = validate_local_contracts(
            store=_store(),
            parser=_parser(s1, s2),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": None,
                            "violations": [
                                {
                                    "rule": "COUNTERPART_MISMATCH",
                                    "severity": "WARNING",
                                    "field_path": "",
                                    "producer": {},
                                    "consumer": {},
                                    "message": (
                                        "Topic 'orders' version '1.0.0' has 1 producer(s)"
                                        " but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                },
                {
                    "topic": "orders",
                    "version": "2.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": None,
                            "violations": [
                                {
                                    "rule": "COUNTERPART_MISMATCH",
                                    "severity": "WARNING",
                                    "field_path": "",
                                    "producer": {},
                                    "consumer": {},
                                    "message": (
                                        "Topic 'orders' version '2.0.0' has 1 producer(s)"
                                        " but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                },
            ],
        }

    def test_global_status_is_failed_when_any_group_fails(self) -> None:
        ok_producer = _schema(topic="orders", fields=[_field("id", "string")])
        ok_consumer = _schema(topic="orders", role="consumer", fields=[_field("id", "string")])
        ok_consumer.repository = "ok-repo"

        bad_producer = _schema(topic="payments", fields=[_field("id", "string")])
        bad_consumer = _schema(topic="payments", role="consumer", fields=[_field("id", "integer")])
        bad_consumer.repository = "bad-repo"

        result = validate_local_contracts(
            store=_store(ok_consumer, bad_consumer),
            parser=_parser(ok_producer, bad_producer),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "FAILED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "ok-repo/OrderSchema",
                            "violations": [],
                        }
                    ],
                },
                {
                    "topic": "payments",
                    "version": "1.0.0",
                    "status": "FAILED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "bad-repo/OrderSchema",
                            "violations": [
                                {
                                    "rule": "TYPE_MISMATCH",
                                    "severity": "CRITICAL",
                                    "field_path": "id",
                                    "producer": {"type": "string"},
                                    "consumer": {"type": "integer"},
                                    "message": (
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                }
                            ],
                        }
                    ],
                },
            ],
        }


class TestValidatePublishedContracts:
    def test_returns_passed_when_store_is_empty(self) -> None:
        result = validate_published_contracts(store=_store())

        assert result.to_dict() == {"status": "PASSED", "reports": []}

    def test_returns_passed_for_compatible_pair(self) -> None:
        producer_schema = _schema(role="producer", fields=[_field("id", "string")])
        consumer_schema = _schema(role="consumer", fields=[_field("id", "string")])

        result = validate_published_contracts(store=_store(producer_schema, consumer_schema))

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [],
                        }
                    ],
                }
            ],
        }

    def test_returns_failed_when_critical_severity_found(self) -> None:
        producer_schema = _schema(role="producer", fields=[_field("id", "string")])
        consumer_schema = _schema(role="consumer", fields=[_field("id", "integer")])

        result = validate_published_contracts(store=_store(producer_schema, consumer_schema))

        assert result.to_dict() == {
            "status": "FAILED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "FAILED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [
                                {
                                    "rule": "TYPE_MISMATCH",
                                    "severity": "CRITICAL",
                                    "field_path": "id",
                                    "producer": {"type": "string"},
                                    "consumer": {"type": "integer"},
                                    "message": (
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_returns_passed_warning_severity_found(self) -> None:
        producer_schema = _schema(role="producer", topic="orders", version="1.0.0")

        result = validate_published_contracts(store=_store(producer_schema))

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": None,
                            "violations": [
                                {
                                    "rule": "COUNTERPART_MISMATCH",
                                    "severity": "WARNING",
                                    "field_path": "",
                                    "producer": {},
                                    "consumer": {},
                                    "message": (
                                        "Topic 'orders' version '1.0.0' has 1 producer(s)"
                                        " but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_topic_filter_skips_unmatched_topics(self) -> None:
        store = _store(
            _schema(topic="payments", role="producer"),
            _schema(topic="payments", role="consumer"),
        )

        result = validate_published_contracts(store=store, topics=["orders"])

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [],
        }

    def test_topic_filter_logs_warning_for_missing_topic(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="contract_sentinel.services.validate"):
            validate_published_contracts(store=_store(), topics=["orders"])

        assert caplog.record_tuples == [
            (
                "contract_sentinel.services.validate",
                30,
                "Topic 'orders' was requested but no published contract was found.",
            )
        ]

    def test_produces_separate_reports_for_different_groups(self) -> None:
        store = _store(
            _schema(topic="orders", version="1.0.0", role="producer"),
            _schema(topic="orders", version="1.0.0", role="consumer"),
            _schema(topic="orders", version="2.0.0", role="producer"),
            _schema(topic="orders", version="2.0.0", role="consumer"),
        )

        result = validate_published_contracts(store=store)

        assert result.to_dict() == {
            "status": "PASSED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [],
                        }
                    ],
                },
                {
                    "topic": "orders",
                    "version": "2.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [],
                        }
                    ],
                },
            ],
        }

    def test_global_status_is_failed_when_any_group_fails(self) -> None:
        ok_fields = [_field("id", "string")]
        bad_fields = [_field("id", "integer")]
        store = _store(
            _schema(topic="orders", version="1.0.0", role="producer", fields=ok_fields),
            _schema(topic="orders", version="1.0.0", role="consumer", fields=ok_fields),
            _schema(topic="payments", version="1.0.0", role="producer", fields=ok_fields),
            _schema(topic="payments", version="1.0.0", role="consumer", fields=bad_fields),
        )

        result = validate_published_contracts(store=store)

        assert result.to_dict() == {
            "status": "FAILED",
            "reports": [
                {
                    "topic": "orders",
                    "version": "1.0.0",
                    "status": "PASSED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [],
                        }
                    ],
                },
                {
                    "topic": "payments",
                    "version": "1.0.0",
                    "status": "FAILED",
                    "pairs": [
                        {
                            "producer_id": "test-repo/OrderSchema",
                            "consumer_id": "test-repo/OrderSchema",
                            "violations": [
                                {
                                    "rule": "TYPE_MISMATCH",
                                    "severity": "CRITICAL",
                                    "field_path": "id",
                                    "producer": {"type": "string"},
                                    "consumer": {"type": "integer"},
                                    "message": (
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                }
                            ],
                        }
                    ],
                },
            ],
        }
