from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractSchema


class CounterpartMismatchRule:
    """Rule that checks if a topic/version group has both producers and consumers."""

    def check(
        self,
        producers: list[ContractSchema],
        consumers: list[ContractSchema],
    ) -> list[Violation]:
        violations: list[Violation] = []

        if not producers and consumers:
            first = consumers[0]
            violations.append(
                Violation(
                    rule="COUNTERPART_MISMATCH",
                    severity="WARNING",
                    field_path="",
                    producer={},
                    consumer={},
                    message=(
                        f"Topic '{first.topic}' version '{first.version}' has "
                        f"{len(consumers)} consumer(s) but no matching producer."
                    ),
                )
            )
            return violations

        if not consumers and producers:
            first = producers[0]
            violations.append(
                Violation(
                    rule="COUNTERPART_MISMATCH",
                    severity="WARNING",
                    field_path="",
                    producer={},
                    consumer={},
                    message=(
                        f"Topic '{first.topic}' version '{first.version}' has "
                        f"{len(producers)} producer(s) but no matching consumer."
                    ),
                )
            )
            return violations

        return violations
