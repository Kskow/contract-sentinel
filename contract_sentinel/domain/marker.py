from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

_T = TypeVar("_T")


class Role(Enum):
    """Declares whether a schema class acts as a data producer or consumer."""

    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass(frozen=True)
class ContractMeta:
    """Immutable metadata attached to a class by the ``@contract`` decorator."""

    topic: str
    role: Role
    version: str


def contract(
    topic: str,
    role: Role,
    version: str,
) -> Callable[[type[_T]], type[_T]]:
    """Class decorator that marks a schema as a contract participant.

    Sets ``__contract__`` on the decorated class to a :class:`ContractMeta`
    instance carrying the supplied *topic*, *role*, and *version*.  No other attribute on the
    class is modified.

    Usage::

        @contract(topic="orders.created", role=Role.PRODUCER, version="1.0.0")
        class OrderSchema(Schema):
            ...
    """
    meta = ContractMeta(topic=topic, role=role, version=version)

    def decorator(cls: type[_T]) -> type[_T]:
        cls.__contract__ = meta  # type: ignore[attr-defined]
        return cls

    return decorator
