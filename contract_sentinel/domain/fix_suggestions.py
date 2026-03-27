from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestionsReport, TopicFixSuggestions

if TYPE_CHECKING:
    from contract_sentinel.domain.report import ContractReport, ContractsValidationReport
    from contract_sentinel.domain.rules.engine import PairViolations
    from contract_sentinel.domain.rules.violation import Violation


@dataclasses.dataclass
class FixSuggestion:
    """Atomic fix unit — one per CRITICAL violation."""

    producer_suggestion: str
    consumer_suggestion: str


@dataclasses.dataclass
class PairFixSuggestion:
    """Pre-rendered fix blocks for one producer/consumer pair."""

    producer_id: str
    consumer_id: str
    producer_suggestions: str
    consumer_suggestions: str


def build_contracts_fix_report(
    validation_report: ContractsValidationReport,
) -> FixSuggestionsReport:
    """Transform a full validation report into a sparse FixSuggestionsReport."""
    suggestions_by_topic: list[TopicFixSuggestions] = []
    for contract_report in validation_report.reports:
        fix_report = _suggest_contract_fixes(contract_report)
        if fix_report is not None:
            suggestions_by_topic.append(fix_report)
    return FixSuggestionsReport(suggestions_by_topic=suggestions_by_topic)


def _suggest_contract_fixes(contract_report: ContractReport) -> TopicFixSuggestions | None:
    """Build a TopicFixSuggestions for one topic — returns ``None`` if all pairs pass."""
    pairs: list[PairFixSuggestion] = []
    for pair in contract_report.pairs:
        pair_fix = suggest_fixes(pair)
        if pair_fix is not None:
            pairs.append(pair_fix)
    if not pairs:
        return None
    return TopicFixSuggestions(topic=contract_report.topic, pairs=pairs)


def suggest_fixes(pair: PairViolations) -> PairFixSuggestion | None:
    """Return fix suggestions for every CRITICAL violation in *pair*."""
    critical = [v for v in pair.violations if v.severity == "CRITICAL"]
    if not critical:
        return None

    instructions: list[FixSuggestion] = []
    for violation in critical:
        fix = _instruction_for(violation)
        if fix is not None:
            instructions.append(fix)

    if not instructions:
        return None

    # COUNTERPART_MISMATCH — the only rule that sets ids to None — is WARNING
    # severity and is excluded by the critical filter above.
    assert pair.producer_id is not None
    assert pair.consumer_id is not None

    return PairFixSuggestion(
        producer_id=pair.producer_id,
        consumer_id=pair.consumer_id,
        producer_suggestions=_build_block(
            pair.producer_id,
            pair.consumer_id,
            [i.producer_suggestion for i in instructions],
        ),
        consumer_suggestions=_build_block(
            pair.consumer_id,
            pair.producer_id,
            [i.consumer_suggestion for i in instructions],
        ),
    )


def _build_block(schema_id: str, counterpart_id: str, instructions: list[str]) -> str:
    """Assemble a numbered fix prompt block for one side of a pair."""
    class_name = schema_id.rsplit("/", 1)[1]
    header = (
        f"In `{class_name}`, make the following changes to satisfy the contract"
        f" with {counterpart_id}:"
    )
    numbered = "\n".join(f"{i}. {instr}" for i, instr in enumerate(instructions, 1))
    return f"{header}\n\n{numbered}"


def _instruction_for(violation: Violation) -> FixSuggestion | None:
    """Map a single CRITICAL violation to a ``FixSuggestion``."""
    path = violation.field_path
    producer = violation.producer
    consumer = violation.consumer

    match violation.rule:
        case "TYPE_MISMATCH":
            return FixSuggestion(
                producer_suggestion=(
                    f"Change the type of field '{path}'"
                    f" from '{producer['type']}' to '{consumer['type']}'."
                ),
                consumer_suggestion=(
                    f"Change the type of field '{path}'"
                    f" from '{consumer['type']}' to '{producer['type']}'."
                ),
            )
        case "MISSING_FIELD":
            return FixSuggestion(
                producer_suggestion=f"Add '{path}' as a required field.",
                consumer_suggestion=(
                    f"Add a 'load_default' to field '{path}', or mark it as not required."
                ),
            )
        case "REQUIREMENT_MISMATCH":
            return FixSuggestion(
                producer_suggestion=f"Mark field '{path}' as required.",
                consumer_suggestion=(
                    f"Add a 'load_default' to field '{path}', or mark it as not required."
                ),
            )
        case "NULLABILITY_MISMATCH":
            return FixSuggestion(
                producer_suggestion=f"Remove the nullable constraint from field '{path}'.",
                consumer_suggestion=f"Mark field '{path}' as nullable.",
            )
        case "DIRECTION_MISMATCH":
            return FixSuggestion(
                producer_suggestion=(
                    f"Remove the load-only constraint from field '{path}'"
                    " so it is included in serialised output."
                ),
                consumer_suggestion=(
                    f"Mark field '{path}' as dump-only,"
                    " or remove the expectation of receiving it from the producer."
                ),
            )
        case "STRUCTURE_MISMATCH":
            return FixSuggestion(
                producer_suggestion=(
                    f"Replace the open map for field '{path}' with a fixed-schema nested object."
                ),
                consumer_suggestion=(
                    f"Replace the fixed-schema nested object for field '{path}' with an open map."
                ),
            )
        case "UNDECLARED_FIELD":
            return FixSuggestion(
                producer_suggestion=(
                    f"Remove field '{path}' from your schema,"
                    " or rename it to match a field declared in the consumer."
                ),
                consumer_suggestion=(
                    f"Declare field '{path}' in your schema,"
                    " or change the unknown field policy from 'forbid' to 'ignore' or 'allow'."
                ),
            )
        case "METADATA_ALLOWED_VALUES_MISMATCH":
            if producer.get("allowed_values") is None:
                producer_instruction = (
                    f"Add an allowed-values constraint to field '{path}'"
                    f" whose values are a subset of {consumer['allowed_values']}."
                )
            else:
                producer_instruction = (
                    f"Restrict the allowed values for field '{path}'"
                    f" to {consumer['allowed_values']}."
                )
            return FixSuggestion(
                producer_suggestion=producer_instruction,
                consumer_suggestion=(
                    f"Expand the allowed values for field '{path}'"
                    f" to include {producer['allowed_values']}."
                ),
            )
        case "METADATA_RANGE_MISMATCH":
            return FixSuggestion(
                producer_suggestion=(
                    f"Tighten the range constraint on field '{path}'"
                    f" to match the consumer: {consumer['range']}."
                ),
                consumer_suggestion=(
                    f"Widen the range constraint on field '{path}'"
                    f" to accept the producer's range: {producer['range']}."
                ),
            )
        case "METADATA_LENGTH_MISMATCH":
            return FixSuggestion(
                producer_suggestion=(
                    f"Tighten the length constraint on field '{path}'"
                    f" to match the consumer: {consumer['length']}."
                ),
                consumer_suggestion=(
                    f"Widen the length constraint on field '{path}'"
                    f" to accept the producer's length: {producer['length']}."
                ),
            )
        case "METADATA_KEY_MISMATCH":
            # Each dict carries exactly one key — the metadata attribute name.
            key = next(iter(consumer))
            return FixSuggestion(
                producer_suggestion=(
                    f"Change metadata '{key}' on field '{path}' to '{consumer[key]}'."
                ),
                consumer_suggestion=(
                    f"Change metadata '{key}' on field '{path}' to '{producer[key]}'."
                ),
            )
        case _:
            # Non-actionable rules (e.g. COUNTERPART_MISMATCH) produce no fix.
            return None
