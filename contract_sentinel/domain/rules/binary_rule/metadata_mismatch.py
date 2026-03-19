from __future__ import annotations

from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class MetadataMismatchRule(BinaryRule):
    """Fails for each metadata key declared by the consumer that differs from the producer.

    Skips ``allowed_values`` — that key carries directional subset semantics handled
    exclusively by EnumValuesMismatchRule to avoid double-reporting.
    All other keys use simple equality: any difference is flagged as a mismatch.
    """

    # Keys handled by dedicated directional rules — skipped here to avoid double-reporting.
    _SKIP_KEYS: frozenset[str] = frozenset({"allowed_values", "range", "length"})

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if consumer.metadata is None:
            return []

        violations: list[Violation] = []
        field_path = producer.name

        for key, consumer_value in consumer.metadata.items():
            if key in self._SKIP_KEYS:
                continue

            producer_value: Any = (
                producer.metadata.get(key) if producer.metadata is not None else None
            )

            if producer_value != consumer_value:
                violations.append(
                    Violation(
                        rule="METADATA_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={key: producer_value},
                        consumer={key: consumer_value},
                        message=(
                            f"Field '{field_path}' has mismatched metadata '{key}':"
                            f" Producer has '{producer_value}',"
                            f" Consumer expects '{consumer_value}'."
                        ),
                    )
                )

        return violations
