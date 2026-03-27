from contract_sentinel.domain.rules import UndeclaredFieldRule
from contract_sentinel.domain.schema import UnknownFieldBehaviour
from tests.unit.helpers import create_field


class TestUndeclaredFieldRule:
    def test_returns_violation_when_consumer_forbids_unknowns(self) -> None:
        producer_field = create_field(name="extra", type="string")

        violations = UndeclaredFieldRule().check(producer_field, UnknownFieldBehaviour.FORBID)

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
        producer_field = create_field(name="extra", type="string")

        assert UndeclaredFieldRule().check(producer_field, UnknownFieldBehaviour.IGNORE) == []

    def test_returns_empty_when_consumer_allows_unknowns(self) -> None:
        producer_field = create_field(name="extra", type="string")

        assert UndeclaredFieldRule().check(producer_field, UnknownFieldBehaviour.ALLOW) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert UndeclaredFieldRule().check(None, UnknownFieldBehaviour.FORBID) == []

    def test_returns_empty_when_unknown_is_none(self) -> None:
        producer_field = create_field(name="extra", type="string")

        assert UndeclaredFieldRule().check(producer_field, None) == []
