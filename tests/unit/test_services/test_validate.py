from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, create_autospec

import marshmallow

from contract_sentinel.services.validate import (
    validate_local_contracts,
    validate_published_contracts,
)
from tests.unit.helpers import create_field, create_schema

if TYPE_CHECKING:
    import pytest

    from contract_sentinel.adapters.contract_store import ContractStore
    from contract_sentinel.domain.schema import ContractSchema


class _MarshmallowClass(marshmallow.Schema):
    """Minimal class recognised by detect_framework as Marshmallow."""


class _OtherMarshmallowClass(marshmallow.Schema):
    """Another minimal class."""


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
    from contract_sentinel.adapters.schema_parsers.parser import SchemaParser

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


class TestValidateLocalContracts:
    def test_returns_passed_when_no_local_classes(self) -> None:
        result = validate_local_contracts(
            store=_store(),
            parser=_parser(create_schema()),
            loader=lambda: [],
            config=_config(),
        )

        assert result.to_dict() == {"status": "PASSED", "contracts": []}

    def test_returns_passed_for_compatible_pair(self) -> None:
        producer_schema = create_schema(role="producer", fields=[create_field("id", "string")])
        consumer_schema = create_schema(role="consumer", fields=[create_field("id", "string")])

        result = validate_local_contracts(
            store=_store(consumer_schema),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders",
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
        producer_schema = create_schema(role="producer", fields=[create_field("id", "string")])
        consumer_schema = create_schema(role="consumer", fields=[create_field("id", "integer")])

        result = validate_local_contracts(
            store=_store(consumer_schema),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "FAILED",
            "contracts": [
                {
                    "topic": "orders",
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
        producer_schema = create_schema(role="producer", topic="orders")

        result = validate_local_contracts(
            store=_store(),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders",
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
                                        "Topic 'orders' has 1 producer(s) but no matching consumer."
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
            parser=_parser(create_schema(topic="payments")),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
            topics=["orders"],
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [],
        }

    def test_topic_filter_logs_warning_for_missing_topic(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="contract_sentinel.services.validate"):
            validate_local_contracts(
                store=_store(),
                parser=_parser(create_schema()),
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

    def test_produces_separate_report_per_topic(self) -> None:
        s1 = create_schema(topic="orders", role="producer")
        s2 = create_schema(topic="payments", role="producer")

        result = validate_local_contracts(
            store=_store(),
            parser=_parser(s1, s2),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders",
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
                                        "Topic 'orders' has 1 producer(s) but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                },
                {
                    "topic": "payments",
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
                                        "Topic 'payments' has 1 producer(s)"
                                        " but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                },
            ],
        }

    def test_validates_against_counterpart_when_topic_contains_slashes(self) -> None:
        producer_schema = create_schema(
            topic="orders/created", role="producer", fields=[create_field("id", "string")]
        )
        consumer_schema = create_schema(
            topic="orders/created", role="consumer", fields=[create_field("id", "string")]
        )

        result = validate_local_contracts(
            store=_store(consumer_schema),
            parser=_parser(producer_schema),
            loader=lambda: [_MarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders/created",
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

    def test_global_status_is_failed_when_any_group_fails(self) -> None:
        ok_producer = create_schema(topic="orders", fields=[create_field("id", "string")])
        ok_consumer = create_schema(
            topic="orders", role="consumer", fields=[create_field("id", "string")]
        )
        ok_consumer.repository = "ok-repo"

        bad_producer = create_schema(topic="payments", fields=[create_field("id", "string")])
        bad_consumer = create_schema(
            topic="payments", role="consumer", fields=[create_field("id", "integer")]
        )
        bad_consumer.repository = "bad-repo"

        result = validate_local_contracts(
            store=_store(ok_consumer, bad_consumer),
            parser=_parser(ok_producer, bad_producer),
            loader=lambda: [_MarshmallowClass, _OtherMarshmallowClass],
            config=_config(),
        )

        assert result.to_dict() == {
            "status": "FAILED",
            "contracts": [
                {
                    "topic": "orders",
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

        assert result.to_dict() == {"status": "PASSED", "contracts": []}

    def test_returns_passed_for_compatible_pair(self) -> None:
        producer_schema = create_schema(role="producer", fields=[create_field("id", "string")])
        consumer_schema = create_schema(role="consumer", fields=[create_field("id", "string")])

        result = validate_published_contracts(store=_store(producer_schema, consumer_schema))

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders",
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
        producer_schema = create_schema(role="producer", fields=[create_field("id", "string")])
        consumer_schema = create_schema(role="consumer", fields=[create_field("id", "integer")])

        result = validate_published_contracts(store=_store(producer_schema, consumer_schema))

        assert result.to_dict() == {
            "status": "FAILED",
            "contracts": [
                {
                    "topic": "orders",
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
        producer_schema = create_schema(role="producer", topic="orders")

        result = validate_published_contracts(store=_store(producer_schema))

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders",
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
                                        "Topic 'orders' has 1 producer(s) but no matching consumer."
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
            create_schema(topic="payments", role="producer"),
            create_schema(topic="payments", role="consumer"),
        )

        result = validate_published_contracts(store=store, topics=["orders"])

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [],
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

    def test_produces_separate_report_per_topic(self) -> None:
        store = _store(
            create_schema(topic="orders", role="producer"),
            create_schema(topic="orders", role="consumer"),
            create_schema(topic="payments", role="producer"),
            create_schema(topic="payments", role="consumer"),
        )

        result = validate_published_contracts(store=store)

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders",
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
        ok_fields = [create_field("id", "string")]
        bad_fields = [create_field("id", "integer")]
        store = _store(
            create_schema(topic="orders", role="producer", fields=ok_fields),
            create_schema(topic="orders", role="consumer", fields=ok_fields),
            create_schema(topic="payments", role="producer", fields=ok_fields),
            create_schema(topic="payments", role="consumer", fields=bad_fields),
        )

        result = validate_published_contracts(store=store)

        assert result.to_dict() == {
            "status": "FAILED",
            "contracts": [
                {
                    "topic": "orders",
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

    def test_topic_filter_works_when_topic_contains_slashes(self) -> None:
        matching = create_schema(topic="orders/created", role="producer")
        excluded = create_schema(topic="payments", role="producer")

        result = validate_published_contracts(
            store=_store(matching, excluded),
            topics=["orders/created"],
        )

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders/created",
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
                                        "Topic 'orders/created' has 1 producer(s)"
                                        " but no matching consumer."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_validates_pair_when_topic_contains_slashes(self) -> None:
        producer_schema = create_schema(
            topic="orders/created", role="producer", fields=[create_field("id", "string")]
        )
        consumer_schema = create_schema(
            topic="orders/created", role="consumer", fields=[create_field("id", "string")]
        )

        result = validate_published_contracts(store=_store(producer_schema, consumer_schema))

        assert result.to_dict() == {
            "status": "PASSED",
            "contracts": [
                {
                    "topic": "orders/created",
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
