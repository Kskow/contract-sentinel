from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class ConsumerOnlyRule(ABC):
    """Consumer expects the field, producer doesn't — missing field checks."""

    @abstractmethod
    def check(self, consumer: ContractField) -> list[Violation]: ...


class MissingFieldRule(ConsumerOnlyRule):
    """Fails when a field is absent from the producer but required (no default) in the consumer."""

    def check(self, consumer: ContractField) -> list[Violation]:
        consumer_has_default = "load_default" in (consumer.metadata or {})
        if not (consumer.is_required is True and not consumer_has_default):
            return []

        field_path = consumer.name
        return [
            Violation(
                rule="MISSING_FIELD",
                severity="CRITICAL",
                field_path=field_path,
                producer={"exists": False},
                consumer={"is_required": consumer.is_required},
                message=f"Field '{field_path}' is missing in Producer but required in Consumer.",
            )
        ]
