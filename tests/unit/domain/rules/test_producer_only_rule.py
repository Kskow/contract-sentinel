from contract_sentinel.domain.rules.producer_only_rule import UndeclaredFieldRule
from contract_sentinel.domain.schema import ContractField, UnknownFieldBehaviour


class TestUndeclaredFieldRule:
    def test_returns_violation_when_consumer_forbids_unknowns(self) -> None:
        producer = ContractField(name="extra", type="string", is_required=True, is_nullable=False)

        violations = UndeclaredFieldRule(UnknownFieldBehaviour.FORBID).check(producer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "UNDECLARED_FIELD",
            "severity": "CRITICAL",
            "field_path": "extra",
            "producer": {"exists": True},
            "consumer": {"exists": False, "unknown": "forbid"},
            "message": (
                "Field 'extra' is sent by Producer but is not declared"
                " in Consumer (unknown=forbid)."
            ),
        }

    def test_returns_empty_when_consumer_ignores_unknowns(self) -> None:
        producer = ContractField(name="extra", type="string", is_required=True, is_nullable=False)

        assert UndeclaredFieldRule(UnknownFieldBehaviour.IGNORE).check(producer) == []

    def test_returns_empty_when_consumer_allows_unknowns(self) -> None:
        producer = ContractField(name="extra", type="string", is_required=True, is_nullable=False)

        assert UndeclaredFieldRule(UnknownFieldBehaviour.ALLOW).check(producer) == []
