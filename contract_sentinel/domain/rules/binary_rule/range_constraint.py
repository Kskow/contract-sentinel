from __future__ import annotations

from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


class RangeConstraintRule(BinaryRule):
    """Fails when the producer's numeric range is wider than the consumer's.

    Reads ``metadata["range"]`` — populated for fields with ``validate.Range``.

    Direction matters: a producer that can emit values outside the consumer's
    accepted range is always breaking; a consumer that accepts a wider range
    than the producer emits is safe and passes silently.

    Boundary inclusivity is respected: if producer emits a boundary value
    (``min_inclusive=True``) that the consumer rejects (``min_inclusive=False``),
    that is a violation even when the numeric bounds are identical.

    Skipped entirely when the consumer declares no range constraint.
    ``MetadataMismatchRule`` skips the ``"range"`` key to avoid double-reporting.
    """

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        c_range: dict[str, Any] | None = (consumer.metadata or {}).get("range")
        if c_range is None:
            return []

        p_range: dict[str, Any] | None = (producer.metadata or {}).get("range")
        field_path = producer.name

        if p_range is None:
            return [
                Violation(
                    rule="RANGE_CONSTRAINT_MISMATCH",
                    severity="CRITICAL",
                    field_path=field_path,
                    producer={"range": None},
                    consumer={"range": c_range},
                    message=(
                        f"Field '{field_path}' has no range constraint in Producer"
                        " but Consumer enforces one"
                        " — Producer may emit values Consumer will reject."
                    ),
                )
            ]

        violations: list[Violation] = []

        # --- minimum bound ---
        c_min = c_range.get("min")
        if c_min is not None:
            p_min = p_range.get("min")
            if p_min is None:
                violations.append(
                    Violation(
                        rule="RANGE_CONSTRAINT_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"range": p_range},
                        consumer={"range": c_range},
                        message=(
                            f"Field '{field_path}' Producer has no minimum bound"
                            f" but Consumer requires min={c_min}"
                            f" (inclusive={c_range.get('min_inclusive', True)})"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )
            else:
                p_min_incl: bool = p_range.get("min_inclusive", True)
                c_min_incl: bool = c_range.get("min_inclusive", True)
                if p_min < c_min or (p_min == c_min and p_min_incl and not c_min_incl):
                    violations.append(
                        Violation(
                            rule="RANGE_CONSTRAINT_MISMATCH",
                            severity="CRITICAL",
                            field_path=field_path,
                            producer={"range": p_range},
                            consumer={"range": c_range},
                            message=(
                                f"Field '{field_path}' Producer minimum {p_min}"
                                f" (inclusive={p_min_incl})"
                                f" is below Consumer minimum {c_min}"
                                f" (inclusive={c_min_incl})"
                                " — Producer can emit values Consumer will reject."
                            ),
                        )
                    )

        # --- maximum bound ---
        c_max = c_range.get("max")
        if c_max is not None:
            p_max = p_range.get("max")
            if p_max is None:
                violations.append(
                    Violation(
                        rule="RANGE_CONSTRAINT_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"range": p_range},
                        consumer={"range": c_range},
                        message=(
                            f"Field '{field_path}' Producer has no maximum bound"
                            f" but Consumer requires max={c_max}"
                            f" (inclusive={c_range.get('max_inclusive', True)})"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )
            else:
                p_max_incl: bool = p_range.get("max_inclusive", True)
                c_max_incl: bool = c_range.get("max_inclusive", True)
                if p_max > c_max or (p_max == c_max and p_max_incl and not c_max_incl):
                    violations.append(
                        Violation(
                            rule="RANGE_CONSTRAINT_MISMATCH",
                            severity="CRITICAL",
                            field_path=field_path,
                            producer={"range": p_range},
                            consumer={"range": c_range},
                            message=(
                                f"Field '{field_path}' Producer maximum {p_max}"
                                f" (inclusive={p_max_incl})"
                                f" exceeds Consumer maximum {c_max}"
                                f" (inclusive={c_max_incl})"
                                " — Producer can emit values Consumer will reject."
                            ),
                        )
                    )

        return violations
