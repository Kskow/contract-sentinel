from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any

from contract_sentinel.domain.schema import MISSING, ContractField, UnknownFieldBehaviour


@dataclasses.dataclass
class Violation:
    rule: str
    severity: str
    field_path: str
    producer: dict[str, Any]
    consumer: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "field_path": self.field_path,
            "producer": self.producer,
            "consumer": self.consumer,
            "message": self.message,
        }


class BinaryRule(ABC):
    """Both fields are present — type, nullability, requirement, and metadata checks."""

    @abstractmethod
    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]: ...


class ProducerOnlyRule(ABC):
    """Producer has the field, consumer doesn't — undeclared field checks."""

    @abstractmethod
    def check(self, producer: ContractField) -> list[Violation]: ...


class ConsumerOnlyRule(ABC):
    """Consumer expects the field, producer doesn't — missing field checks."""

    @abstractmethod
    def check(self, consumer: ContractField) -> list[Violation]: ...


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


class MissingFieldRule(ConsumerOnlyRule):
    """Fails when a field is absent from the producer but required (no default) in the consumer."""

    def check(self, consumer: ContractField) -> list[Violation]:
        if not (consumer.is_required is True and consumer.default is MISSING):
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


class MetadataMismatchRule(BinaryRule):
    """Fails for each metadata key declared by the consumer that differs from the producer."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if consumer.metadata is None:
            return []

        violations: list[Violation] = []
        field_path = producer.name
        for key in consumer.metadata:
            producer_value = producer.metadata.get(key) if producer.metadata is not None else None

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
