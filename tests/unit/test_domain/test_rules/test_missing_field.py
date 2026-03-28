from contract_sentinel.domain.rules.missing_field import MissingFieldRule
from tests.unit.helpers import create_field


class TestMissingFieldRule:
    def test_returns_violation_when_producer_field_absent_and_consumer_required(self) -> None:
        consumer = create_field()

        violations = MissingFieldRule().check(None, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "MISSING_FIELD",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"exists": False},
            "consumer": {"is_required": True},
            "message": "Field 'field' is missing in Producer but required in Consumer.",
        }

    def test_returns_empty_when_consumer_has_default(self) -> None:
        consumer = create_field(metadata={"load_default": "fallback"})

        assert MissingFieldRule().check(None, consumer) == []

    def test_returns_empty_when_consumer_is_not_required(self) -> None:
        consumer = create_field(is_required=False)

        assert MissingFieldRule().check(None, consumer) == []

    def test_returns_empty_when_producer_is_present(self) -> None:
        # Both sides present — not a missing-field scenario.
        assert MissingFieldRule().check(create_field(), create_field()) == []
