from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class TypeMismatchRule(Rule):
    """Fails when producer and consumer declare a different type for the same field."""

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        if producer.type == consumer.type:
            return []

        field_path = producer.name
        return [
            Violation(
                rule=RuleName.TYPE_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"type": producer.type},
                consumer={"type": consumer.type},
                message=(
                    f"Field '{field_path}' is a '{producer.type}' in Producer"
                    f" but Consumer expects a '{consumer.type}'."
                ),
            )
        ]
