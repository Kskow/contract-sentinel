from __future__ import annotations

import dataclasses
from enum import StrEnum
from typing import Any


class UnknownFieldBehaviour(StrEnum):
    """How a schema handles fields not declared in its definition.

    FORBID — unknown fields raise a validation error (default).
    IGNORE — unknown fields are silently dropped.
    ALLOW  — unknown fields are passed through as-is.
    """

    FORBID = "forbid"
    IGNORE = "ignore"
    ALLOW = "allow"


@dataclasses.dataclass
class ContractField:
    """Canonical representation of a single field in a contract schema.

    Core fields (always present, always breaking on mismatch):
        name           — wire name (data_key if set, otherwise attribute name).
        type           — JSON Schema type string.
        is_required    — field must be present in the payload.
        is_nullable    — field may be null.
        is_load_only   — field only appears during deserialization (consumer → producer).
        is_dump_only   — field only appears during serialization (producer → consumer).

    Structural fields (typed, require their own rule semantics):
        fields   — populated for type "object" or "array" of objects (nested schema).
        unknown  — populated for type "object", carrying the nested schema's unknown-field policy.

    Soft constraints (compared via MetadataMismatchRule):
        metadata — arbitrary dict of type-specific extras injected by the parser
                   (e.g. format, custom_format, values, load_default, dump_default,
                   length, range, pattern, allowed_values, item_type).
                   Omitted from serialised JSON when None.
    """

    name: str
    type: str
    is_required: bool
    is_nullable: bool
    is_load_only: bool = False
    is_dump_only: bool = False
    is_supported: bool = True
    fields: list[ContractField] | None = None
    unknown: UnknownFieldBehaviour | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "is_required": self.is_required,
            "is_nullable": self.is_nullable,
        }
        if self.is_load_only:
            result["is_load_only"] = self.is_load_only
        if self.is_dump_only:
            result["is_dump_only"] = self.is_dump_only
        result["is_supported"] = self.is_supported
        if self.fields is not None:
            result["fields"] = [f.to_dict() for f in self.fields]
        if self.unknown is not None:
            result["unknown"] = self.unknown.value
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractField:
        kwargs: dict[str, Any] = {
            "name": data["name"],
            "type": data["type"],
            "is_required": data["is_required"],
            "is_nullable": data["is_nullable"],
            "is_load_only": data.get("is_load_only", False),
            "is_dump_only": data.get("is_dump_only", False),
            "is_supported": data.get("is_supported", True),
        }
        if "fields" in data:
            kwargs["fields"] = [cls.from_dict(f) for f in data["fields"]]
        if "unknown" in data:
            kwargs["unknown"] = UnknownFieldBehaviour(data["unknown"])
        if "metadata" in data:
            kwargs["metadata"] = data["metadata"]
        return cls(**kwargs)


@dataclasses.dataclass
class ContractSchema:
    """Canonical envelope for a contract published by one participant.

    Produced by the parser adapter from a decorated schema class and stored in
    Storage as JSON. Consumed by the validator to compare producer/consumer pairs.
    """

    topic: str
    role: str
    repository: str
    class_name: str
    unknown: UnknownFieldBehaviour
    fields: list[ContractField]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "role": self.role,
            "repository": self.repository,
            "class_name": self.class_name,
            "unknown": self.unknown.value,
            "fields": [f.to_dict() for f in self.fields],
        }

    def to_store_key(self) -> str:
        """Return the canonical relative S3 key for this contract."""
        return f"{self.topic}/{self.role}/{self.repository}/{self.class_name}.json"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractSchema:
        return cls(
            topic=data["topic"],
            role=data["role"],
            repository=data["repository"],
            class_name=data["class_name"],
            unknown=UnknownFieldBehaviour(data["unknown"]),
            fields=[ContractField.from_dict(f) for f in data["fields"]],
        )
