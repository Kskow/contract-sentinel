from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class RequirementMismatchRule(Rule):
    """Fails when a field is optional in the producer but required (no default) in the consumer."""

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        consumer_has_default = "load_default" in (consumer.metadata or {})
        if not (
            producer.is_required is False
            and consumer.is_required is True
            and not consumer_has_default
        ):
            return []

        field_path = producer.name
        return [
            Violation(
                rule=RuleName.REQUIREMENT_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"is_required": producer.is_required},
                consumer={"is_required": consumer.is_required},
                message=f"Field '{field_path}' is optional in Producer but required in Consumer.",
            )
        ]

    def suggest_fix(self, violation: Violation) -> FixSuggestion | None:
        path = violation.field_path
        return FixSuggestion(
            producer_suggestion=f"Mark field '{path}' as required.",
            consumer_suggestion=(
                f"Add a 'load_default' to field '{path}', or mark it as not required."
            ),
        )
