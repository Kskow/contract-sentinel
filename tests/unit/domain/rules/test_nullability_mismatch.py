from contract_sentinel.domain.rules import NullabilityMismatchRule
from tests.unit.domain.rules.helpers import field


class TestNullabilityMismatchRule:
    def test_returns_violation_when_producer_allows_none_consumer_does_not(self) -> None:
        producer = field(is_nullable=True)
        consumer = field(is_nullable=False)

        violations = NullabilityMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "NULLABILITY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"is_nullable": True},
            "consumer": {"is_nullable": False},
            "message": "Field 'field' allows null in Producer but Consumer expects a value.",
        }

    def test_returns_empty_when_both_allow_none(self) -> None:
        f = field(is_nullable=True)

        assert NullabilityMismatchRule().check(f, f) == []

    def test_returns_empty_when_neither_allows_none(self) -> None:
        f = field(is_nullable=False)

        assert NullabilityMismatchRule().check(f, f) == []

    def test_returns_empty_when_consumer_allows_none_but_producer_does_not(self) -> None:
        # Safe direction: consumer is more permissive.
        producer = field(is_nullable=False)
        consumer = field(is_nullable=True)

        assert NullabilityMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert NullabilityMismatchRule().check(None, field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert NullabilityMismatchRule().check(field(), None) == []
