from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.violation import Violation
    from contract_sentinel.domain.schema import ContractField


class NestedFieldRule(BinaryRule):
    """Recursively applies binary rules to sub-fields of object / array-of-object fields.

    Only fires when both the producer and consumer field carry a ``fields`` list
    (i.e. they are ``object`` or ``array`` of objects, not primitive arrays).
    Fields present in only one side are intentionally ignored here — missing or
    undeclared nested fields are the responsibility of the consumer-only /
    producer-only rule passes.

    To support arbitrary depth, append this instance to the same list you inject:

        rules: list[BinaryRule] = [TypeMismatchRule(), ...]
        nested = NestedFieldRule(rules)
        rules.append(nested)   # NestedFieldRule now sees itself → deep recursion works

    Path prefixing: violations from sub-fields are rewritten from ``"street"``
    to ``"address.street"`` so callers always see the full dot-separated path.
    """

    def __init__(self, rules: list[BinaryRule]) -> None:
        # Holds a reference to the shared mutable list; appending to it after
        # construction (e.g. to add this instance itself) is visible here.
        self._rules = rules

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        if producer.fields is None or consumer.fields is None:
            return []

        # Skip if the types themselves differ — TypeMismatchRule fires for that.
        if producer.type != consumer.type:
            return []

        producer_map = {f.name: f for f in producer.fields}
        consumer_map = {f.name: f for f in consumer.fields}
        prefix = producer.name

        violations: list[Violation] = []
        for name, c_field in consumer_map.items():
            if name not in producer_map:
                # Missing nested field → left to ConsumerOnlyRule at that level.
                continue
            p_field = producer_map[name]
            for rule in self._rules:
                for v in rule.check(p_field, c_field):
                    violations.append(_with_path_prefix(v, prefix))

        return violations


def _with_path_prefix(violation: Violation, prefix: str) -> Violation:
    """Clone a Violation with its field_path (and message) prefixed by a parent field name."""
    new_path = f"{prefix}.{violation.field_path}"
    new_message = violation.message.replace(f"'{violation.field_path}'", f"'{new_path}'", 1)
    return dataclasses.replace(violation, field_path=new_path, message=new_message)
