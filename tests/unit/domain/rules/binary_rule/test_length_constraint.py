from contract_sentinel.domain.rules.binary_rule import LengthConstraintRule
from contract_sentinel.domain.schema import ContractField
from tests.unit.domain.rules.binary_rule.helpers import field


def _len_field(name: str = "username", **length_kwargs: object) -> ContractField:
    return field(name=name, type="string", metadata={"length": dict(length_kwargs)})


class TestLengthConstraintRule:
    def test_returns_empty_when_consumer_has_no_length(self) -> None:
        producer = _len_field(max=500)
        consumer = field(name="username", type="string")

        assert LengthConstraintRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_within_consumer_bounds(self) -> None:
        producer = _len_field(min=3, max=50)
        consumer = _len_field(min=1, max=100)

        assert LengthConstraintRule().check(producer, consumer) == []

    def test_returns_empty_when_both_use_same_equal(self) -> None:
        f = _len_field(equal=10)

        assert LengthConstraintRule().check(f, f) == []

    def test_returns_empty_when_consumer_bounds_are_wider(self) -> None:
        # Safe direction — consumer accepts more than producer can ever send.
        producer = _len_field(min=5, max=50)
        consumer = _len_field(min=1, max=200)

        assert LengthConstraintRule().check(producer, consumer) == []

    def test_returns_violation_when_producer_has_no_length_consumer_has_length(self) -> None:
        producer = field(name="username", type="string")
        consumer = _len_field(min=3, max=50)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": None},
            "consumer": {"length": {"min": 3, "max": 50}},
            "message": (
                "Field 'username' has no length constraint in Producer"
                " but Consumer enforces one"
                " — Producer may emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_min_below_consumer_min(self) -> None:
        producer = _len_field(min=1, max=100)
        consumer = _len_field(min=5, max=100)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1, "max": 100}},
            "consumer": {"length": {"min": 5, "max": 100}},
            "message": (
                "Field 'username' Producer minimum length 1"
                " is below Consumer minimum length 5"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_has_no_min_consumer_requires_min(self) -> None:
        producer = _len_field(max=100)
        consumer = _len_field(min=3, max=100)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"max": 100}},
            "consumer": {"length": {"min": 3, "max": 100}},
            "message": (
                "Field 'username' Producer has no minimum length"
                " but Consumer requires at least 3"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_max_exceeds_consumer_max(self) -> None:
        producer = _len_field(min=1, max=500)
        consumer = _len_field(min=1, max=100)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1, "max": 500}},
            "consumer": {"length": {"min": 1, "max": 100}},
            "message": (
                "Field 'username' Producer maximum length 500"
                " exceeds Consumer maximum length 100"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_has_no_max_consumer_requires_max(self) -> None:
        producer = _len_field(min=1)
        consumer = _len_field(min=1, max=100)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1}},
            "consumer": {"length": {"min": 1, "max": 100}},
            "message": (
                "Field 'username' Producer has no maximum length"
                " but Consumer allows at most 100"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_producer_equal_differs_from_consumer_equal(self) -> None:
        producer = _len_field(equal=8)
        consumer = _len_field(equal=10)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"equal": 8}},
            "consumer": {"length": {"equal": 10}},
            "message": (
                "Field 'username' Producer minimum length 8"
                " is below Consumer minimum length 10"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_violation_when_consumer_equal_and_producer_has_wider_max(self) -> None:
        producer = _len_field(min=1, max=50)
        consumer = _len_field(equal=10)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1, "max": 50}},
            "consumer": {"length": {"equal": 10}},
            "message": (
                "Field 'username' Producer minimum length 1"
                " is below Consumer minimum length 10"
                " — Producer can emit values Consumer will reject."
            ),
        }
        assert violations[1].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1, "max": 50}},
            "consumer": {"length": {"equal": 10}},
            "message": (
                "Field 'username' Producer maximum length 50"
                " exceeds Consumer maximum length 10"
                " — Producer can emit values Consumer will reject."
            ),
        }

    def test_returns_multiple_violations_when_both_bounds_broken(self) -> None:
        producer = _len_field(min=1, max=500)
        consumer = _len_field(min=5, max=100)

        violations = LengthConstraintRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1, "max": 500}},
            "consumer": {"length": {"min": 5, "max": 100}},
            "message": (
                "Field 'username' Producer minimum length 1"
                " is below Consumer minimum length 5"
                " — Producer can emit values Consumer will reject."
            ),
        }
        assert violations[1].to_dict() == {
            "rule": "LENGTH_CONSTRAINT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "username",
            "producer": {"length": {"min": 1, "max": 500}},
            "consumer": {"length": {"min": 5, "max": 100}},
            "message": (
                "Field 'username' Producer maximum length 500"
                " exceeds Consumer maximum length 100"
                " — Producer can emit values Consumer will reject."
            ),
        }
