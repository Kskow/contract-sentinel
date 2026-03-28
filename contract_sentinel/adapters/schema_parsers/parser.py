from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable

    from contract_sentinel.domain.schema import (
        ContractField,
        ContractSchema,
        UnknownFieldBehaviour,
    )


class ResolvedFieldType(NamedTuple):
    # Core — always set
    type: str
    format: str | None
    is_supported: bool = True
    # Object / array-of-objects — set by _resolve_nested, _resolve_list, _resolve_dict
    fields: list[ContractField] | None = None
    unknown: UnknownFieldBehaviour | None = None
    # Array of primitives — set by _resolve_list
    item_type: str | None = None
    # Dict/Mapping — set by _resolve_dict
    key_type: str | None = None
    value_type: str | None = None


class TypeMapEntry(NamedTuple):
    field_class: type
    json_type: str
    format: str | None = None
    is_supported: bool = True
    resolver: Callable[..., ResolvedFieldType] | None = None


class SchemaParser(ABC):
    """Abstract parser that converts a decorated schema class into a ContractSchema.

    Each framework implementation (Marshmallow, Pydantic, …) subclasses this.
    The service layer calls ``parse`` without knowing which framework is in use.
    """

    @abstractmethod
    def parse(self, cls: type) -> ContractSchema:
        """Introspect *cls* and return its canonical ContractSchema representation."""
        ...
