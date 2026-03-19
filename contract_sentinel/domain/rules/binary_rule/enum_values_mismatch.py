from __future__ import annotations

from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class EnumValuesMismatchRule(BinaryRule):
    """Fails when the producer can emit a value the consumer does not accept.

    Reads ``metadata["allowed_values"]`` — populated for both Marshmallow ``Enum``
    fields and ``OneOf`` validators.  The check is directional: the producer's value
    set must be a *subset* of the consumer's.  A consumer that accepts more values
    than the producer ever emits is harmless and passes silently.

    If either side has no ``allowed_values`` entry, the rule is skipped — the field
    is either unconstrained or the constraint is not statically introspectable.
    """

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        producer_values: list[Any] | None = (
            producer.metadata.get("allowed_values") if producer.metadata else None
        )
        consumer_values: list[Any] | None = (
            consumer.metadata.get("allowed_values") if consumer.metadata else None
        )

        if producer_values is None or consumer_values is None:
            return []

        unexpected = sorted(set(producer_values) - set(consumer_values), key=str)
        if not unexpected:
            return []

        field_path = producer.name
        return [
            Violation(
                rule="ENUM_VALUES_MISMATCH",
                severity="CRITICAL",
                field_path=field_path,
                producer={"allowed_values": producer_values},
                consumer={"allowed_values": consumer_values},
                message=(
                    f"Field '{field_path}' producer can emit {unexpected!r}"
                    " but Consumer does not accept those values."
                ),
            )
        ]
