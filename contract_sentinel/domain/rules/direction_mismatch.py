from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class DirectionMismatchRule(Rule):
    """Fails when a field is load-only in the producer but the consumer expects to receive it.

    A ``load_only`` producer field is excluded from serialised output — the producer
    schema uses it only when *deserialising* incoming data (e.g. a write-only API
    input field).  If the consumer schema expects to receive that field as part of
    the producer's message, it will never arrive, breaking the consumer.

    The rule is skipped when the consumer marks the same field as ``dump_only``
    (consumer only *sends* it, never reads it from the producer), because in that
    case the consumer has no expectation of receiving the field either.
    """

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        if not (producer.is_load_only and not consumer.is_dump_only):
            return []

        field_path = producer.name
        return [
            Violation(
                rule=RuleName.DIRECTION_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"is_load_only": True},
                consumer={"is_dump_only": consumer.is_dump_only},
                message=(
                    f"Field '{field_path}' is load-only in Producer"
                    " (never included in serialised output)"
                    " but Consumer schema expects to receive it."
                ),
            )
        ]

    def suggest_fix(self, violation: Violation) -> FixSuggestion | None:
        path = violation.field_path
        return FixSuggestion(
            producer_suggestion=(
                f"Ensure field '{path}' is included in serialised output"
                " (remove any output-exclusion flag)."
            ),
            consumer_suggestion=(
                f"Mark field '{path}' as input-only,"
                " or remove the expectation of receiving it from the producer."
            ),
        )
