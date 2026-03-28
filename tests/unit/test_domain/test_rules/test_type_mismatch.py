from contract_sentinel.domain.rules.type_mismatch import TypeMismatchRule
from tests.unit.helpers import create_field


class TestTypeMismatchRule:
    def test_returns_violation_when_types_differ(self) -> None:
        producer = create_field(type="string")
        consumer = create_field(type="integer")

        violations = TypeMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"type": "string"},
            "consumer": {"type": "integer"},
            "message": "Field 'field' is a 'string' in Producer but Consumer expects a 'integer'.",
        }

    def test_returns_empty_when_types_match(self) -> None:
        f = create_field(type="string")

        assert TypeMismatchRule().check(f, f) == []

    def test_returns_empty_when_both_are_objects(self) -> None:
        # Object-level type match; sub-field differences handled by NestedFieldRule.
        f = create_field(type="object")

        assert TypeMismatchRule().check(f, f) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert TypeMismatchRule().check(None, create_field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert TypeMismatchRule().check(create_field(), None) == []
