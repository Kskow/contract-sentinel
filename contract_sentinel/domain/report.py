from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.engine import PairViolations


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


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
class ContractsValidationReport:
    """Aggregated result across all validated topic groups."""

    reports: list[ContractReport]

    @property
    def status(self) -> ValidationStatus:
        """FAILED when at least one ContractReport is FAILED."""
        for report in self.reports:
            if report.status == ValidationStatus.FAILED:
                return ValidationStatus.FAILED
        return ValidationStatus.PASSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reports": [report.to_dict() for report in self.reports],
        }
