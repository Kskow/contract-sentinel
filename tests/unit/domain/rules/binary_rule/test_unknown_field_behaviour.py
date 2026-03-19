from contract_sentinel.domain.rules.binary_rule import UnknownFieldBehaviourRule
from contract_sentinel.domain.schema import ContractField, UnknownFieldBehaviour
from tests.unit.domain.rules.binary_rule.helpers import field


def _obj(unknown: UnknownFieldBehaviour | None) -> ContractField:
    return field(type="object", unknown=unknown)


class TestUnknownFieldBehaviourRule:
    def test_returns_violation_when_producer_allow_consumer_forbid(self) -> None:
        producer = _obj(UnknownFieldBehaviour.ALLOW)
        consumer = _obj(UnknownFieldBehaviour.FORBID)

        violations = UnknownFieldBehaviourRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "UNKNOWN_FIELD_BEHAVIOUR_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"unknown": "allow"},
            "consumer": {"unknown": "forbid"},
            "message": (
                "Field 'field' nested schema allows unknown fields ('allow') in Producer"
                " but Consumer restricts them ('forbid'):"
                " extra fields the Producer emits may be rejected."
            ),
        }

    def test_returns_violation_when_producer_ignore_consumer_forbid(self) -> None:
        producer = _obj(UnknownFieldBehaviour.IGNORE)
        consumer = _obj(UnknownFieldBehaviour.FORBID)

        violations = UnknownFieldBehaviourRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].rule == "UNKNOWN_FIELD_BEHAVIOUR_MISMATCH"

    def test_returns_violation_when_producer_allow_consumer_ignore(self) -> None:
        # ALLOW > IGNORE in permissiveness — producer may emit extra fields
        # that consumer silently drops but the contract is still technically wider.
        producer = _obj(UnknownFieldBehaviour.ALLOW)
        consumer = _obj(UnknownFieldBehaviour.IGNORE)

        violations = UnknownFieldBehaviourRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].rule == "UNKNOWN_FIELD_BEHAVIOUR_MISMATCH"

    def test_returns_empty_when_both_forbid(self) -> None:
        f = _obj(UnknownFieldBehaviour.FORBID)

        assert UnknownFieldBehaviourRule().check(f, f) == []

    def test_returns_empty_when_both_allow(self) -> None:
        f = _obj(UnknownFieldBehaviour.ALLOW)

        assert UnknownFieldBehaviourRule().check(f, f) == []

    def test_returns_empty_when_producer_forbid_consumer_allow(self) -> None:
        # Safe direction: consumer more permissive — accepts anything producer sends.
        producer = _obj(UnknownFieldBehaviour.FORBID)
        consumer = _obj(UnknownFieldBehaviour.ALLOW)

        assert UnknownFieldBehaviourRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_ignore_consumer_allow(self) -> None:
        producer = _obj(UnknownFieldBehaviour.IGNORE)
        consumer = _obj(UnknownFieldBehaviour.ALLOW)

        assert UnknownFieldBehaviourRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_unknown_is_none(self) -> None:
        # Primitive field — no nested schema, no unknown policy to compare.
        producer = field(type="string", unknown=None)
        consumer = _obj(UnknownFieldBehaviour.FORBID)

        assert UnknownFieldBehaviourRule().check(producer, consumer) == []

    def test_returns_empty_when_consumer_unknown_is_none(self) -> None:
        producer = _obj(UnknownFieldBehaviour.ALLOW)
        consumer = field(type="string", unknown=None)

        assert UnknownFieldBehaviourRule().check(producer, consumer) == []
