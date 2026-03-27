from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.fix_suggestions import (
    PairFixSuggestion,
    generate_fix_suggestions,
    suggest_fixes,
)
from contract_sentinel.domain.report import (
    ContractReport,
    FixSuggestionsReport,
    TopicFixSuggestions,
    ValidationReport,
)
from contract_sentinel.domain.rules.engine import PairViolations
from tests.unit.helpers import create_violation

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.violation import Violation


def _pair(violations: list[Violation]) -> PairViolations:
    return PairViolations(
        producer_id="repo-a/ProducerSchema",
        consumer_id="repo-b/ConsumerSchema",
        violations=violations,
    )


class TestGenerateFixSuggestions:
    def test_returns_empty_report_when_no_violations(self) -> None:
        report = ValidationReport(contracts=[ContractReport(topic="orders", pairs=[])])

        assert generate_fix_suggestions(report) == FixSuggestionsReport(suggestions=[])

    def test_excludes_topics_where_all_pairs_pass(self) -> None:
        passing_pair = PairViolations(
            producer_id="svc-a/OrderSchema",
            consumer_id="svc-b/OrderConsumer",
            violations=[create_violation("TYPE_MISMATCH", severity="WARNING")],
        )
        failing_pair = PairViolations(
            producer_id="svc-a/PaymentSchema",
            consumer_id="svc-b/PaymentConsumer",
            violations=[create_violation("MISSING_FIELD", field_path="amount")],
        )
        report = ValidationReport(
            contracts=[
                ContractReport(topic="orders", pairs=[passing_pair]),
                ContractReport(topic="payments", pairs=[failing_pair]),
            ]
        )

        assert generate_fix_suggestions(report) == FixSuggestionsReport(
            suggestions=[
                TopicFixSuggestions(
                    topic="payments",
                    pairs=[
                        PairFixSuggestion(
                            producer_id="svc-a/PaymentSchema",
                            consumer_id="svc-b/PaymentConsumer",
                            producer_suggestions="1. Add 'amount' as a required field.",
                            consumer_suggestions=(
                                "1. Add a 'load_default' to field 'amount',"
                                " or mark it as not required."
                            ),
                        )
                    ],
                )
            ]
        )

    def test_excludes_passing_pairs_within_a_failing_topic(self) -> None:
        passing_pair = PairViolations(
            producer_id="svc-a/OrderSchema",
            consumer_id="svc-b/OrderConsumer",
            violations=[],
        )
        failing_pair = PairViolations(
            producer_id="svc-a/OrderSchema",
            consumer_id="svc-c/OrderConsumer",
            violations=[create_violation("MISSING_FIELD", field_path="amount")],
        )
        report = ValidationReport(
            contracts=[ContractReport(topic="orders", pairs=[passing_pair, failing_pair])]
        )

        assert generate_fix_suggestions(report) == FixSuggestionsReport(
            suggestions=[
                TopicFixSuggestions(
                    topic="orders",
                    pairs=[
                        PairFixSuggestion(
                            producer_id="svc-a/OrderSchema",
                            consumer_id="svc-c/OrderConsumer",
                            producer_suggestions="1. Add 'amount' as a required field.",
                            consumer_suggestions=(
                                "1. Add a 'load_default' to field 'amount',"
                                " or mark it as not required."
                            ),
                        )
                    ],
                )
            ]
        )


class TestSuggestFixes:
    def test_returns_none_when_violations_list_is_empty(self) -> None:
        assert suggest_fixes(_pair([])) is None

    def test_returns_none_when_all_violations_are_non_critical(self) -> None:
        assert suggest_fixes(_pair([create_violation("TYPE_MISMATCH", severity="WARNING")])) is None

    def test_filters_out_non_critical_violations_and_only_processes_critical(self) -> None:
        pair = _pair(
            [
                create_violation("TYPE_MISMATCH", severity="WARNING", field_path="ignored"),
                create_violation("MISSING_FIELD", field_path="required_field"),
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions="1. Add 'required_field' as a required field.",
            consumer_suggestions=(
                "1. Add a 'load_default' to field 'required_field', or mark it as not required."
            ),
        )

    def test_multiple_critical_violations_produce_a_numbered_block(self) -> None:
        pair = _pair(
            [
                create_violation(
                    "TYPE_MISMATCH", producer={"type": "String"}, consumer={"type": "Integer"}
                ),
                create_violation("MISSING_FIELD", field_path="other_field"),
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Change the type of field 'field_name' from 'String' to 'Integer'.\n"
                "2. Add 'other_field' as a required field."
            ),
            consumer_suggestions=(
                "1. Change the type of field 'field_name' from 'Integer' to 'String'.\n"
                "2. Add a 'load_default' to field 'other_field', or mark it as not required."
            ),
        )

    def test_type_mismatch_instructions(self) -> None:
        pair = _pair(
            [
                create_violation(
                    "TYPE_MISMATCH", producer={"type": "String"}, consumer={"type": "Integer"}
                )
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Change the type of field 'field_name' from 'String' to 'Integer'."
            ),
            consumer_suggestions=(
                "1. Change the type of field 'field_name' from 'Integer' to 'String'."
            ),
        )

    def test_missing_field_instructions(self) -> None:
        pair = _pair([create_violation("MISSING_FIELD", field_path="email")])

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions="1. Add 'email' as a required field.",
            consumer_suggestions=(
                "1. Add a 'load_default' to field 'email', or mark it as not required."
            ),
        )

    def test_requirement_mismatch_instructions(self) -> None:
        pair = _pair([create_violation("REQUIREMENT_MISMATCH", field_path="status")])

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions="1. Mark field 'status' as required.",
            consumer_suggestions=(
                "1. Add a 'load_default' to field 'status', or mark it as not required."
            ),
        )

    def test_nullability_mismatch_instructions(self) -> None:
        pair = _pair([create_violation("NULLABILITY_MISMATCH", field_path="age")])

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions="1. Remove the nullable constraint from field 'age'.",
            consumer_suggestions="1. Mark field 'age' as nullable.",
        )

    def test_direction_mismatch_instructions(self) -> None:
        pair = _pair([create_violation("DIRECTION_MISMATCH", field_path="token")])

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Ensure field 'token' is included in serialised output"
                " (remove any output-exclusion flag)."
            ),
            consumer_suggestions=(
                "1. Mark field 'token' as input-only,"
                " or remove the expectation of receiving it from the producer."
            ),
        )

    def test_structure_mismatch_instructions(self) -> None:
        pair = _pair([create_violation("STRUCTURE_MISMATCH", field_path="metadata")])

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Replace the open map for field 'metadata' with a fixed-schema nested object."
            ),
            consumer_suggestions=(
                "1. Replace the fixed-schema nested object for field 'metadata' with an open map."
            ),
        )

    def test_undeclared_field_instructions(self) -> None:
        pair = _pair([create_violation("UNDECLARED_FIELD", field_path="extra_field")])

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Remove field 'extra_field' from your schema,"
                " or rename it to match a field declared in the consumer."
            ),
            consumer_suggestions=(
                "1. Declare field 'extra_field' in your schema,"
                " or change the unknown field policy from 'forbid' to 'ignore' or 'allow'."
            ),
        )

    def test_metadata_allowed_values_mismatch_when_producer_has_no_constraint_tells_to_add(
        self,
    ) -> None:
        pair = _pair(
            [
                create_violation(
                    "METADATA_ALLOWED_VALUES_MISMATCH",
                    field_path="category",
                    producer={"allowed_values": None},
                    consumer={"allowed_values": ["A", "B"]},
                )
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Add an allowed-values constraint to field 'category'"
                " whose values are a subset of ['A', 'B']."
            ),
            consumer_suggestions=(
                "1. Expand the allowed values for field 'category' to include None."
            ),
        )

    def test_metadata_allowed_values_mismatch_when_producer_has_constraint_tells_to_restrict(
        self,
    ) -> None:
        pair = _pair(
            [
                create_violation(
                    "METADATA_ALLOWED_VALUES_MISMATCH",
                    field_path="category",
                    producer={"allowed_values": ["A", "B", "C"]},
                    consumer={"allowed_values": ["A", "B"]},
                )
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Restrict the allowed values for field 'category' to ['A', 'B']."
            ),
            consumer_suggestions=(
                "1. Expand the allowed values for field 'category' to include ['A', 'B', 'C']."
            ),
        )

    def test_metadata_range_mismatch_instructions(self) -> None:
        pair = _pair(
            [
                create_violation(
                    "METADATA_RANGE_MISMATCH",
                    field_path="score",
                    producer={"range": (0, 1000)},
                    consumer={"range": (0, 100)},
                )
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Tighten the range constraint on field 'score' to match the consumer: (0, 100)."
            ),
            consumer_suggestions=(
                "1. Widen the range constraint on field 'score'"
                " to accept the producer's range: (0, 1000)."
            ),
        )

    def test_metadata_length_mismatch_instructions(self) -> None:
        pair = _pair(
            [
                create_violation(
                    "METADATA_LENGTH_MISMATCH",
                    field_path="username",
                    producer={"length": (0, 500)},
                    consumer={"length": (0, 50)},
                )
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Tighten the length constraint on field 'username'"
                " to match the consumer: (0, 50)."
            ),
            consumer_suggestions=(
                "1. Widen the length constraint on field 'username'"
                " to accept the producer's length: (0, 500)."
            ),
        )

    def test_metadata_key_mismatch_instructions(self) -> None:
        pair = _pair(
            [
                create_violation(
                    "METADATA_KEY_MISMATCH",
                    field_path="created_at",
                    producer={"format": "iso8601"},
                    consumer={"format": "timestamp"},
                )
            ]
        )

        assert suggest_fixes(pair) == PairFixSuggestion(
            producer_id="repo-a/ProducerSchema",
            consumer_id="repo-b/ConsumerSchema",
            producer_suggestions=(
                "1. Change metadata 'format' on field 'created_at' to 'timestamp'."
            ),
            consumer_suggestions=(
                "1. Change metadata 'format' on field 'created_at' to 'iso8601'."
            ),
        )
