from __future__ import annotations

from contract_sentinel.domain.rules.counterpart_mismatch import CounterpartMismatchRule
from tests.unit.helpers import create_schema


class TestCounterpartMismatchRule:
    def test_returns_empty_when_both_producers_and_consumers_exist(self) -> None:
        producers = [create_schema(role="producer")]
        consumers = [create_schema(role="consumer")]

        assert CounterpartMismatchRule().check(producers, consumers) == []

    def test_returns_warning_when_only_consumers_exist(self) -> None:
        consumers = [create_schema(role="consumer", topic="orders")]

        violations = CounterpartMismatchRule().check([], consumers)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "COUNTERPART_MISMATCH",
            "severity": "WARNING",
            "field_path": "",
            "producer": {},
            "consumer": {},
            "message": "Topic 'orders' has 1 consumer(s) but no matching producer.",
        }

    def test_returns_warning_when_only_producers_exist(self) -> None:
        producers = [
            create_schema(role="producer", topic="orders"),
            create_schema(role="producer", topic="orders"),
        ]

        violations = CounterpartMismatchRule().check(producers, [])

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "COUNTERPART_MISMATCH",
            "severity": "WARNING",
            "field_path": "",
            "producer": {},
            "consumer": {},
            "message": "Topic 'orders' has 2 producer(s) but no matching consumer.",
        }

    def test_returns_empty_when_both_lists_are_empty(self) -> None:
        assert CounterpartMismatchRule().check([], []) == []
