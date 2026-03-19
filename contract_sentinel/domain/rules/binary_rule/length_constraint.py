from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


def _length_effective_min(d: dict[str, int]) -> int | None:
    """Effective minimum length from a ``metadata["length"]`` dict.

    ``equal`` is treated as both the minimum and maximum — a field constrained
    to exactly N characters has an effective min of N.
    """
    if "equal" in d:
        return d["equal"]
    return d.get("min")


def _length_effective_max(d: dict[str, int]) -> int | None:
    """Effective maximum length from a ``metadata["length"]`` dict."""
    if "equal" in d:
        return d["equal"]
    return d.get("max")


class LengthConstraintRule(BinaryRule):
    """Fails when the producer's string/array length range is wider than the consumer's.

    Reads ``metadata["length"]`` — populated for fields with ``validate.Length``.
    Supports both range-style constraints (``min`` / ``max``) and exact-length
    constraints (``equal``).  ``equal`` is expanded to an effective min and max of
    the same value before comparison so mixed styles are handled uniformly.

    Skipped entirely when the consumer declares no length constraint.
    ``MetadataMismatchRule`` skips the ``"length"`` key to avoid double-reporting.
    """

    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        c_length: dict[str, int] | None = (consumer.metadata or {}).get("length")
        if c_length is None:
            return []

        p_length: dict[str, int] | None = (producer.metadata or {}).get("length")
        field_path = producer.name

        if p_length is None:
            return [
                Violation(
                    rule="LENGTH_CONSTRAINT_MISMATCH",
                    severity="CRITICAL",
                    field_path=field_path,
                    producer={"length": None},
                    consumer={"length": c_length},
                    message=(
                        f"Field '{field_path}' has no length constraint in Producer"
                        " but Consumer enforces one"
                        " — Producer may emit values Consumer will reject."
                    ),
                )
            ]

        p_min = _length_effective_min(p_length)
        p_max = _length_effective_max(p_length)
        c_min = _length_effective_min(c_length)
        c_max = _length_effective_max(c_length)

        violations: list[Violation] = []

        # --- minimum bound ---
        if c_min is not None:
            if p_min is None:
                violations.append(
                    Violation(
                        rule="LENGTH_CONSTRAINT_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"length": p_length},
                        consumer={"length": c_length},
                        message=(
                            f"Field '{field_path}' Producer has no minimum length"
                            f" but Consumer requires at least {c_min}"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )
            elif p_min < c_min:
                violations.append(
                    Violation(
                        rule="LENGTH_CONSTRAINT_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"length": p_length},
                        consumer={"length": c_length},
                        message=(
                            f"Field '{field_path}' Producer minimum length {p_min}"
                            f" is below Consumer minimum length {c_min}"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )

        # --- maximum bound ---
        if c_max is not None:
            if p_max is None:
                violations.append(
                    Violation(
                        rule="LENGTH_CONSTRAINT_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"length": p_length},
                        consumer={"length": c_length},
                        message=(
                            f"Field '{field_path}' Producer has no maximum length"
                            f" but Consumer allows at most {c_max}"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )
            elif p_max > c_max:
                violations.append(
                    Violation(
                        rule="LENGTH_CONSTRAINT_MISMATCH",
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"length": p_length},
                        consumer={"length": c_length},
                        message=(
                            f"Field '{field_path}' Producer maximum length {p_max}"
                            f" exceeds Consumer maximum length {c_max}"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )

        return violations
