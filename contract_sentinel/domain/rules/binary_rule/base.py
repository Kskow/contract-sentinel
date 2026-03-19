from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.violation import Violation
    from contract_sentinel.domain.schema import ContractField


class BinaryRule(ABC):
    """Both fields are present — type, nullability, requirement, and metadata checks."""

    @abstractmethod
    def check(self, producer: ContractField, consumer: ContractField) -> list[Violation]: ...
