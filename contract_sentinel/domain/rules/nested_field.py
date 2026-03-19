from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.rule import Rule
from contract_sentinel.domain.rules.undeclared_field import UndeclaredFieldRule

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.violation import Violation
    from contract_sentinel.domain.schema import ContractField

# Module-level singleton — no per-instance state needed.
_undeclared = UndeclaredFieldRule()


class NestedFieldRule(Rule):
    """Recursively applies rules to sub-fields of object / array-of-object fields.

    Only fires when both the producer and consumer field carry a ``fields`` list
    (i.e. they are ``object`` or ``array`` of objects, not primitive arrays).

    **Unified loop** iterates over all field names present in either side:
    producer-only fields pass ``(p_field, None)`` so rules like ``MissingFieldRule``
    can ignore them while ``UndeclaredFieldRule`` fires if the consumer forbids unknowns.
    Consumer-only fields pass ``(None, c_field)`` so ``MissingFieldRule`` can fire.

    ``UndeclaredFieldRule`` is special — it needs the parent consumer object (to read
    ``consumer.unknown``) rather than a matched consumer field.  It runs in a dedicated
    pass for producer-only fields, receiving ``(p_field, parent_consumer)``.

    To support arbitrary depth, append this instance to the same list you inject:

        rules: list[Rule] = [TypeMismatchRule(), MissingFieldRule(), ...]
        nested = NestedFieldRule(rules)
        rules.append(nested)   # NestedFieldRule now sees itself → deep recursion works

    Path prefixing: violations from sub-fields are rewritten from ``"street"``
    to ``"address.street"`` so callers always see the full dot-separated path.
    """

    def __init__(self, rules: list[Rule]) -> None:
        # Holds a reference to the shared mutable list; appending to it after
        # construction (e.g. to add this instance itself) is visible here.
        self._rules = rules

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        if producer.fields is None or consumer.fields is None:
            return []

        # Skip if the types themselves differ — TypeMismatchRule fires for that.
        if producer.type != consumer.type:
            return []

        producer_map = {f.name: f for f in producer.fields}
        consumer_map = {f.name: f for f in consumer.fields}
        prefix = producer.name

        violations: list[Violation] = []

        # Unified pass: matched fields get both sides; consumer-only get (None, c_field).
        all_names = list(producer_map) + [k for k in consumer_map if k not in producer_map]
        for name in all_names:
            p_field = producer_map.get(name)
            c_field = consumer_map.get(name)
            for rule in self._rules:
                for v in rule.check(p_field, c_field):
                    violations.append(_with_path_prefix(v, prefix))

        # UndeclaredFieldRule needs the parent consumer object, not a matched field.
        for name, p_field in producer_map.items():
            if name not in consumer_map:
                for v in _undeclared.check(p_field, consumer):
                    violations.append(_with_path_prefix(v, prefix))

        return violations


def _with_path_prefix(violation: Violation, prefix: str) -> Violation:
    """Clone a Violation with its field_path (and message) prefixed by a parent field name."""
    new_path = f"{prefix}.{violation.field_path}"
    new_message = violation.message.replace(f"'{violation.field_path}'", f"'{new_path}'", 1)
    return dataclasses.replace(violation, field_path=new_path, message=new_message)
