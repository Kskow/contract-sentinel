from __future__ import annotations

from abc import ABC, abstractmethod

from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField, UnknownFieldBehaviour


class ProducerOnlyRule(ABC):
    """Producer has the field, consumer doesn't — undeclared field checks."""

    @abstractmethod
    def check(self, producer: ContractField) -> list[Violation]: ...


class UndeclaredFieldRule(ProducerOnlyRule):
    """Fails when the producer sends a field the consumer has not declared and forbids unknowns."""

    def __init__(self, consumer_unknown: UnknownFieldBehaviour) -> None:
        self._consumer_unknown = consumer_unknown

    def check(self, producer: ContractField) -> list[Violation]:
        if self._consumer_unknown != UnknownFieldBehaviour.FORBID:
            return []

        field_path = producer.name
        return [
            Violation(
                rule="UNDECLARED_FIELD",
                severity="CRITICAL",
                field_path=field_path,
                producer={"exists": True},
                consumer={"exists": False, "unknown": self._consumer_unknown.value},
                message=(
                    f"Field '{field_path}' is sent by Producer but is not declared"
                    " in Consumer (unknown=forbid)."
                ),
            )
        ]
