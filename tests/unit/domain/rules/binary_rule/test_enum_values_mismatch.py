from contract_sentinel.domain.rules.binary_rule import EnumValuesMismatchRule
from contract_sentinel.domain.schema import ContractField
from tests.unit.domain.rules.binary_rule.helpers import field


def _enum_field(allowed: list | None) -> ContractField:
    return field(
        name="status",
        type="string",
        metadata={"format": "enum", "allowed_values": allowed} if allowed is not None else None,
    )


class TestEnumValuesMismatchRule:
    def test_returns_violation_when_producer_emits_value_consumer_cannot_accept(self) -> None:
        producer = _enum_field(["active", "inactive", "deleted"])
        consumer = _enum_field(["active", "inactive"])

        violations = EnumValuesMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "ENUM_VALUES_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "status",
            "producer": {"allowed_values": ["active", "inactive", "deleted"]},
            "consumer": {"allowed_values": ["active", "inactive"]},
            "message": (
                "Field 'status' producer can emit ['deleted']"
                " but Consumer does not accept those values."
            ),
        }

    def test_returns_empty_when_producer_values_are_subset_of_consumer(self) -> None:
        producer = _enum_field(["active", "inactive"])
        consumer = _enum_field(["active", "inactive", "pending"])

        assert EnumValuesMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_values_are_equal(self) -> None:
        f = _enum_field(["active", "inactive"])

        assert EnumValuesMismatchRule().check(f, f) == []

    def test_returns_empty_when_producer_has_no_allowed_values(self) -> None:
        # Unconstrained producer — cannot statically determine what it may emit.
        producer = field(name="status")
        consumer = _enum_field(["active"])

        assert EnumValuesMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_consumer_has_no_allowed_values(self) -> None:
        # Unconstrained consumer — accepts anything.
        producer = _enum_field(["active"])
        consumer = field(name="status")

        assert EnumValuesMismatchRule().check(producer, consumer) == []
