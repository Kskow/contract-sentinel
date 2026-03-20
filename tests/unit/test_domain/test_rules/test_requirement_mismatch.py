from contract_sentinel.domain.rules import RequirementMismatchRule
from tests.unit.test_domain.test_rules.helpers import field


class TestRequirementMismatchRule:
    def test_returns_violation_when_producer_optional_consumer_required_no_default(self) -> None:
        producer = field(is_required=False)
        consumer = field(is_required=True)

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
        f = field(is_required=True)

        assert RequirementMismatchRule().check(f, f) == []

    def test_returns_empty_when_consumer_has_load_default(self) -> None:
        producer = field(is_required=False)
        consumer = field(is_required=True, metadata={"load_default": "fallback"})

        assert RequirementMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert RequirementMismatchRule().check(None, field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert RequirementMismatchRule().check(field(), None) == []
