from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField

# Types for which fields carries structural meaning — only these can exhibit an
# open-map vs fixed-schema mismatch.
_STRUCTURAL_TYPES: frozenset[str] = frozenset({"object", "array"})


class StructureMismatchRule(Rule):
    """Fails when the producer is an open map but the consumer expects a fixed schema.

    Covers two concrete cases:
    - ``fields.Dict()`` (producer) vs ``fields.Nested(...)`` (consumer) — both resolve to
      ``type="object"`` but only the Nested side carries declared sub-fields.
    - ``fields.List(fields.Dict())`` (producer) vs ``fields.List(fields.Nested(...))``
      (consumer) — same asymmetry at ``type="array"``.

    The inverse (Nested producer, Dict consumer) is intentionally NOT a violation:
    the consumer imposes no sub-field expectations, so the producer trivially satisfies them.
    """

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        if producer.type != consumer.type:
            # TypeMismatchRule already covers this; no double-reporting.
            return []
        if producer.type not in _STRUCTURAL_TYPES:
            return []
        if producer.fields is not None or consumer.fields is None:
            # Either both have sub-fields (handled by recursion), or only the producer
            # has them (compatible — consumer is the open map), or neither does.
            return []

        field_path = producer.name
        return [
            Violation(
                rule=RuleName.STRUCTURE_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"structure": "open_map"},
                consumer={"structure": "fixed_schema"},
                message=(
                    f"Field '{field_path}' is an open map in Producer"
                    f" but Consumer expects a fixed-schema object."
                ),
            )
        ]

    def suggest_fix(self, violation: Violation) -> FixSuggestion | None:
        path = violation.field_path
        return FixSuggestion(
            producer_suggestion=(
                f"Replace the open map for field '{path}' with a fixed-schema nested object."
            ),
            consumer_suggestion=(
                f"Replace the fixed-schema nested object for field '{path}' with an open map."
            ),
        )
