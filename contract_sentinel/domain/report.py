from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contract_sentinel.domain.fix_suggestions import PairFixSuggestion
    from contract_sentinel.domain.rules.violation import Violation


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclasses.dataclass
class PairViolations:
    """Violations produced by a single producer/consumer pair."""

    producer_id: str | None
    consumer_id: str | None
    violations: list[Violation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer_id": self.producer_id,
            "consumer_id": self.consumer_id,
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclasses.dataclass
class ContractReport:
    """Validation result for a single topic group, broken down by pair."""

    topic: str
    pairs: list[PairViolations]

    @property
    def status(self) -> ValidationStatus:
        """FAILED when at least one CRITICAL violation exists; WARNING-only stays PASSED."""
        for pair in self.pairs:
            for violation in pair.violations:
                if violation.severity == "CRITICAL":
                    return ValidationStatus.FAILED
        return ValidationStatus.PASSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "status": self.status,
            "pairs": [pair.to_dict() for pair in self.pairs],
        }


@dataclasses.dataclass
class ValidationReport:
    """Aggregated result across all validated topic groups."""

    contracts: list[ContractReport]

    @property
    def status(self) -> ValidationStatus:
        """FAILED when at least one ContractReport is FAILED."""
        for contract in self.contracts:
            if contract.status == ValidationStatus.FAILED:
                return ValidationStatus.FAILED
        return ValidationStatus.PASSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "contracts": [contract.to_dict() for contract in self.contracts],
        }


@dataclasses.dataclass
class FixSuggestion:
    """Atomic fix unit — one per CRITICAL violation."""

    producer_suggestion: str
    consumer_suggestion: str


@dataclasses.dataclass
class TopicFixSuggestions:
    """Fix suggestions for a single topic — only pairs with at least one CRITICAL violation."""

    topic: str
    pairs: list[PairFixSuggestion]


@dataclasses.dataclass
class FixSuggestionsReport:
    """Sparse fix report — only topics with at least one failing pair."""

    suggestions: list[TopicFixSuggestions]

    @property
    def has_suggestions(self) -> bool:
        return len(self.suggestions) > 0
