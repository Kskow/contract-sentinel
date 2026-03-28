from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion, FixSuggestionsReport, TopicFixSuggestions
from contract_sentinel.domain.rules.direction_mismatch import DirectionMismatchRule
from contract_sentinel.domain.rules.metadata_mismatch import MetadataMismatchRule
from contract_sentinel.domain.rules.missing_field import MissingFieldRule
from contract_sentinel.domain.rules.nullability_mismatch import NullabilityMismatchRule
from contract_sentinel.domain.rules.requirement_mismatch import RequirementMismatchRule
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.structure_mismatch import StructureMismatchRule
from contract_sentinel.domain.rules.type_mismatch import TypeMismatchRule
from contract_sentinel.domain.rules.undeclared_field import UndeclaredFieldRule

if TYPE_CHECKING:
    from contract_sentinel.domain.report import ContractReport, PairViolations, ValidationReport
    from contract_sentinel.domain.rules.violation import Violation


RULE_REGISTRY: dict[RuleName, Rule | UndeclaredFieldRule] = {
    RuleName.TYPE_MISMATCH: TypeMismatchRule(),
    RuleName.MISSING_FIELD: MissingFieldRule(),
    RuleName.REQUIREMENT_MISMATCH: RequirementMismatchRule(),
    RuleName.NULLABILITY_MISMATCH: NullabilityMismatchRule(),
    RuleName.DIRECTION_MISMATCH: DirectionMismatchRule(),
    RuleName.STRUCTURE_MISMATCH: StructureMismatchRule(),
    RuleName.UNDECLARED_FIELD: UndeclaredFieldRule(),
    RuleName.METADATA_ALLOWED_VALUES_MISMATCH: MetadataMismatchRule(),
    RuleName.METADATA_RANGE_MISMATCH: MetadataMismatchRule(),
    RuleName.METADATA_LENGTH_MISMATCH: MetadataMismatchRule(),
    RuleName.METADATA_KEY_MISMATCH: MetadataMismatchRule(),
}


@dataclasses.dataclass
class PairFixSuggestion:
    """Pre-rendered fix blocks for one producer/consumer pair."""

    producer_id: str
    consumer_id: str
    producer_suggestions: str
    consumer_suggestions: str


def generate_fix_suggestions(
    validation_report: ValidationReport,
) -> FixSuggestionsReport:
    """Transform a full validation report into a sparse FixSuggestionsReport."""
    suggestions: list[TopicFixSuggestions] = []
    for contract_report in validation_report.contracts:
        fix_report = _suggest_contract_fixes(contract_report)
        if fix_report is not None:
            suggestions.append(fix_report)
    return FixSuggestionsReport(suggestions=suggestions)


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
        producer_suggestions=_build_block([i.producer_suggestion for i in instructions]),
        consumer_suggestions=_build_block([i.consumer_suggestion for i in instructions]),
    )


def _build_block(instructions: list[str]) -> str:
    """Assemble a numbered fix prompt block for one side of a pair."""
    return "\n".join(f"{i}. {instr}" for i, instr in enumerate(instructions, 1))


def _instruction_for(violation: Violation) -> FixSuggestion | None:
    """Delegate to the rule instance responsible for this violation."""
    rule = RULE_REGISTRY.get(violation.rule)
    return rule.suggest_fix(violation) if rule else None
