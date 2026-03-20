from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.counterpart_mismatch import CounterpartMismatchRule
from contract_sentinel.domain.rules.direction_mismatch import DirectionMismatchRule
from contract_sentinel.domain.rules.metadata_mismatch import MetadataMismatchRule
from contract_sentinel.domain.rules.missing_field import MissingFieldRule
from contract_sentinel.domain.rules.nullability_mismatch import NullabilityMismatchRule
from contract_sentinel.domain.rules.requirement_mismatch import RequirementMismatchRule
from contract_sentinel.domain.rules.type_mismatch import TypeMismatchRule
from contract_sentinel.domain.rules.undeclared_field import UndeclaredFieldRule

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.rule import Rule
    from contract_sentinel.domain.rules.violation import Violation
    from contract_sentinel.domain.schema import ContractField, ContractSchema

PAIR_RULES: list[Rule] = [
    TypeMismatchRule(),
    RequirementMismatchRule(),
    NullabilityMismatchRule(),
    MissingFieldRule(),
    MetadataMismatchRule(),
    DirectionMismatchRule(),
]


def validate_group(
    producers: list[ContractSchema],
    consumers: list[ContractSchema],
) -> list[Violation]:
    """Validate a whole group of producers and consumers for one (topic, version) pair.

    Checks if counterparts exist (e.g. at least one producer for consumers).
    If a schema is 'lonely', emits a WARNING violation and skips rest checks.
    Otherwise, runs all validate_pair combinations.
    """

    violations: list[Violation] = []

    # 1. Counterpart check
    if counterpart_violations := CounterpartMismatchRule().check(producers, consumers):
        return counterpart_violations

    # 2. Pairwise check
    for producer in producers:
        for consumer in consumers:
            violations.extend(validate_pair(producer, consumer))

    return violations


def validate_pair(
    producer: ContractSchema | ContractField,
    consumer: ContractSchema | ContractField,
) -> list[Violation]:
    """Run all rules against every field pair in one (producer, consumer) scope.

    Accepts either ``ContractSchema`` (root level) or ``ContractField`` (nested level) —
    both expose ``.fields`` and ``.unknown`` so the algorithm is identical at every depth.

    Three passes are run:

    **Unified pass** — iterates the union of all field names (producer-declaration order
    first, consumer-only names appended). Matched fields receive both sides; consumer-only
    fields receive ``(None, consumer_field)`` so MissingFieldRule can fire.

    **Nested pass** — for matched fields where both sides declare sub-fields of the same
    type, recurses into ``validate_pair`` and prefixes violation paths with the parent
    field name (e.g. ``"street"`` becomes ``"address.street"``).

    **Undeclared pass** — producer-only fields are checked against ``consumer.unknown``
    directly; no synthetic ContractField wrapper needed.
    """
    producer_fields = {field.name: field for field in producer.fields or []}
    consumer_fields = {field.name: field for field in consumer.fields or []}
    violations: list[Violation] = []

    all_field_names = list(producer_fields) + [
        name for name in consumer_fields if name not in producer_fields
    ]
    for field_name in all_field_names:
        producer_field = producer_fields.get(field_name)
        consumer_field = consumer_fields.get(field_name)
        for rule in PAIR_RULES:
            violations.extend(rule.check(producer_field, consumer_field))

        if (
            producer_field is not None
            and consumer_field is not None
            and producer_field.type == consumer_field.type
            and producer_field.fields is not None
            and consumer_field.fields is not None
        ):
            nested = validate_pair(producer_field, consumer_field)
            violations.extend(_with_path_prefix(v, producer_field.name) for v in nested)

    for field_name, producer_field in producer_fields.items():
        if field_name not in consumer_fields:
            violations.extend(UndeclaredFieldRule().check(producer_field, consumer.unknown))

    return violations


def _with_path_prefix(violation: Violation, prefix: str) -> Violation:
    """Clone a Violation with its field_path (and message) prefixed by a parent field name."""
    new_path = f"{prefix}.{violation.field_path}"
    new_message = violation.message.replace(f"'{violation.field_path}'", f"'{new_path}'", 1)
    return dataclasses.replace(violation, field_path=new_path, message=new_message)
