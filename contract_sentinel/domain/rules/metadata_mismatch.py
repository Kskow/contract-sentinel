from __future__ import annotations

from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractField


def _length_effective_min(length_dict: dict[str, int]) -> int | None:
    if "equal" in length_dict:
        return length_dict["equal"]
    return length_dict.get("min")


def _length_effective_max(length_dict: dict[str, int]) -> int | None:
    if "equal" in length_dict:
        return length_dict["equal"]
    return length_dict.get("max")


class MetadataMismatchRule(Rule):
    """Single entry-point for all producer/consumer metadata validation.

    Consumer-driven throughout: keys present on the producer but absent on the
    consumer are ignored — the consumer defines the contract.
    """

    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        if consumer.metadata is None:
            return []

        violations: list[Violation] = []

        for key in consumer.metadata:
            match key:
                case "allowed_values":
                    violations.extend(self._compare_allowed_values(producer, consumer))
                case "range":
                    violations.extend(self._compare_range(producer, consumer))
                case "length":
                    violations.extend(self._compare_length(producer, consumer))
                case _:
                    violations.extend(self._check_key_mismatch(producer, consumer, key))

        return violations

    def _compare_allowed_values(
        self, producer: ContractField, consumer: ContractField
    ) -> list[Violation]:
        """Fails when the producer can emit a value the consumer does not accept."""
        consumer_values: list[Any] = consumer.metadata.get("allowed_values")  # type: ignore[union-attr]
        producer_values: list[Any] | None = (producer.metadata or {}).get("allowed_values")
        field_path = producer.name

        if producer_values is None:
            return [
                Violation(
                    rule=RuleName.METADATA_ALLOWED_VALUES_MISMATCH,
                    severity="CRITICAL",
                    field_path=field_path,
                    producer={"allowed_values": None},
                    consumer={"allowed_values": consumer_values},
                    message=(
                        f"Field '{field_path}' Producer has no allowed-values constraint"
                        " but Consumer restricts accepted values"
                        " — Producer may emit values Consumer will reject."
                    ),
                )
            ]

        unexpected = set(producer_values) - set(consumer_values)
        if not unexpected:
            return []

        return [
            Violation(
                rule=RuleName.METADATA_ALLOWED_VALUES_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"allowed_values": producer_values},
                consumer={"allowed_values": consumer_values},
                message=(
                    f"Field '{field_path}' Producer can emit {sorted(unexpected, key=str)!r}"
                    " but Consumer does not accept those values."
                ),
            )
        ]

    def _compare_range(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        """Fails when the producer's numeric range is wider than the consumer's."""
        c_range: dict[str, Any] = consumer.metadata.get("range")  # type: ignore[union-attr]
        p_range: dict[str, Any] | None = (producer.metadata or {}).get("range")
        field_path = producer.name

        if p_range is None:
            return [
                Violation(
                    rule=RuleName.METADATA_RANGE_MISMATCH,
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

        c_min = c_range.get("min")
        if c_min is not None:
            c_min_incl: bool = c_range.get("min_inclusive", True)
            p_min = p_range.get("min")
            if p_min is None:
                violations.append(
                    Violation(
                        rule=RuleName.METADATA_RANGE_MISMATCH,
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"range": p_range},
                        consumer={"range": c_range},
                        message=(
                            f"Field '{field_path}' Producer has no minimum bound"
                            f" but Consumer requires min={c_min}"
                            f" (inclusive={c_min_incl})"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )
            else:
                p_min_incl: bool = p_range.get("min_inclusive", True)
                if p_min < c_min or (p_min == c_min and p_min_incl and not c_min_incl):
                    violations.append(
                        Violation(
                            rule=RuleName.METADATA_RANGE_MISMATCH,
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

        c_max = c_range.get("max")
        if c_max is not None:
            c_max_incl: bool = c_range.get("max_inclusive", True)
            p_max = p_range.get("max")
            if p_max is None:
                violations.append(
                    Violation(
                        rule=RuleName.METADATA_RANGE_MISMATCH,
                        severity="CRITICAL",
                        field_path=field_path,
                        producer={"range": p_range},
                        consumer={"range": c_range},
                        message=(
                            f"Field '{field_path}' Producer has no maximum bound"
                            f" but Consumer requires max={c_max}"
                            f" (inclusive={c_max_incl})"
                            " — Producer can emit values Consumer will reject."
                        ),
                    )
                )
            else:
                p_max_incl: bool = p_range.get("max_inclusive", True)
                if p_max > c_max or (p_max == c_max and p_max_incl and not c_max_incl):
                    violations.append(
                        Violation(
                            rule=RuleName.METADATA_RANGE_MISMATCH,
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

    def _compare_length(self, producer: ContractField, consumer: ContractField) -> list[Violation]:
        """Fails when the producer's string/array length range is wider than the consumer's."""
        c_length: dict[str, int] = consumer.metadata.get("length")  # type: ignore[union-attr]
        p_length: dict[str, int] | None = (producer.metadata or {}).get("length")
        field_path = producer.name

        if p_length is None:
            return [
                Violation(
                    rule=RuleName.METADATA_LENGTH_MISMATCH,
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

        if c_min is not None:
            if p_min is None:
                violations.append(
                    Violation(
                        rule=RuleName.METADATA_LENGTH_MISMATCH,
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
                        rule=RuleName.METADATA_LENGTH_MISMATCH,
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

        if c_max is not None:
            if p_max is None:
                violations.append(
                    Violation(
                        rule=RuleName.METADATA_LENGTH_MISMATCH,
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
                        rule=RuleName.METADATA_LENGTH_MISMATCH,
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

    def suggest_fix(self, violation: Violation) -> FixSuggestion | None:
        path = violation.field_path
        producer = violation.producer
        consumer = violation.consumer
        match violation.rule:
            case RuleName.METADATA_ALLOWED_VALUES_MISMATCH:
                if producer.get("allowed_values") is None:
                    producer_instruction = (
                        f"Add an allowed-values constraint to field '{path}'"
                        f" whose values are a subset of {consumer['allowed_values']}."
                    )
                else:
                    producer_instruction = (
                        f"Restrict the allowed values for field '{path}'"
                        f" to {consumer['allowed_values']}."
                    )
                return FixSuggestion(
                    producer_suggestion=producer_instruction,
                    consumer_suggestion=(
                        f"Expand the allowed values for field '{path}'"
                        f" to include {producer['allowed_values']}."
                    ),
                )
            case RuleName.METADATA_RANGE_MISMATCH:
                return FixSuggestion(
                    producer_suggestion=(
                        f"Tighten the range constraint on field '{path}'"
                        f" to match the consumer: {consumer['range']}."
                    ),
                    consumer_suggestion=(
                        f"Widen the range constraint on field '{path}'"
                        f" to accept the producer's range: {producer['range']}."
                    ),
                )
            case RuleName.METADATA_LENGTH_MISMATCH:
                return FixSuggestion(
                    producer_suggestion=(
                        f"Tighten the length constraint on field '{path}'"
                        f" to match the consumer: {consumer['length']}."
                    ),
                    consumer_suggestion=(
                        f"Widen the length constraint on field '{path}'"
                        f" to accept the producer's length: {producer['length']}."
                    ),
                )
            case RuleName.METADATA_KEY_MISMATCH:
                # Each dict carries exactly one key — the metadata attribute name.
                key = next(iter(consumer))
                return FixSuggestion(
                    producer_suggestion=(
                        f"Change metadata '{key}' on field '{path}' to '{consumer[key]}'."
                    ),
                    consumer_suggestion=(
                        f"Change metadata '{key}' on field '{path}' to '{producer[key]}'."
                    ),
                )
            case _:
                return None

    def _check_key_mismatch(
        self,
        producer: ContractField,
        consumer: ContractField,
        key: str,
    ) -> list[Violation]:
        consumer_value: Any = consumer.metadata.get(key)  # type: ignore[union-attr]
        producer_value: Any = producer.metadata.get(key) if producer.metadata is not None else None

        if producer_value == consumer_value:
            return []

        field_path = producer.name

        return [
            Violation(
                rule=RuleName.METADATA_KEY_MISMATCH,
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
        ]
