from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Sequence


class UnknownFieldBehaviour(StrEnum):
    """How a schema handles fields not declared in its definition.

    FORBID — unknown fields raise a validation error (default).
    IGNORE — unknown fields are silently dropped.
    ALLOW  — unknown fields are passed through as-is.
    """

    FORBID = "forbid"
    IGNORE = "ignore"
    ALLOW = "allow"


# Sentinel for a field that carries no default value.
# Absent from the serialised JSON; distinct from default=None.
MISSING: Final[object] = object()


@dataclasses.dataclass
class ContractField:
    """Canonical representation of a single field in a contract schema.

    `format` refines `type` with a JSON-Schema-compatible format string.
    Omitted from serialised JSON when None.
    `default` uses the MISSING sentinel when the field has no default value —
    in that case the key is omitted from the serialised JSON entirely.
    `fields` is populated only when type == "object" (nested schema).
    `unknown` is populated only when type == "object", carrying the nested
    schema's own unknown-field policy.
    `values` is populated only for enum fields; holds the set of allowed values.
    """

    name: str
    type: str
    is_required: bool
    is_nullable: bool
    format: str | None = None
    default: object = dataclasses.field(default=MISSING)
    fields: list[ContractField] | None = None
    metadata: dict[str, Any] | None = None
    unknown: UnknownFieldBehaviour | None = None
    values: Sequence[str | int | float] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "is_required": self.is_required,
            "is_nullable": self.is_nullable,
        }
        if self.format is not None:
            result["format"] = self.format
        if self.default is not MISSING:
            result["default"] = self.default
        if self.fields is not None:
            result["fields"] = [f.to_dict() for f in self.fields]
        if self.metadata is not None:
            result["metadata"] = self.metadata
        if self.unknown is not None:
            result["unknown"] = self.unknown.value
        if self.values is not None:
            result["values"] = self.values
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractField:
        kwargs: dict[str, Any] = {
            "name": data["name"],
            "type": data["type"],
            "is_required": data["is_required"],
            "is_nullable": data["is_nullable"],
        }
        if "format" in data:
            kwargs["format"] = data["format"]
        if "default" in data:
            kwargs["default"] = data["default"]
        if "fields" in data:
            kwargs["fields"] = [cls.from_dict(f) for f in data["fields"]]
        if "metadata" in data:
            kwargs["metadata"] = data["metadata"]
        if "unknown" in data:
            kwargs["unknown"] = UnknownFieldBehaviour(data["unknown"])
        if "values" in data:
            kwargs["values"] = data["values"]
        return cls(**kwargs)


@dataclasses.dataclass
class ContractSchema:
    """Canonical envelope for a versioned contract published by one participant.

    Produced by the parser adapter from a decorated schema class and stored in
    Storage as JSON. Consumed by the validator to compare producer/consumer pairs.
    """

    topic: str
    role: str
    version: str
    repository: str
    class_name: str
    unknown: UnknownFieldBehaviour
    fields: list[ContractField]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "role": self.role,
            "version": self.version,
            "repository": self.repository,
            "class_name": self.class_name,
            "unknown": self.unknown.value,
            "fields": [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractSchema:
        return cls(
            topic=data["topic"],
            role=data["role"],
            version=data["version"],
            repository=data["repository"],
            class_name=data["class_name"],
            unknown=UnknownFieldBehaviour(data["unknown"]),
            fields=[ContractField.from_dict(f) for f in data["fields"]],
        )
