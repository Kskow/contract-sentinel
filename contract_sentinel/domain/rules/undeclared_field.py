from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import UnknownFieldBehaviour

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class UndeclaredFieldRule:
    """Fails when the producer sends a field the consumer has not declared and forbids unknowns.

    Intentionally does **not** extend ``Rule`` — its second argument is not a peer field but
    the consumer container's unknown policy, which is a fundamentally different concept.
    Keeping it separate makes the call site honest: callers pass ``consumer.unknown`` directly
    rather than wrapping it in a synthetic ``ContractField``.

    ``FORBID`` → violation (consumer will reject the field).
    ``IGNORE`` / ``ALLOW`` / ``None`` → passes silently.
    """

    def check(
        self, producer: ContractField | None, unknown: UnknownFieldBehaviour | None
    ) -> list[Violation]:
        if producer is None:
            return []
        if unknown != UnknownFieldBehaviour.FORBID:
            return []

        field_path = producer.name
        return [
            Violation(
                rule="UNDECLARED_FIELD",
                severity="CRITICAL",
                field_path=field_path,
                producer={"exists": True},
                consumer={"exists": False, "unknown": unknown.value},
                message=(
                    f"Field '{field_path}' is sent by Producer but is not declared"
                    " in Consumer (unknown=forbid)."
                ),
            )
        ]
