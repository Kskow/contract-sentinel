from contract_sentinel.domain.rules.requirement_mismatch import RequirementMismatchRule
from tests.unit.helpers import create_field


class TestRequirementMismatchRule:
    def test_returns_violation_when_producer_optional_consumer_required_no_default(self) -> None:
        producer = create_field(is_required=False)
        consumer = create_field(is_required=True)

        violations = RequirementMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "REQUIREMENT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"is_required": False},
            "consumer": {"is_required": True},
            "message": "Field 'field' is optional in Producer but required in Consumer.",
        }

    def test_returns_empty_when_both_required(self) -> None:
        f = create_field(is_required=True)

        assert RequirementMismatchRule().check(f, f) == []

    def test_returns_empty_when_consumer_has_load_default(self) -> None:
        producer = create_field(is_required=False)
        consumer = create_field(is_required=True, metadata={"load_default": "fallback"})

        assert RequirementMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert RequirementMismatchRule().check(None, create_field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert RequirementMismatchRule().check(create_field(), None) == []
