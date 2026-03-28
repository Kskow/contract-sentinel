from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.direction_mismatch import DirectionMismatchRule
from contract_sentinel.domain.rules.rule import RuleName
from tests.unit.helpers import create_field, create_violation


class TestDirectionMismatchRule:
    def test_returns_violation_when_producer_load_only_consumer_not_dump_only(self) -> None:
        producer = create_field(is_load_only=True)
        consumer = create_field(is_dump_only=False)

        violations = DirectionMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "DIRECTION_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"is_load_only": True},
            "consumer": {"is_dump_only": False},
            "message": (
                "Field 'field' is load-only in Producer"
                " (never included in serialised output)"
                " but Consumer schema expects to receive it."
            ),
        }

    def test_returns_empty_when_producer_load_only_and_consumer_also_dump_only(self) -> None:
        # Consumer only sends this field (dump_only) — it has no expectation of receiving it.
        producer = create_field(is_load_only=True)
        consumer = create_field(is_dump_only=True)

        assert DirectionMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_not_load_only(self) -> None:
        producer = create_field(is_load_only=False)
        consumer = create_field()

        assert DirectionMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_dump_only(self) -> None:
        # dump_only producer always includes the field in its output — no conflict.
        producer = create_field(is_dump_only=True)
        consumer = create_field()

        assert DirectionMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_both_fields_are_regular(self) -> None:
        producer = create_field()
        consumer = create_field()

        assert DirectionMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert DirectionMismatchRule().check(None, create_field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert DirectionMismatchRule().check(create_field(), None) == []

    def test_suggest_fix_returns_direction_instructions(self) -> None:
        violation = create_violation(RuleName.DIRECTION_MISMATCH, field_path="token")

        assert DirectionMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Ensure field 'token' is included in serialised output"
                " (remove any output-exclusion flag)."
            ),
            consumer_suggestion=(
                "Mark field 'token' as input-only,"
                " or remove the expectation of receiving it from the producer."
            ),
        )
