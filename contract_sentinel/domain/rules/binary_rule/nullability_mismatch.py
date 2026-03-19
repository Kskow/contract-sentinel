from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class NullabilityMismatchRule(BinaryRule):
    """Fails when the producer allows null but the consumer does not."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if not (producer.is_nullable is True and consumer.is_nullable is False):
            return []

        field_path = producer.name
        return [
            Violation(
                rule="NULLABILITY_MISMATCH",
                severity="CRITICAL",
                field_path=field_path,
                producer={"is_nullable": producer.is_nullable},
                consumer={"is_nullable": consumer.is_nullable},
                message=(
                    f"Field '{field_path}' allows null in Producer but Consumer expects a value."
                ),
            )
        ]
