from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractSchema


class SchemaParser(ABC):
    """Port for converting a decorated schema class into a canonical ContractSchema.

    Each framework adapter (Marshmallow, Pydantic, …) provides its own
    implementation. The service layer calls this without knowing which
    framework is in use.
    """

    @abstractmethod
    def parse(self, cls: type) -> ContractSchema:
        """Introspect *cls* and return its canonical ContractSchema representation."""
        ...
