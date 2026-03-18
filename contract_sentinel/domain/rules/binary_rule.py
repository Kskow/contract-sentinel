from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import MISSING

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class BinaryRule(ABC):
    """Both fields are present — type, nullability, requirement, and metadata checks."""

    @abstractmethod
    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]: ...


class TypeMismatchRule(BinaryRule):
    """Fails when producer and consumer declare different types for the same field."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if producer.type == consumer.type:
            return []

        field_path = producer.name
        return [
            Violation(
                rule="TYPE_MISMATCH",
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


class RequirementMismatchRule(BinaryRule):
    """Fails when a field is optional in the producer but required (no default) in the consumer."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if not (
            producer.is_required is False
            and consumer.is_required is True
            and consumer.default is MISSING
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


class MetadataMismatchRule(BinaryRule):
    """Fails for each metadata key declared by the consumer that differs from the producer."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if consumer.metadata is None:
            return []

        violations: list[Violation] = []
        field_path = producer.name
        for key in consumer.metadata:
            producer_value: Any = (
                producer.metadata.get(key) if producer.metadata is not None else None
            )

            if producer_value != consumer.metadata[key]:
                violations.append(
                    Violation(
                        rule="METADATA_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={key: producer_value},
                        consumer={key: consumer.metadata[key]},
                        message=(
                            f"Field '{field_path}' has mismatched metadata '{key}':"
                            f" Producer has '{producer_value}',"
                            f" Consumer expects '{consumer.metadata[key]}'."
                        ),
                    )
                )
        return violations
