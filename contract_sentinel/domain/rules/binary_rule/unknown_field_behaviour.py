from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import UnknownFieldBehaviour

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField

# Higher value = more permissive (producer can emit more than consumer accepts).
_UNKNOWN_PERMISSIVENESS: dict[UnknownFieldBehaviour, int] = {
    UnknownFieldBehaviour.FORBID: 0,
    UnknownFieldBehaviour.IGNORE: 1,
    UnknownFieldBehaviour.ALLOW: 2,
}


class UnknownFieldBehaviourRule(BinaryRule):
    """Fails when the producer's nested-object unknown-field policy is more permissive
    than the consumer's.

    Only applies to fields that carry an ``unknown`` policy (i.e. nested ``object``
    fields).  If the producer schema allows or ignores unknown fields it may emit
    extra keys that the consumer's stricter policy would reject.

    Permissiveness order (ascending): FORBID < IGNORE < ALLOW.

    Safe direction: consumer is *more* permissive than producer (consumer accepts
    everything the producer can send).  Breaking direction: producer is *more*
    permissive — it may emit fields the consumer cannot handle.
    """

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if producer.unknown is None or consumer.unknown is None:
            return []

        if _UNKNOWN_PERMISSIVENESS[producer.unknown] <= _UNKNOWN_PERMISSIVENESS[consumer.unknown]:
            return []

        field_path = producer.name
        return [
            Violation(
                rule="UNKNOWN_FIELD_BEHAVIOUR_MISMATCH",
                severity="CRITICAL",
                field_path=field_path,
                producer={"unknown": producer.unknown.value},
                consumer={"unknown": consumer.unknown.value},
                message=(
                    f"Field '{field_path}' nested schema allows unknown fields"
                    f" ('{producer.unknown}') in Producer"
                    f" but Consumer restricts them ('{consumer.unknown}'):"
                    " extra fields the Producer emits may be rejected."
                ),
            )
        ]
