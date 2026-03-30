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
                case "forbidden_values":
                    violations.extend(self._compare_forbidden_values(producer, consumer))
                case "contains_only":
                    violations.extend(self._compare_contains_only(producer, consumer))
                case "contains_none_of":
                    violations.extend(self._compare_contains_none_of(producer, consumer))
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

    def _compare_forbidden_values(
        self, producer: ContractField, consumer: ContractField
    ) -> list[Violation]:
        """Fails when the producer can still emit values the consumer forbids."""
        consumer_forbidden: list[Any] = consumer.metadata.get("forbidden_values")  # type: ignore[union-attr]
        producer_forbidden: list[Any] | None = (producer.metadata or {}).get("forbidden_values")
        field_path = producer.name

        if producer_forbidden is None:
            return [
                Violation(
                    rule=RuleName.METADATA_FORBIDDEN_VALUES_MISMATCH,
                    severity="CRITICAL",
                    field_path=field_path,
                    producer={"forbidden_values": None},
                    consumer={"forbidden_values": consumer_forbidden},
                    message=(
                        f"Field '{field_path}' Producer has no forbidden-values constraint"
                        " but Consumer forbids some values"
                        " — Producer may emit values Consumer will reject."
                    ),
                )
            ]

        not_covered = set(consumer_forbidden) - set(producer_forbidden)
        if not not_covered:
            return []

        return [
            Violation(
                rule=RuleName.METADATA_FORBIDDEN_VALUES_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"forbidden_values": producer_forbidden},
                consumer={"forbidden_values": consumer_forbidden},
                message=(
                    f"Field '{field_path}' Producer does not forbid"
                    f" {sorted(not_covered, key=str)!r}"
                    " which Consumer rejects — Producer may emit values Consumer will reject."
                ),
            )
        ]

    def _compare_contains_only(
        self, producer: ContractField, consumer: ContractField
    ) -> list[Violation]:
        """Fails when the producer can emit list items the consumer does not accept."""
        consumer_choices: list[Any] = consumer.metadata.get("contains_only")  # type: ignore[union-attr]
        producer_choices: list[Any] | None = (producer.metadata or {}).get("contains_only")
        field_path = producer.name

        if producer_choices is None:
            return [
                Violation(
                    rule=RuleName.METADATA_CONTAINS_ONLY_MISMATCH,
                    severity="CRITICAL",
                    field_path=field_path,
                    producer={"contains_only": None},
                    consumer={"contains_only": consumer_choices},
                    message=(
                        f"Field '{field_path}' Producer has no contains-only constraint"
                        " but Consumer restricts accepted items"
                        " — Producer may emit items Consumer will reject."
                    ),
                )
            ]

        unexpected = set(producer_choices) - set(consumer_choices)
        if not unexpected:
            return []

        return [
            Violation(
                rule=RuleName.METADATA_CONTAINS_ONLY_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"contains_only": producer_choices},
                consumer={"contains_only": consumer_choices},
                message=(
                    f"Field '{field_path}' Producer can emit items"
                    f" {sorted(unexpected, key=str)!r}"
                    " that Consumer does not accept."
                ),
            )
        ]

    def _compare_contains_none_of(
        self, producer: ContractField, consumer: ContractField
    ) -> list[Violation]:
        """Fails when the producer can include list items the consumer excludes."""
        consumer_none_of: list[Any] = consumer.metadata.get("contains_none_of")  # type: ignore[union-attr]
        producer_none_of: list[Any] | None = (producer.metadata or {}).get("contains_none_of")
        field_path = producer.name

        if producer_none_of is None:
            return [
                Violation(
                    rule=RuleName.METADATA_CONTAINS_NONE_OF_MISMATCH,
                    severity="CRITICAL",
                    field_path=field_path,
                    producer={"contains_none_of": None},
                    consumer={"contains_none_of": consumer_none_of},
                    message=(
                        f"Field '{field_path}' Producer has no contains-none-of constraint"
                        " but Consumer excludes some items"
                        " — Producer may include items Consumer will reject."
                    ),
                )
            ]

        not_covered = set(consumer_none_of) - set(producer_none_of)
        if not not_covered:
            return []

        return [
            Violation(
                rule=RuleName.METADATA_CONTAINS_NONE_OF_MISMATCH,
                severity="CRITICAL",
                field_path=field_path,
                producer={"contains_none_of": producer_none_of},
                consumer={"contains_none_of": consumer_none_of},
                message=(
                    f"Field '{field_path}' Producer does not exclude"
                    f" {sorted(not_covered, key=str)!r}"
                    " which Consumer rejects — Producer may include items Consumer will reject."
                ),
            )
        ]

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
            case RuleName.METADATA_FORBIDDEN_VALUES_MISMATCH:
                if producer.get("forbidden_values") is None:
                    producer_instruction = (
                        f"Add a NoneOf constraint to field '{path}'"
                        f" that forbids at least {consumer['forbidden_values']}."
                    )
                else:
                    producer_instruction = (
                        f"Expand the NoneOf constraint on field '{path}'"
                        f" to also forbid {consumer['forbidden_values']}."
                    )
                return FixSuggestion(
                    producer_suggestion=producer_instruction,
                    consumer_suggestion=(
                        f"Reduce the forbidden_values constraint on field '{path}'"
                        " to only include values the producer also forbids."
                    ),
                )
            case RuleName.METADATA_CONTAINS_ONLY_MISMATCH:
                if producer.get("contains_only") is None:
                    producer_instruction = (
                        f"Add a ContainsOnly constraint to field '{path}'"
                        f" restricting emitted items to a subset of {consumer['contains_only']}."
                    )
                else:
                    producer_instruction = (
                        f"Restrict the ContainsOnly constraint on field '{path}'"
                        f" to {consumer['contains_only']}."
                    )
                return FixSuggestion(
                    producer_suggestion=producer_instruction,
                    consumer_suggestion=(
                        f"Expand the ContainsOnly constraint on field '{path}'"
                        " to include all items the producer may emit."
                    ),
                )
            case RuleName.METADATA_CONTAINS_NONE_OF_MISMATCH:
                if producer.get("contains_none_of") is None:
                    producer_instruction = (
                        f"Add a ContainsNoneOf constraint to field '{path}'"
                        f" that excludes at least {consumer['contains_none_of']}."
                    )
                else:
                    producer_instruction = (
                        f"Expand the ContainsNoneOf constraint on field '{path}'"
                        f" to also exclude {consumer['contains_none_of']}."
                    )
                return FixSuggestion(
                    producer_suggestion=producer_instruction,
                    consumer_suggestion=(
                        f"Reduce the ContainsNoneOf constraint on field '{path}'"
                        " to only include values the producer also excludes."
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
