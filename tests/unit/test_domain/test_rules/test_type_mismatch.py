from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import RuleName
from contract_sentinel.domain.rules.type_mismatch import TypeMismatchRule
from tests.unit.helpers import create_field, create_violation


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

    def test_suggest_fix_returns_type_change_instructions(self) -> None:
        violation = create_violation(
            RuleName.TYPE_MISMATCH,
            field_path="id",
            producer={"type": "string"},
            consumer={"type": "integer"},
        )

        assert TypeMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=("Change the type of field 'id' from 'string' to 'integer'."),
            consumer_suggestion=("Change the type of field 'id' from 'integer' to 'string'."),
        )
