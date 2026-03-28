from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.violation import Violation
    from contract_sentinel.domain.schema import ContractField


class RuleName(StrEnum):
    TYPE_MISMATCH = "TYPE_MISMATCH"
    MISSING_FIELD = "MISSING_FIELD"
    REQUIREMENT_MISMATCH = "REQUIREMENT_MISMATCH"
    NULLABILITY_MISMATCH = "NULLABILITY_MISMATCH"
    DIRECTION_MISMATCH = "DIRECTION_MISMATCH"
    STRUCTURE_MISMATCH = "STRUCTURE_MISMATCH"
    UNDECLARED_FIELD = "UNDECLARED_FIELD"
    COUNTERPART_MISMATCH = "COUNTERPART_MISMATCH"
    METADATA_ALLOWED_VALUES_MISMATCH = "METADATA_ALLOWED_VALUES_MISMATCH"
    METADATA_RANGE_MISMATCH = "METADATA_RANGE_MISMATCH"
    METADATA_LENGTH_MISMATCH = "METADATA_LENGTH_MISMATCH"
    METADATA_KEY_MISMATCH = "METADATA_KEY_MISMATCH"


class Rule(ABC):
    """Rule that operates on a producer/consumer field pair.

    Either side may be ``None`` — rules self-determine what to do based on presence:

    - Both present     → standard matched-field checks (type, nullability, etc.)
    - producer is None → consumer-only checks (e.g. MissingFieldRule)
    - consumer is None → not used in practice; rules return ``[]``
    """

    @abstractmethod
    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]: ...
