from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class RequirementMismatchRule(BinaryRule):
    """Fails when a field is optional in the producer but required (no default) in the consumer."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
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
                rule="REQUIREMENT_MISMATCH",
                severity="CRITICAL",
                field_path=field_path,
                producer={"is_required": producer.is_required},
                consumer={"is_required": consumer.is_required},
                message=f"Field '{field_path}' is optional in Producer but required in Consumer.",
            )
        ]
