from contract_sentinel.domain.rules import UndeclaredFieldRule
from contract_sentinel.domain.schema import UnknownFieldBehaviour
from tests.unit.domain.rules.helpers import field


class TestUndeclaredFieldRule:
    def test_returns_violation_when_consumer_forbids_unknowns(self) -> None:
        producer_field = field(name="extra", type="string")
        parent_consumer = field(name="payload", type="object", unknown=UnknownFieldBehaviour.FORBID)

        violations = UndeclaredFieldRule().check(producer_field, parent_consumer)

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
        producer_field = field(name="extra", type="string")
        parent_consumer = field(name="payload", type="object", unknown=UnknownFieldBehaviour.IGNORE)

        assert UndeclaredFieldRule().check(producer_field, parent_consumer) == []

    def test_returns_empty_when_consumer_allows_unknowns(self) -> None:
        producer_field = field(name="extra", type="string")
        parent_consumer = field(name="payload", type="object", unknown=UnknownFieldBehaviour.ALLOW)

        assert UndeclaredFieldRule().check(producer_field, parent_consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        parent_consumer = field(name="payload", type="object", unknown=UnknownFieldBehaviour.FORBID)

        assert UndeclaredFieldRule().check(None, parent_consumer) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        producer_field = field(name="extra", type="string")

        assert UndeclaredFieldRule().check(producer_field, None) == []
