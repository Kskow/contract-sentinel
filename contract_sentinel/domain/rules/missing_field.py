from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class MissingFieldRule(Rule):
    """Fails when a field is absent from the producer but required (no default) in the consumer.

    Fires only when ``producer is None`` — meaning the field exists in the consumer
    schema but was not declared by the producer at all.  Fields that carry a
    ``load_default`` in their metadata are optional at runtime and are therefore safe.
    """

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is not None or consumer is None:
            return []
        consumer_has_default = "load_default" in (consumer.metadata or {})
        if not (consumer.is_required is True and not consumer_has_default):
            return []

        field_path = consumer.name
        return [
            Violation(
                rule=RuleName.MISSING_FIELD,
                severity="CRITICAL",
                field_path=field_path,
                producer={"exists": False},
                consumer={"is_required": consumer.is_required},
                message=f"Field '{field_path}' is missing in Producer but required in Consumer.",
            )
        ]

    def suggest_fix(self, violation: Violation) -> FixSuggestion | None:
        path = violation.field_path
        return FixSuggestion(
            producer_suggestion=f"Add '{path}' as a required field.",
            consumer_suggestion=(
                f"Add a 'load_default' to field '{path}', or mark it as not required."
            ),
        )
