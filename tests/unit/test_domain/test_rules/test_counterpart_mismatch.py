from __future__ import annotations

from contract_sentinel.domain.rules.counterpart_mismatch import CounterpartMismatchRule
from contract_sentinel.domain.schema import ContractSchema, UnknownFieldBehaviour


def _schema(
    topic: str = "orders", version: str = "1.0.0", role: str = "producer"
) -> ContractSchema:
    return ContractSchema(
        topic=topic,
        role=role,
        version=version,
        repository="test-repo",
        class_name="OrderSchema",
        unknown=UnknownFieldBehaviour.FORBID,
        fields=[],
    )


class TestCounterpartMismatchRule:
    def test_returns_empty_when_both_producers_and_consumers_exist(self) -> None:
        producers = [_schema(role="producer")]
        consumers = [_schema(role="consumer")]

        assert CounterpartMismatchRule().check(producers, consumers) == []

    def test_returns_warning_when_only_consumers_exist(self) -> None:
        consumers = [_schema(role="consumer", topic="orders", version="1.1.0")]

        violations = CounterpartMismatchRule().check([], consumers)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "COUNTERPART_MISMATCH",
            "severity": "WARNING",
            "field_path": "",
            "producer": {},
            "consumer": {},
            "message": "Topic 'orders' version '1.1.0' has 1 consumer(s) but no matching producer.",
        }

    def test_returns_warning_when_only_producers_exist(self) -> None:
        producers = [
            _schema(role="producer", topic="orders", version="1.1.0"),
            _schema(role="producer", topic="orders", version="1.1.0"),
        ]

        violations = CounterpartMismatchRule().check(producers, [])

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "COUNTERPART_MISMATCH",
            "severity": "WARNING",
            "field_path": "",
            "producer": {},
            "consumer": {},
            "message": "Topic 'orders' version '1.1.0' has 2 producer(s) but no matching consumer.",
        }

    def test_returns_empty_when_both_lists_are_empty(self) -> None:
        assert CounterpartMismatchRule().check([], []) == []
