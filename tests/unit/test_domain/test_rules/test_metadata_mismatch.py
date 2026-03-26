from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.metadata_mismatch import MetadataMismatchRule
from tests.unit.test_domain.test_rules.helpers import field

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


def _range_field(name: str = "amount", **range_kwargs: object) -> ContractField:
    return field(name=name, type="number", metadata={"range": dict(range_kwargs)})


def _len_field(name: str = "username", **length_kwargs: object) -> ContractField:
    return field(name=name, type="string", metadata={"length": dict(length_kwargs)})


def _enum_field(name: str = "status", allowed: list | None = None) -> ContractField:
    return field(
        name=name,
        type="string",
        metadata={"allowed_values": allowed} if allowed is not None else None,
    )


class TestMetadataMismatchRule:
    def test_returns_violation_per_mismatched_key(self) -> None:
        producer = field(metadata={"timezone": "utc"})
        consumer = field(metadata={"timezone": "est"})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_KEY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"timezone": "utc"},
            "consumer": {"timezone": "est"},
            "message": (
                "Field 'field' has mismatched metadata 'timezone':"
                " Producer has 'utc', Consumer expects 'est'."
            ),
        }

    def test_returns_multiple_violations_for_multiple_mismatches(self) -> None:
        producer = field(metadata={"timezone": "utc", "encoding": "utf-8"})
        consumer = field(metadata={"timezone": "est", "encoding": "ascii"})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "METADATA_KEY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"timezone": "utc"},
            "consumer": {"timezone": "est"},
            "message": (
                "Field 'field' has mismatched metadata 'timezone':"
                " Producer has 'utc', Consumer expects 'est'."
            ),
        }
        assert violations[1].to_dict() == {
            "rule": "METADATA_KEY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"encoding": "utf-8"},
            "consumer": {"encoding": "ascii"},
            "message": (
                "Field 'field' has mismatched metadata 'encoding':"
                " Producer has 'utf-8', Consumer expects 'ascii'."
            ),
        }

    def test_returns_empty_when_metadata_matches(self) -> None:
        f = field(metadata={"timezone": "utc"})

        assert MetadataMismatchRule().check(f, f) == []

    def test_returns_violation_when_producer_metadata_absent_consumer_requires_it(self) -> None:
        producer = field()
        consumer = field(metadata={"timezone": "utc"})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_KEY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"timezone": None},
            "consumer": {"timezone": "utc"},
            "message": (
                "Field 'field' has mismatched metadata 'timezone':"
                " Producer has 'None', Consumer expects 'utc'."
            ),
        }

    def test_returns_empty_when_consumer_metadata_is_none(self) -> None:
        producer = field(metadata={"timezone": "utc"})
        consumer = field()

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_ignores_producer_keys_not_declared_by_consumer(self) -> None:
        producer = field(metadata={"timezone": "utc", "encoding": "utf-8"})
        consumer = field(metadata={"timezone": "utc"})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert MetadataMismatchRule().check(None, field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert MetadataMismatchRule().check(field(), None) == []

    def test_allowed_values_returns_violation_when_producer_emits_unaccepted_values(
        self,
    ) -> None:
        producer = _enum_field(allowed=["active", "inactive", "deleted"])
        consumer = _enum_field(allowed=["active", "inactive"])

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_ALLOWED_VALUES_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "status",
            "producer": {"allowed_values": ["active", "inactive", "deleted"]},
            "consumer": {"allowed_values": ["active", "inactive"]},
            "message": (
                "Field 'status' Producer can emit ['deleted']"
                " but Consumer does not accept those values."
            ),
        }

    def test_allowed_values_returns_empty_when_producer_values_are_subset_of_consumer(self) -> None:
        producer = _enum_field(allowed=["active", "inactive"])
        consumer = _enum_field(allowed=["active", "inactive", "pending"])

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_allowed_values_returns_empty_when_values_are_equal(self) -> None:
        f = _enum_field(allowed=["active", "inactive"])

        assert MetadataMismatchRule().check(f, f) == []

    def test_allowed_values_returns_violation_when_producer_unconstrained_but_consumer_constrained(
        self,
    ) -> None:
        producer = field(name="status")
        consumer = _enum_field(allowed=["active"])

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_ALLOWED_VALUES_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "status",
            "producer": {"allowed_values": None},
            "consumer": {"allowed_values": ["active"]},
            "message": (
                "Field 'status' Producer has no allowed-values constraint"
                " but Consumer restricts accepted values"
                " — Producer may emit values Consumer will reject."
            ),
        }

    def test_allowed_values_returns_empty_when_consumer_has_no_allowed_values(self) -> None:
        producer = _enum_field(allowed=["active"])
        consumer = field(name="status")

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_range_returns_empty_when_consumer_has_no_range(self) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = field(name="amount", type="number")

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_range_returns_empty_when_producer_range_within_consumer_range(self) -> None:
        producer = _range_field(min=10, min_inclusive=True, max=90, max_inclusive=True)
        consumer = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_range_returns_empty_when_ranges_are_equal(self) -> None:
        f = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        assert MetadataMismatchRule().check(f, f) == []

    def test_range_returns_empty_when_consumer_min_but_producer_min_higher(self) -> None:
        # Producer is MORE constrained on the lower bound — safe.
        producer = _range_field(min=20, min_inclusive=True)
        consumer = _range_field(min=10, min_inclusive=True)

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_range_returns_empty_when_consumer_max_but_producer_max_lower(self) -> None:
        # Producer is MORE constrained on the upper bound — safe.
        producer = _range_field(max=50, max_inclusive=True)
        consumer = _range_field(max=100, max_inclusive=True)

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_range_returns_violation_when_producer_has_no_range_consumer_has_range(
        self,
    ) -> None:
        producer = field(name="amount", type="number")
        consumer = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_violation_when_producer_min_below_consumer_min(self) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = _range_field(min=10, min_inclusive=True)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_violation_when_producer_has_no_min_consumer_requires_min(
        self,
    ) -> None:
        # Producer only constrains max; consumer requires a min too.
        producer = _range_field(max=100, max_inclusive=True)
        consumer = _range_field(min=5, min_inclusive=True, max=100, max_inclusive=True)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_violation_for_min_inclusive_boundary(self) -> None:
        # Same numeric min but producer is inclusive while consumer is exclusive —
        # producer can emit the boundary value that consumer rejects.
        producer = _range_field(min=0, min_inclusive=True)
        consumer = _range_field(min=0, min_inclusive=False)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_violation_when_producer_max_above_consumer_max(self) -> None:
        producer = _range_field(max=1000, max_inclusive=True)
        consumer = _range_field(max=100, max_inclusive=True)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_violation_when_producer_has_no_max_consumer_requires_max(
        self,
    ) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = _range_field(min=0, min_inclusive=True, max=100, max_inclusive=True)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_violation_for_max_inclusive_boundary(self) -> None:
        producer = _range_field(max=100, max_inclusive=True)
        consumer = _range_field(max=100, max_inclusive=False)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_range_returns_multiple_violations_when_both_bounds_broken(self) -> None:
        producer = _range_field(min=0, min_inclusive=True, max=1000, max_inclusive=True)
        consumer = _range_field(min=10, min_inclusive=True, max=100, max_inclusive=True)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "METADATA_RANGE_MISMATCH",
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
            "rule": "METADATA_RANGE_MISMATCH",
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

    def test_length_returns_empty_when_consumer_has_no_length(self) -> None:
        producer = _len_field(max=500)
        consumer = field(name="username", type="string")

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_length_returns_empty_when_producer_within_consumer_bounds(self) -> None:
        producer = _len_field(min=3, max=50)
        consumer = _len_field(min=1, max=100)

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_length_returns_empty_when_both_use_same_equal(self) -> None:
        f = _len_field(equal=10)

        assert MetadataMismatchRule().check(f, f) == []

    def test_length_returns_empty_when_consumer_bounds_are_wider(self) -> None:
        # Safe direction — consumer accepts more than producer can ever send.
        producer = _len_field(min=5, max=50)
        consumer = _len_field(min=1, max=200)

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_length_returns_violation_when_producer_has_no_length_consumer_has_length(
        self,
    ) -> None:
        producer = field(name="username", type="string")
        consumer = _len_field(min=3, max=50)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_violation_when_producer_min_below_consumer_min(self) -> None:
        producer = _len_field(min=1, max=100)
        consumer = _len_field(min=5, max=100)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_violation_when_producer_has_no_min_consumer_requires_min(
        self,
    ) -> None:
        producer = _len_field(max=100)
        consumer = _len_field(min=3, max=100)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_violation_when_producer_max_exceeds_consumer_max(self) -> None:
        producer = _len_field(min=1, max=500)
        consumer = _len_field(min=1, max=100)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_violation_when_producer_has_no_max_consumer_requires_max(
        self,
    ) -> None:
        producer = _len_field(min=1)
        consumer = _len_field(min=1, max=100)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_violation_when_producer_equal_differs_from_consumer_equal(
        self,
    ) -> None:
        producer = _len_field(equal=8)
        consumer = _len_field(equal=10)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_violation_when_consumer_equal_and_producer_has_wider_max(
        self,
    ) -> None:
        producer = _len_field(min=1, max=50)
        consumer = _len_field(equal=10)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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
            "rule": "METADATA_LENGTH_MISMATCH",
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

    def test_length_returns_multiple_violations_when_both_bounds_broken(self) -> None:
        producer = _len_field(min=1, max=500)
        consumer = _len_field(min=5, max=100)

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "METADATA_LENGTH_MISMATCH",
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
            "rule": "METADATA_LENGTH_MISMATCH",
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
