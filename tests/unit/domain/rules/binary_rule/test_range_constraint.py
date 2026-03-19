from contract_sentinel.domain.rules.binary_rule import RangeConstraintRule
from contract_sentinel.domain.schema import ContractField
from tests.unit.domain.rules.binary_rule.helpers import field


def _range_field(name: str = "amount", **range_kwargs: object) -> ContractField:
    return field(name=name, type="number", metadata={"range": dict(range_kwargs)})


class TestRangeConstraintRule:
    def test_returns_empty_when_consumer_has_no_range(self) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = field(name="amount", type="number")

        assert RangeConstraintRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_range_within_consumer_range(self) -> None:
        producer = _range_field(min=10, min_inclusive=True, max=90, max_inclusive=True)
        consumer = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        assert RangeConstraintRule().check(producer, consumer) == []

    def test_returns_empty_when_ranges_are_equal(self) -> None:
        f = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        assert RangeConstraintRule().check(f, f) == []

    def test_returns_empty_when_consumer_min_but_producer_min_higher(self) -> None:
        # Producer is MORE constrained on the lower bound — safe.
        producer = _range_field(min=20, min_inclusive=True)
        consumer = _range_field(min=10, min_inclusive=True)

        assert RangeConstraintRule().check(producer, consumer) == []

    def test_returns_empty_when_consumer_max_but_producer_max_lower(self) -> None:
        # Producer is MORE constrained on the upper bound — safe.
        producer = _range_field(max=50, max_inclusive=True)
        consumer = _range_field(max=100, max_inclusive=True)

        assert RangeConstraintRule().check(producer, consumer) == []

    def test_returns_violation_when_producer_has_no_range_consumer_has_range(self) -> None:
        producer = field(name="amount", type="number")
        consumer = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": None},
            "consumer": {
                "range": {"min": 0, "min_inclusive": True, "max": 100, "max_inclusive": True}
            },
            "message": (
                "Field 'amount' has no range constraint in Producer"
                " but Consumer enforces one"
                " — Producer may emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_min_below_consumer_min(self) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = _range_field(min=10, min_inclusive=True)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": {"min": 0, "min_inclusive": True}},
            "consumer": {"range": {"min": 10, "min_inclusive": True}},
            "message": (
                "Field 'amount' Producer minimum 0 (inclusive=True)"
                " is below Consumer minimum 10 (inclusive=True)"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_has_no_min_consumer_requires_min(self) -> None:
        # Producer only constrains max; consumer requires a min too.
        producer = _range_field(max=100, max_inclusive=True)
        consumer = _range_field(min=5, min_inclusive=True, max=100, max_inclusive=True)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": {"max": 100, "max_inclusive": True}},
            "consumer": {
                "range": {"min": 5, "min_inclusive": True, "max": 100, "max_inclusive": True}
            },
            "message": (
                "Field 'amount' Producer has no minimum bound"
                " but Consumer requires min=5 (inclusive=True)"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_for_min_inclusive_boundary(self) -> None:
        # Same numeric min but producer is inclusive while consumer is exclusive —
        # producer can emit the boundary value that consumer rejects.
        producer = _range_field(min=0, min_inclusive=True)
        consumer = _range_field(min=0, min_inclusive=False)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": {"min": 0, "min_inclusive": True}},
            "consumer": {"range": {"min": 0, "min_inclusive": False}},
            "message": (
                "Field 'amount' Producer minimum 0 (inclusive=True)"
                " is below Consumer minimum 0 (inclusive=False)"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_max_above_consumer_max(self) -> None:
        producer = _range_field(max=1000, max_inclusive=True)
        consumer = _range_field(max=100, max_inclusive=True)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": {"max": 1000, "max_inclusive": True}},
            "consumer": {"range": {"max": 100, "max_inclusive": True}},
            "message": (
                "Field 'amount' Producer maximum 1000 (inclusive=True)"
                " exceeds Consumer maximum 100 (inclusive=True)"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_has_no_max_consumer_requires_max(self) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": {"min": 0, "min_inclusive": True}},
            "consumer": {
                "range": {"min": 0, "min_inclusive": True, "max": 100, "max_inclusive": True}
            },
            "message": (
                "Field 'amount' Producer has no maximum bound"
                " but Consumer requires max=100 (inclusive=True)"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_for_max_inclusive_boundary(self) -> None:
        producer = _range_field(max=100, max_inclusive=True)
        consumer = _range_field(max=100, max_inclusive=False)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {"range": {"max": 100, "max_inclusive": True}},
            "consumer": {"range": {"max": 100, "max_inclusive": False}},
            "message": (
                "Field 'amount' Producer maximum 100 (inclusive=True)"
                " exceeds Consumer maximum 100 (inclusive=False)"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_multiple_violations_when_both_bounds_broken(self) -> None:
        producer = _range_field(min=0, min_inclusive=True, max=1000, max_inclusive=True)
        consumer = _range_field(min=10, min_inclusive=True, max=100, max_inclusive=True)

        violations = RangeConstraintRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {
                "range": {"min": 0, "min_inclusive": True, "max": 1000, "max_inclusive": True}
            },
            "consumer": {
                "range": {"min": 10, "min_inclusive": True, "max": 100, "max_inclusive": True}
            },
            "message": (
                "Field 'amount' Producer minimum 0 (inclusive=True)"
                " is below Consumer minimum 10 (inclusive=True)"
                " — Producer can emit values Consumer will reject."
            ),
        }
        assert violations[1].to_dict() == {
            "rule": "RANGE_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "amount",
            "producer": {
                "range": {"min": 0, "min_inclusive": True, "max": 1000, "max_inclusive": True}
            },
            "consumer": {
                "range": {"min": 10, "min_inclusive": True, "max": 100, "max_inclusive": True}
            },
            "message": (
                "Field 'amount' Producer maximum 1000 (inclusive=True)"
                " exceeds Consumer maximum 100 (inclusive=True)"
                " — Producer can emit values Consumer will reject."
            ),
        }
