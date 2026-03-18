from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from contract_sentinel.domain.schema import (
    MISSING,
    ContractField,
    ContractSchema,
    UnknownFieldBehaviour,
)

if TYPE_CHECKING:
    import marshmallow.fields as mmf


class SchemaParser(ABC):
    """Abstract parser that converts a decorated schema class into a ContractSchema.

    Each framework implementation (Marshmallow, Pydantic, …) subclasses this.
    The service layer calls ``parse`` without knowing which framework is in use.
    """

    @abstractmethod
    def parse(self, cls: type) -> ContractSchema:
        """Introspect *cls* and return its canonical ContractSchema representation."""
        ...


class Marshmallow3Parser(SchemaParser):
    """SchemaParser backed by Marshmallow 3.x.

    marshmallow is imported once in ``__init__`` so this module loads safely
    without the marshmallow optional extra installed — the import only runs
    when the parser is actually constructed.
    """

    def __init__(self, repository: str) -> None:
        import marshmallow

        self._repository = repository
        self._ma: marshmallow = marshmallow  # type: ignore[valid-type]

        # Each entry is (field_class, json_schema_type, format | None).
        # Order matters: subclasses must appear before their parents.
        # - NaiveDateTime / AwareDateTime / Time / Date all subclass DateTime → placed first.
        # - IPv4/IPv6 before IP; IPv4Interface/IPv6Interface before IPInterface (safest order).
        # - Dict subclasses Mapping → placed before Mapping.
        # - All format-bearing String subclasses appear before the plain String catch-all.
        self._type_map: list[tuple[type, str, str | None]] = [
            # DateTime family — all serialise as ISO strings
            (marshmallow.fields.NaiveDateTime, "string", "date-time"),
            (marshmallow.fields.AwareDateTime, "string", "date-time"),
            (marshmallow.fields.Time, "string", "time"),
            (marshmallow.fields.Date, "string", "date"),
            (marshmallow.fields.DateTime, "string", "date-time"),
            # Temporal duration — marshmallow dumps as total_seconds() (a number)
            (marshmallow.fields.TimeDelta, "number", None),
            # Numeric
            (marshmallow.fields.Integer, "integer", None),
            (marshmallow.fields.Float, "number", None),
            (marshmallow.fields.Decimal, "number", None),
            # Boolean
            (marshmallow.fields.Boolean, "boolean", None),
            # Collections
            (marshmallow.fields.Tuple, "array", None),
            (marshmallow.fields.List, "array", None),
            (marshmallow.fields.Dict, "object", None),
            (marshmallow.fields.Mapping, "object", None),
            # String subclasses with semantic formats — most specific first
            (marshmallow.fields.Email, "string", "email"),
            (marshmallow.fields.URL, "string", "uri"),
            (marshmallow.fields.UUID, "string", "uuid"),
            (marshmallow.fields.IPv4Interface, "string", "ipv4interface"),
            (marshmallow.fields.IPv6Interface, "string", "ipv6interface"),
            (marshmallow.fields.IPInterface, "string", "ipinterface"),
            (marshmallow.fields.IPv4, "string", "ipv4"),
            (marshmallow.fields.IPv6, "string", "ipv6"),
            (marshmallow.fields.IP, "string", "ip"),
            (marshmallow.fields.Enum, "string", "enum"),
            # Plain string — catch-all for any remaining String subclass
            (marshmallow.fields.String, "string", None),
        ]
        self._unknown_map: dict[str, UnknownFieldBehaviour] = {
            marshmallow.RAISE: UnknownFieldBehaviour.FORBID,
            marshmallow.EXCLUDE: UnknownFieldBehaviour.IGNORE,
            marshmallow.INCLUDE: UnknownFieldBehaviour.ALLOW,
        }

    def parse(self, cls: type) -> ContractSchema:
        """Introspect a ``@contract``-decorated Marshmallow 3 schema and return a ContractSchema."""
        meta = cls.__contract__  # type: ignore[attr-defined]  # set by @contract decorator
        schema_instance: Any = cls()

        unknown = self._map_unknown(schema_instance.unknown)
        fields = [self._parse_field(name, field) for name, field in schema_instance.fields.items()]

        return ContractSchema(
            topic=meta.topic,
            role=meta.role.value,
            version=meta.version,
            repository=self._repository,
            class_name=cls.__name__,
            unknown=unknown,
            fields=fields,
        )

    def _parse_field(self, name: str, field: mmf.Field) -> ContractField:
        field_type, field_format, nested_fields, nested_unknown = self._resolve_type(field)

        raw_default: Any = field.load_default
        default = MISSING if raw_default is self._ma.missing else raw_default

        return ContractField(
            name=name,
            type=field_type,
            format=field_format,
            is_required=field.required,
            is_nullable=field.allow_none,
            default=default,
            fields=nested_fields,
            unknown=nested_unknown,
            values=self._extract_enum_values(field),
        )

    def _resolve_type(
        self, field: mmf.Field
    ) -> tuple[str, str | None, list[ContractField] | None, UnknownFieldBehaviour | None]:
        if isinstance(field, self._ma.fields.Nested):
            nested_schema: Any = field.schema
            nested_fields = [self._parse_field(name, f) for name, f in nested_schema.fields.items()]
            return "object", None, nested_fields, self._map_unknown(nested_schema.unknown)

        for field_class, type_name, fmt in self._type_map:
            if isinstance(field, field_class):
                return type_name, fmt, None, None

        # Unknown field type — preserve the class name as a format hint so
        # format-level diffing still catches mismatches between exotic types.
        return "string", type(field).__name__.lower(), None, None

    def _extract_enum_values(self, field: mmf.Field) -> list[str | int | float | bool] | None:
        """Return the list of allowed values for Enum fields; None for everything else."""
        if not isinstance(field, self._ma.fields.Enum):
            return None
        return [m.value for m in field.enum]

    def _map_unknown(self, unknown: str) -> UnknownFieldBehaviour:
        return self._unknown_map.get(unknown, UnknownFieldBehaviour.FORBID)
