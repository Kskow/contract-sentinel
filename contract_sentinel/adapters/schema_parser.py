from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_sentinel.domain.schema import ContractSchema


class SchemaParser(ABC):
    """Abstract parser that converts a decorated schema class into a ContractSchema.

    Each framework implementation (Marshmallow, Pydantic, …) subclasses this.
    The service layer calls ``parse`` without knowing which framework is in use.
    """

    @abstractmethod
    def parse(self, cls: type) -> ContractSchema:
        """Introspect *cls* and return its canonical ContractSchema representation."""
        ...
