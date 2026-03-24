from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, NamedTuple

from contract_sentinel.domain.schema import (
    ContractField,
    ContractSchema,
    UnknownFieldBehaviour,
)

if TYPE_CHECKING:
    import types
    from collections.abc import Callable

    import marshmallow.fields as mmf


class _ResolvedFieldType(NamedTuple):
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


class _TypeMapEntry(NamedTuple):
    field_class: type
    json_type: str
    format: str | None = None
    is_supported: bool = True
    resolver: Callable[..., _ResolvedFieldType] | None = None


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
        self._ma: types.ModuleType = marshmallow
        self._validate = marshmallow.validate

        # Order matters: subclasses must appear before their parents.
        # Entries with a resolver delegate inner-type introspection to a dedicated method.
        # Entries with is_supported=False are recognised but not introspected — the report
        # will note that the tool cannot validate the inner structure of these types.
        self._type_map: list[_TypeMapEntry] = [
            # DateTime family — ISO strings; subclasses before the DateTime catch-all
            _TypeMapEntry(marshmallow.fields.NaiveDateTime, "string", "date-time"),
            _TypeMapEntry(marshmallow.fields.AwareDateTime, "string", "date-time"),
            _TypeMapEntry(marshmallow.fields.Time, "string", "time"),
            _TypeMapEntry(marshmallow.fields.Date, "string", "date"),
            _TypeMapEntry(marshmallow.fields.DateTime, "string", "date-time"),
            # Temporal duration — marshmallow dumps as total_seconds() (a number)
            _TypeMapEntry(marshmallow.fields.TimeDelta, "number"),
            # Numeric
            _TypeMapEntry(marshmallow.fields.Integer, "integer"),
            _TypeMapEntry(marshmallow.fields.Float, "number"),
            _TypeMapEntry(marshmallow.fields.Decimal, "number"),
            # Boolean
            _TypeMapEntry(marshmallow.fields.Boolean, "boolean"),
            # Collections — Dict before Mapping (subclass); Nested and List have resolvers;
            # Tuple is positional + heterogeneous with no JSON Schema equivalent.
            _TypeMapEntry(marshmallow.fields.Nested, "object", resolver=self._resolve_nested),
            _TypeMapEntry(marshmallow.fields.List, "array", resolver=self._resolve_list),
            _TypeMapEntry(marshmallow.fields.Dict, "object", resolver=self._resolve_dict),
            _TypeMapEntry(marshmallow.fields.Mapping, "object", resolver=self._resolve_dict),
            _TypeMapEntry(marshmallow.fields.Tuple, "array", is_supported=False),
            # Enum — string with a restricted value set; "enum" format signals enum semantics
            _TypeMapEntry(marshmallow.fields.Enum, "string", "enum"),
            # String subclasses with semantic formats — most specific first.
            # All are plain strings on the wire but carry application-layer meaning;
            # a producer/consumer format mismatch is caught by MetadataMismatchRule.
            _TypeMapEntry(marshmallow.fields.Email, "string", "email"),
            _TypeMapEntry(marshmallow.fields.URL, "string", "uri"),
            _TypeMapEntry(marshmallow.fields.UUID, "string", "uuid"),
            _TypeMapEntry(marshmallow.fields.IPv4Interface, "string", "ipv4interface"),
            _TypeMapEntry(marshmallow.fields.IPv6Interface, "string", "ipv6interface"),
            _TypeMapEntry(marshmallow.fields.IPInterface, "string", "ipinterface"),
            _TypeMapEntry(marshmallow.fields.IPv4, "string", "ipv4"),
            _TypeMapEntry(marshmallow.fields.IPv6, "string", "ipv6"),
            _TypeMapEntry(marshmallow.fields.IP, "string", "ip"),
            # Plain string — catch-all for any remaining String subclass
            _TypeMapEntry(marshmallow.fields.String, "string"),
            # Raw — schema-less pass-through; any value is valid on the wire
            _TypeMapEntry(marshmallow.fields.Raw, "any"),
            # Constant — always emits the same literal; type is inferred from the Python value
            _TypeMapEntry(marshmallow.fields.Constant, "any", resolver=self._resolve_constant),
            # Computed fields — output type is determined at runtime, not statically inspectable
            _TypeMapEntry(marshmallow.fields.Method, "string", is_supported=False),
            _TypeMapEntry(marshmallow.fields.Function, "string", is_supported=False),
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
            repository=self._repository,
            class_name=cls.__name__,
            unknown=unknown,
            fields=fields,
        )

    def _parse_field(self, name: str, field: mmf.Field) -> ContractField:
        wire_name = field.data_key if field.data_key is not None else name
        resolved = self._resolve_type(field)
        metadata = self._build_metadata(field, resolved)

        return ContractField(
            name=wire_name,
            type=resolved.type,
            is_required=field.required,
            is_nullable=field.allow_none,
            is_load_only=field.load_only,
            is_dump_only=field.dump_only,
            is_supported=resolved.is_supported,
            fields=resolved.fields,
            unknown=resolved.unknown,
            metadata=metadata if metadata else None,
        )

    def _build_metadata(self, field: mmf.Field, resolved: _ResolvedFieldType) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        if resolved.format is not None:
            metadata["format"] = resolved.format
            field_fmt: str | None = getattr(field, "format", None)
            if field_fmt is not None:
                metadata["custom_format"] = field_fmt

        if resolved.item_type is not None:
            metadata["item_type"] = resolved.item_type

        if resolved.key_type is not None:
            metadata["key_type"] = resolved.key_type

        if resolved.value_type is not None:
            metadata["value_type"] = resolved.value_type

        if isinstance(field, self._ma.fields.Enum):
            metadata["allowed_values"] = [m.value for m in field.enum]

        # Constant fields set load_default/dump_default to their value automatically;
        # emitting them alongside `constant` would be pure noise.
        is_constant = isinstance(field, self._ma.fields.Constant)
        if is_constant:
            # self._ma is ModuleType so attribute access returns Any; isinstance on Any
            # cannot narrow `field`, hence .constant is not visible to the type checker.
            metadata["constant"] = field.constant  # type: ignore[union-attr]
        else:
            if field.load_default is not self._ma.missing:
                metadata["load_default"] = field.load_default
            if field.dump_default is not self._ma.missing:
                metadata["dump_default"] = field.dump_default

        metadata.update(self._extract_validators(field))

        return metadata

    def _resolve_type(self, field: mmf.Field) -> _ResolvedFieldType:
        for entry in self._type_map:
            if isinstance(field, entry.field_class):
                if not entry.is_supported:
                    return _ResolvedFieldType(entry.json_type, entry.format, is_supported=False)
                if entry.resolver is not None:
                    return entry.resolver(field)
                return _ResolvedFieldType(entry.json_type, entry.format)

        # Unknown field type — class name as a format hint so metadata-level
        # diffing still catches mismatches between exotic types.
        # Marked unsupported: the tool cannot reason about the inner structure.
        return _ResolvedFieldType("string", type(field).__name__.lower(), is_supported=False)

    def _resolve_nested(self, field: mmf.Nested) -> _ResolvedFieldType:
        nested_schema: Any = field.schema
        nested_fields = [self._parse_field(name, f) for name, f in nested_schema.fields.items()]
        field_type = "array" if field.many else "object"
        return _ResolvedFieldType(
            field_type, None, fields=nested_fields, unknown=self._map_unknown(nested_schema.unknown)
        )

    def _resolve_list(self, field: mmf.List) -> _ResolvedFieldType:
        inner_resolved = self._resolve_type(field.inner)
        if inner_resolved.fields is not None:
            # List of nested objects — carry the inner schema structure through
            return _ResolvedFieldType(
                "array", None, fields=inner_resolved.fields, unknown=inner_resolved.unknown
            )
        return _ResolvedFieldType("array", None, item_type=inner_resolved.type)

    def _resolve_constant(self, field: mmf.Constant) -> _ResolvedFieldType:
        # Cases are evaluated top-to-bottom, so bool is safely matched before int
        # (bool is a subclass of int in Python).
        match field.constant:
            case bool():
                json_type = "boolean"
            case int():
                json_type = "integer"
            case float():
                json_type = "number"
            case str():
                json_type = "string"
            case list():
                json_type = "array"
            case dict():
                json_type = "object"
            case _:
                json_type = "any"
        return _ResolvedFieldType(json_type, None)

    def _resolve_dict(self, field: mmf.Dict) -> _ResolvedFieldType:
        key_type: str | None = None
        value_type: str | None = None
        value_fields: list[ContractField] | None = None
        value_unknown: UnknownFieldBehaviour | None = None

        if field.key_field is not None:
            key_type = self._resolve_type(field.key_field).type

        if field.value_field is not None:
            value_resolved = self._resolve_type(field.value_field)
            if value_resolved.fields is not None:
                value_fields = value_resolved.fields
                value_unknown = value_resolved.unknown
            else:
                value_type = value_resolved.type

        return _ResolvedFieldType(
            "object",
            None,
            fields=value_fields,
            unknown=value_unknown,
            key_type=key_type,
            value_type=value_type,
        )

    def _extract_validators(self, field: mmf.Field) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for validator in field.validators:
            self._extract_single_validator(validator, metadata)
        return metadata

    def _extract_single_validator(self, validator: object, metadata: dict[str, Any]) -> None:
        if isinstance(validator, self._validate.And):
            for inner in validator.validators:
                self._extract_single_validator(inner, metadata)
        elif isinstance(validator, self._validate.Length):
            length: dict[str, int] = {}
            if validator.equal is not None:
                length["equal"] = validator.equal
            else:
                if validator.min is not None:
                    length["min"] = validator.min
                if validator.max is not None:
                    length["max"] = validator.max
            if length:
                metadata["length"] = length
        elif isinstance(validator, self._validate.Range):
            range_: dict[str, int | float | bool] = {}
            if validator.min is not None:
                range_["min"] = validator.min
                range_["min_inclusive"] = validator.min_inclusive
            if validator.max is not None:
                range_["max"] = validator.max
                range_["max_inclusive"] = validator.max_inclusive
            if range_:
                metadata["range"] = range_
        elif isinstance(validator, self._validate.Regexp):
            metadata["pattern"] = validator.regex.pattern
        elif isinstance(validator, self._validate.OneOf):
            metadata["allowed_values"] = list(validator.choices)

    def _map_unknown(self, unknown: str) -> UnknownFieldBehaviour:
        return self._unknown_map.get(unknown, UnknownFieldBehaviour.FORBID)
