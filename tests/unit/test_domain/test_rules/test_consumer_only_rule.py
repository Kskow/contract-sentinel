from contract_sentinel.domain.rules.missing_field import MissingFieldRule
from contract_sentinel.domain.schema import ContractField


class TestMissingFieldRule:
    def test_returns_violation_when_producer_field_absent_and_consumer_required(self) -> None:
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

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
        consumer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"load_default": "fallback"},
        )

        assert MissingFieldRule().check(None, consumer) == []

    def test_returns_empty_when_consumer_is_not_required(self) -> None:
        consumer = ContractField(name="field", type="string", is_required=False, is_nullable=False)

        assert MissingFieldRule().check(None, consumer) == []

    def test_returns_empty_when_producer_is_present(self) -> None:
        # Both sides present — not a missing-field scenario.
        producer = ContractField(name="field", type="string", is_required=True, is_nullable=False)
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        assert MissingFieldRule().check(producer, consumer) == []
