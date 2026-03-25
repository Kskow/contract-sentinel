from __future__ import annotations

from enum import StrEnum

from contract_sentinel.domain.errors import UnsupportedFrameworkError


class Framework(StrEnum):
    """Supported schema framework backends."""

    MARSHMALLOW = "marshmallow"


def detect_framework(cls: type) -> Framework:
    """Infer the schema framework from class attributes set by the framework itself.

    No framework import is required — the attributes are attached to the class
    by the framework's metaclass or base class when the user defines their schema.

    Raises ``UnsupportedFrameworkError`` when the class cannot be matched to any
    known framework.
    """
    if any(getattr(base, "__module__", "").startswith("marshmallow") for base in cls.__mro__):
        return Framework.MARSHMALLOW
    raise UnsupportedFrameworkError(
        f"Cannot detect schema framework for '{cls.__name__}'. "
        f"Supported frameworks: {', '.join(Framework)}."
    )
