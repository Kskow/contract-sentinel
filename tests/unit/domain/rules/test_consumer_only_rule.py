from contract_sentinel.domain.rules.consumer_only_rule import MissingFieldRule
from contract_sentinel.domain.schema import ContractField


class TestMissingFieldRule:
    def test_returns_violation_when_producer_field_absent_and_consumer_required(self) -> None:
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        violations = MissingFieldRule().check(consumer)

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
        consumer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"load_default": "fallback"},
        )

        assert MissingFieldRule().check(consumer) == []
