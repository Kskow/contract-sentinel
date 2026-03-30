from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.metadata_mismatch import MetadataMismatchRule
from contract_sentinel.domain.rules.rule import RuleName
from tests.unit.helpers import create_field, create_violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


def _range_field(name: str = "amount", **range_kwargs: object) -> ContractField:
    return create_field(name=name, type="number", metadata={"range": dict(range_kwargs)})


def _len_field(name: str = "username", **length_kwargs: object) -> ContractField:
    return create_field(name=name, type="string", metadata={"length": dict(length_kwargs)})


def _enum_field(name: str = "status", allowed: list | None = None) -> ContractField:
    return create_field(
        name=name,
        type="string",
        metadata={"allowed_values": allowed} if allowed is not None else None,
    )


class TestMetadataMismatchRule:
    def test_returns_violation_per_mismatched_key(self) -> None:
        producer = create_field(metadata={"timezone": "utc"})
        consumer = create_field(metadata={"timezone": "est"})

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
        producer = create_field(metadata={"timezone": "utc", "encoding": "utf-8"})
        consumer = create_field(metadata={"timezone": "est", "encoding": "ascii"})

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
        f = create_field(metadata={"timezone": "utc"})

        assert MetadataMismatchRule().check(f, f) == []

    def test_returns_violation_when_producer_metadata_absent_consumer_requires_it(self) -> None:
        producer = create_field()
        consumer = create_field(metadata={"timezone": "utc"})

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
        producer = create_field(metadata={"timezone": "utc"})
        consumer = create_field()

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_ignores_producer_keys_not_declared_by_consumer(self) -> None:
        producer = create_field(metadata={"timezone": "utc", "encoding": "utf-8"})
        consumer = create_field(metadata={"timezone": "utc"})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert MetadataMismatchRule().check(None, create_field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert MetadataMismatchRule().check(create_field(), None) == []

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
        producer = create_field(name="status")
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
        consumer = create_field(name="status")

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_range_returns_empty_when_consumer_has_no_range(self) -> None:
        producer = _range_field(min=0, min_inclusive=True)
        consumer = create_field(name="amount", type="number")

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
        producer = create_field(name="amount", type="number")
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
        consumer = create_field(name="username", type="string")

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
        producer = create_field(name="username", type="string")
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

    def test_suggest_fix_allowed_values_when_producer_unconstrained(self) -> None:
        violation = create_violation(
            RuleName.METADATA_ALLOWED_VALUES_MISMATCH,
            field_path="status",
            producer={"allowed_values": None},
            consumer={"allowed_values": ["active", "inactive"]},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Add an allowed-values constraint to field 'status'"
                " whose values are a subset of ['active', 'inactive']."
            ),
            consumer_suggestion=("Expand the allowed values for field 'status' to include None."),
        )

    def test_suggest_fix_allowed_values_when_producer_has_constraint(self) -> None:
        violation = create_violation(
            RuleName.METADATA_ALLOWED_VALUES_MISMATCH,
            field_path="status",
            producer={"allowed_values": ["active", "inactive", "deleted"]},
            consumer={"allowed_values": ["active", "inactive"]},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Restrict the allowed values for field 'status' to ['active', 'inactive']."
            ),
            consumer_suggestion=(
                "Expand the allowed values for field 'status'"
                " to include ['active', 'inactive', 'deleted']."
            ),
        )

    def test_suggest_fix_range_mismatch(self) -> None:
        violation = create_violation(
            RuleName.METADATA_RANGE_MISMATCH,
            field_path="score",
            producer={"range": {"min": 0, "max": 1000}},
            consumer={"range": {"min": 0, "max": 100}},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Tighten the range constraint on field 'score'"
                " to match the consumer: {'min': 0, 'max': 100}."
            ),
            consumer_suggestion=(
                "Widen the range constraint on field 'score'"
                " to accept the producer's range: {'min': 0, 'max': 1000}."
            ),
        )

    def test_suggest_fix_length_mismatch(self) -> None:
        violation = create_violation(
            RuleName.METADATA_LENGTH_MISMATCH,
            field_path="username",
            producer={"length": {"min": 1, "max": 500}},
            consumer={"length": {"min": 3, "max": 100}},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Tighten the length constraint on field 'username'"
                " to match the consumer: {'min': 3, 'max': 100}."
            ),
            consumer_suggestion=(
                "Widen the length constraint on field 'username'"
                " to accept the producer's length: {'min': 1, 'max': 500}."
            ),
        )

    def test_suggest_fix_key_mismatch(self) -> None:
        violation = create_violation(
            RuleName.METADATA_KEY_MISMATCH,
            field_path="created_at",
            producer={"format": "iso8601"},
            consumer={"format": "timestamp"},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=("Change metadata 'format' on field 'created_at' to 'timestamp'."),
            consumer_suggestion=("Change metadata 'format' on field 'created_at' to 'iso8601'."),
        )

    def test_forbidden_values_returns_violation_when_producer_does_not_cover_all_consumer_forbidden(
        self,
    ) -> None:
        producer = create_field(metadata={"forbidden_values": ["deleted"]})
        consumer = create_field(metadata={"forbidden_values": ["deleted", "banned"]})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_FORBIDDEN_VALUES_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"forbidden_values": ["deleted"]},
            "consumer": {"forbidden_values": ["deleted", "banned"]},
            "message": (
                "Field 'field' Producer does not forbid ['banned']"
                " which Consumer rejects — Producer may emit values Consumer will reject."
            ),
        }

    def test_forbidden_values_returns_violation_when_producer_has_no_forbidden_values(
        self,
    ) -> None:
        producer = create_field()
        consumer = create_field(metadata={"forbidden_values": ["deleted", "banned"]})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_FORBIDDEN_VALUES_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"forbidden_values": None},
            "consumer": {"forbidden_values": ["deleted", "banned"]},
            "message": (
                "Field 'field' Producer has no forbidden-values constraint"
                " but Consumer forbids some values"
                " — Producer may emit values Consumer will reject."
            ),
        }

    def test_forbidden_values_returns_empty_when_producer_is_superset_of_consumer(self) -> None:
        producer = create_field(metadata={"forbidden_values": ["deleted", "banned", "suspended"]})
        consumer = create_field(metadata={"forbidden_values": ["deleted", "banned"]})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_forbidden_values_returns_empty_when_consumer_has_no_forbidden_values(self) -> None:
        producer = create_field(metadata={"forbidden_values": ["deleted"]})
        consumer = create_field()

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_contains_only_returns_violation_when_producer_can_emit_items_consumer_rejects(
        self,
    ) -> None:
        producer = create_field(metadata={"contains_only": ["red", "green", "blue", "yellow"]})
        consumer = create_field(metadata={"contains_only": ["red", "green", "blue"]})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_CONTAINS_ONLY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"contains_only": ["red", "green", "blue", "yellow"]},
            "consumer": {"contains_only": ["red", "green", "blue"]},
            "message": (
                "Field 'field' Producer can emit items ['yellow'] that Consumer does not accept."
            ),
        }

    def test_contains_only_returns_violation_when_producer_has_no_contains_only(self) -> None:
        producer = create_field()
        consumer = create_field(metadata={"contains_only": ["red", "green", "blue"]})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_CONTAINS_ONLY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"contains_only": None},
            "consumer": {"contains_only": ["red", "green", "blue"]},
            "message": (
                "Field 'field' Producer has no contains-only constraint"
                " but Consumer restricts accepted items"
                " — Producer may emit items Consumer will reject."
            ),
        }

    def test_contains_only_returns_empty_when_producer_choices_are_subset_of_consumer(
        self,
    ) -> None:
        producer = create_field(metadata={"contains_only": ["red", "green"]})
        consumer = create_field(metadata={"contains_only": ["red", "green", "blue"]})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_contains_only_returns_empty_when_consumer_has_no_contains_only(self) -> None:
        producer = create_field(metadata={"contains_only": ["red"]})
        consumer = create_field()

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_contains_none_of_returns_violation_when_producer_does_not_cover_all_consumer_excluded(
        self,
    ) -> None:
        producer = create_field(metadata={"contains_none_of": ["profanity"]})
        consumer = create_field(metadata={"contains_none_of": ["profanity", "spam"]})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_CONTAINS_NONE_OF_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"contains_none_of": ["profanity"]},
            "consumer": {"contains_none_of": ["profanity", "spam"]},
            "message": (
                "Field 'field' Producer does not exclude ['spam']"
                " which Consumer rejects — Producer may include items Consumer will reject."
            ),
        }

    def test_contains_none_of_returns_violation_when_producer_has_no_contains_none_of(
        self,
    ) -> None:
        producer = create_field()
        consumer = create_field(metadata={"contains_none_of": ["profanity"]})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_CONTAINS_NONE_OF_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"contains_none_of": None},
            "consumer": {"contains_none_of": ["profanity"]},
            "message": (
                "Field 'field' Producer has no contains-none-of constraint"
                " but Consumer excludes some items"
                " — Producer may include items Consumer will reject."
            ),
        }

    def test_contains_none_of_returns_empty_when_producer_is_superset_of_consumer(self) -> None:
        producer = create_field(metadata={"contains_none_of": ["profanity", "spam", "ads"]})
        consumer = create_field(metadata={"contains_none_of": ["profanity", "spam"]})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_contains_none_of_returns_empty_when_consumer_has_no_contains_none_of(self) -> None:
        producer = create_field(metadata={"contains_none_of": ["profanity"]})
        consumer = create_field()

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_equal_mismatch_uses_generic_key_mismatch_rule(self) -> None:
        producer = create_field(metadata={"equal": "active"})
        consumer = create_field(metadata={"equal": "pending"})

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_KEY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"equal": "active"},
            "consumer": {"equal": "pending"},
            "message": (
                "Field 'field' has mismatched metadata 'equal':"
                " Producer has 'active', Consumer expects 'pending'."
            ),
        }

    def test_suggest_fix_forbidden_values_when_producer_unconstrained(self) -> None:
        violation = create_violation(
            RuleName.METADATA_FORBIDDEN_VALUES_MISMATCH,
            field_path="status",
            producer={"forbidden_values": None},
            consumer={"forbidden_values": ["deleted", "banned"]},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Add a NoneOf constraint to field 'status'"
                " that forbids at least ['deleted', 'banned']."
            ),
            consumer_suggestion=(
                "Reduce the forbidden_values constraint on field 'status'"
                " to only include values the producer also forbids."
            ),
        )

    def test_suggest_fix_contains_only_when_producer_unconstrained(self) -> None:
        violation = create_violation(
            RuleName.METADATA_CONTAINS_ONLY_MISMATCH,
            field_path="colors",
            producer={"contains_only": None},
            consumer={"contains_only": ["red", "green", "blue"]},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Add a ContainsOnly constraint to field 'colors'"
                " restricting emitted items to a subset of ['red', 'green', 'blue']."
            ),
            consumer_suggestion=(
                "Expand the ContainsOnly constraint on field 'colors'"
                " to include all items the producer may emit."
            ),
        )

    def test_suggest_fix_contains_none_of_when_producer_unconstrained(self) -> None:
        violation = create_violation(
            RuleName.METADATA_CONTAINS_NONE_OF_MISMATCH,
            field_path="tags",
            producer={"contains_none_of": None},
            consumer={"contains_none_of": ["profanity"]},
        )

        assert MetadataMismatchRule().suggest_fix(violation) == FixSuggestion(
            producer_suggestion=(
                "Add a ContainsNoneOf constraint to field 'tags'"
                " that excludes at least ['profanity']."
            ),
            consumer_suggestion=(
                "Reduce the ContainsNoneOf constraint on field 'tags'"
                " to only include values the producer also excludes."
            ),
        )
