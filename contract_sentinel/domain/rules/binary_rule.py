from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import MISSING

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


def _type_label(type_: str, format_: str | None) -> str:
    """Human-readable type string that includes format when present."""
    return f"{type_} ({format_})" if format_ is not None else type_


class BinaryRule(ABC):
    """Both fields are present — type, nullability, requirement, and metadata checks."""

    @abstractmethod
    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]: ...


class TypeMismatchRule(BinaryRule):
    """Fails when producer and consumer declare a different type or format for the same field."""

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if producer.type == consumer.type and producer.format == consumer.format:
            return []

        field_path = producer.name
        producer_payload: dict[str, Any] = {"type": producer.type}
        consumer_payload: dict[str, Any] = {"type": consumer.type}
        if producer.format is not None:
            producer_payload["format"] = producer.format
        if consumer.format is not None:
            consumer_payload["format"] = consumer.format

        producer_label = _type_label(producer.type, producer.format)
        consumer_label = _type_label(consumer.type, consumer.format)
        return [
            Violation(
                rule="TYPE_MISMATCH",
                severity="CRITICAL",
                field_path=field_path,
                producer=producer_payload,
                consumer=consumer_payload,
                message=(
                    f"Field '{field_path}' is a '{producer_label}' in Producer"
                    f" but Consumer expects a '{consumer_label}'."
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


class EnumValuesMismatchRule(BinaryRule):
    """Fails when the producer can emit an enum value the consumer does not accept.

    The breaking direction: producer values must be a subset of consumer values.
    If the producer sends a value the consumer's schema doesn't recognise, the
    consumer will reject the message.  The inverse (consumer handles values
    the producer never sends) is harmless and passes silently.

    The check is skipped when either side has no ``values`` list — the field
    may not be an enum, or the parser didn't capture values.
    """

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if producer.values is None or consumer.values is None:
            return []

        unexpected = sorted(set(producer.values) - set(consumer.values))
        if not unexpected:
            return []

        field_path = producer.name
        return [
            Violation(
                rule="ENUM_VALUES_MISMATCH",
                severity="CRITICAL",
                field_path=field_path,
                producer={"values": producer.values},
                consumer={"values": consumer.values},
                message=(
                    f"Field '{field_path}' producer can emit {unexpected!r}"
                    f" but Consumer does not accept those values."
                ),
            )
        ]
