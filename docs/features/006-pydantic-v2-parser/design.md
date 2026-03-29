# Design — Pydantic v2 Parser

## Approach: `model_json_schema(mode='serialization')`

Rather than manually introspecting Python type annotations (`get_origin`, `get_args`,
`types.UnionType` vs `typing.Union`, `annotated_types.Ge/Le/…` object walking), `PydanticParser`
calls Pydantic's own schema generator:

```python
schema = cls.model_json_schema(mode='serialization')
```

`mode='serialization'` produces JSON Schema that reflects the **wire representation** —
serialization aliases are used as property names, and the output describes what `.model_dump()`
actually emits. This is exactly what contract testing needs.

In exchange for eliminating all annotation introspection, the parser must handle three patterns
specific to JSON Schema output:

1. `$ref` / `$defs` — nested models are emitted as references, not inline.
2. `anyOf` — nullable fields use `anyOf: [T_schema, {type: null}]`.
3. `required` array — required field names are in a top-level list, not per-property.

These three are small, isolated, and well-understood. Everything else — type mapping,
constraint keys, Pydantic semantic types, `Literal`, `Enum`, new field types in future
Pydantic releases — is free.

---

## Decorator Compatibility

`@contract` sets `cls.__contract__ = meta` after Pydantic's `ModelMetaclass` has run.
Pydantic fields live in `model_fields`; setting an arbitrary `__contract__` class attribute
post-construction will not create a Pydantic field or interfere with schema generation.
No changes to `participant.py` are needed.

---

## Framework Detection

`detect_framework` gains a Pydantic probe that runs **before** the Marshmallow check:

```
if hasattr(cls, "model_fields"):             → Framework.PYDANTIC
if any(base.__module__.startswith("marshmallow") …):  → Framework.MARSHMALLOW
raise UnsupportedFrameworkError(…)
```

`model_fields` is set by Pydantic's `ModelMetaclass` on every `BaseModel` subclass. The probe
does not import pydantic — consistent with how the Marshmallow probe works.

Adding `Framework.PYDANTIC` to the `StrEnum` automatically updates the `', '.join(Framework)`
fragment in both `UnsupportedFrameworkError` messages (`detect_framework` and `get_parser`),
but the two unit tests that assert the exact error string must be updated:

- `tests/unit/test_domain/test_framework.py` — `detect_framework` error message
- `tests/unit/test_factory.py` — `get_parser` error message

---

## Nested Model Class Registry

`model_json_schema()` resolves types to JSON Schema but discards Python class references.
To read `model_config['extra']` for nested models, the parser builds a
`dict[str, type]` registry — `{ClassName: cls}` — **before** calling `model_json_schema()`,
via a targeted, shallow walk of `model_fields`:

```
registry = {}
_collect_nested_classes(cls, registry)

def _collect_nested_classes(cls, registry):
    for field_info in cls.model_fields.values():
        ann = field_info.annotation  # only used to find BaseModel subclasses
        if isinstance(ann, type) and issubclass(ann, BaseModel) and ann not in registry:
            registry[ann.__name__] = ann
            _collect_nested_classes(ann, registry)  # recurse
```

This is **not** full annotation introspection — it only checks `isinstance(ann, type) and
issubclass(ann, BaseModel)`. Generics (`list[Model]`, `Optional[Model]`) are out of scope for
this walk; those field annotations are already resolved in the JSON Schema output. For the
`unknown` policy of a model referenced via `$ref`, if its class is not in the registry, default
to `UnknownFieldBehaviour.IGNORE` — a safe V1 fallback.

---

## `UnknownFieldBehaviour` Mapping

Read `model_config` directly — not from JSON Schema (it has no equivalent):

| `model_config.get('extra')` | `UnknownFieldBehaviour` | Notes |
|---|---|---|
| `'forbid'` | `FORBID` | |
| `'ignore'` | `IGNORE` | |
| `'allow'` | `ALLOW` | |
| `None` (key absent) | `IGNORE` | Pydantic v2 default behaviour |

**Research item — verify at runtime:** confirm that `cls.model_config.get('extra')` returns
`None` (not `'ignore'`) when `extra` is not explicitly set, so the `None → IGNORE` default
mapping is applied correctly.

---

## `is_required` — `required` Array Lookup

JSON Schema places required field names in a top-level array, not per-property:

```json
{
  "properties": { "amount": {...}, "note": {...} },
  "required": ["amount"]
}
```

Build a `set` from the `"required"` list (default `[]` if absent) before iterating
`"properties"`. Per-field: `field_name in required_set`.

Wire names (aliases) are the property keys — the `"required"` array also uses the alias name.
No extra mapping needed.

---

## `anyOf` — Nullable Detection

`Optional[T]` and `T | None` both produce:

```json
{"anyOf": [<T_schema>, {"type": "null"}]}
```

Detection: if a property schema has `"anyOf"`, partition the members into null-members
(`{"type": "null"}`) and non-null members. If exactly one null-member exists:
- `is_nullable = True`
- Unwrap the single non-null member and use it as the effective property schema.

If `anyOf` contains more than one non-null member (a true union type — e.g. `str | int`),
mark `is_supported=False` and map `type="any"`.

---

## `$ref` / `$defs` Resolution

Nested models appear as:

```json
{"$ref": "#/$defs/CustomerSchema"}
```

Resolver:

```
def _resolve_ref(ref: str, defs: dict) -> dict:
    # ref is always "#/$defs/<Name>" in Pydantic v2
    name = ref.split("/")[-1]
    return defs[name]
```

Pass the top-level `$defs` dict through every recursive call. If a `$ref` key is absent from
`$defs` (should not happen in practice), map to `type="any"`, `is_supported=False`.

---

## JSON Schema Output → `ContractField` Translation

### Type mapping

| JSON Schema property schema | `ContractField.type` | `metadata.format` | Notes |
|---|---|---|---|
| `{"type": "string"}` | `string` | – | |
| `{"type": "string", "format": "date-time"}` | `string` | `date-time` | |
| `{"type": "string", "format": "date"}` | `string` | `date` | |
| `{"type": "string", "format": "time"}` | `string` | `time` | |
| `{"type": "string", "format": "uuid"}` | `string` | `uuid` | |
| `{"type": "string", "format": "email"}` | `string` | `email` | |
| `{"type": "string", "format": "uri"}` | `string` | `uri` | Pydantic `AnyUrl`, `HttpUrl` |
| `{"type": "string", "format": "ipv4"}` | `string` | `ipv4` | |
| `{"type": "string", "format": "ipv6"}` | `string` | `ipv6` | |
| `{"type": "integer"}` | `integer` | – | |
| `{"type": "number"}` | `number` | – | `float`, `Decimal`, `timedelta` |
| `{"type": "boolean"}` | `boolean` | – | |
| `{"type": "object", "properties": {…}}` | `object` | – | Inline nested object (rare in Pydantic v2) |
| `{"$ref": "#/$defs/Name"}` | `object` | – | Resolve ref → nested `fields` + `unknown` |
| `{"type": "array", "items": {…}}` | `array` | – | See list handling below |
| `{"type": "object", "additionalProperties": {…}}` | `object` | – | See dict handling below |
| `{"enum": […]}` | Infer from first value¹ | `enum` if str values | `Literal` or `Enum` |
| `{}` (empty schema) | `any` | – | `typing.Any` |
| `{"anyOf": [T, null]}` | (unwrap T, `is_nullable=True`) | – | See nullable section |
| `{"anyOf": [T1, T2, …]}` (non-nullable union) | `any` | – | `is_supported=False` |
| Unrecognised pattern | `string` | `<title_lower>` or `unknown` | `is_supported=False` |

¹ `{"enum": [1, 2, 3]}` → integers → `type="integer"`. `{"enum": ["a", "b"]}` → strings →
`type="string"`, `format="enum"`, `metadata.allowed_values`. Mixed-type enums → `type="any"`.

### List handling

```json
{"type": "array", "items": <item_schema>}
```

- `item_schema` is a primitive → `metadata.item_type = <resolved type string>`
- `item_schema` is a `$ref` → resolve to `fields` + `unknown` (same path as nested object)

### Dict handling

```json
{"type": "object", "additionalProperties": <value_schema>}
```

- `metadata.key_type = "string"` (JSON objects always have string keys)
- `value_schema` is a primitive → `metadata.value_type = <resolved type string>`
- `value_schema` is a `$ref` → resolve to `fields` + `unknown`

---

## Constraint Extraction

Constraints from `Field(ge=…, le=…, min_length=…, max_length=…, pattern=…)` appear directly
as standard JSON Schema keywords on the property schema — no `FieldInfo.metadata` walking
required.

### Range (`metadata.range`)

| JSON Schema key | `range` entry | Notes |
|---|---|---|
| `"minimum"` | `min`, `min_inclusive=True` | `ge` |
| `"exclusiveMinimum"` | `min`, `min_inclusive=False` | `gt` (JSON Schema 2020-12: numeric) |
| `"maximum"` | `max`, `max_inclusive=True` | `le` |
| `"exclusiveMaximum"` | `max`, `max_inclusive=False` | `lt` |

Emit `metadata.range` only when at least one of these keys is present.

### Length (`metadata.length`)

| JSON Schema key | `length` entry |
|---|---|
| `"minLength"` | `min` |
| `"maxLength"` | `max` |
| both equal | `equal` (drop `min`/`max`) |

### Pattern (`metadata.pattern`)

`"pattern"` key → `metadata.pattern` value verbatim.

---

## `is_load_only` / `is_dump_only`

Pydantic v2 has no direct equivalent. Both flags are always `False` for V1. `@computed_field`
(the closest dump-only analogue) lives in `model_computed_fields`, not `model_fields`, and is
out of scope.

---

## `is_supported`

Every field in `model_fields` that produces a recognised JSON Schema pattern is fully
supported. The only `is_supported=False` cases are:

- Unrecognised JSON Schema pattern (catch-all fallback).
- `anyOf` with more than one non-null member (true union type — not representable in the
  contract diff model).

---

## Default Values

`model_json_schema()` does not include default values. Read them directly from `model_fields`:

| Pydantic attribute | Condition | `metadata` key | Value |
|---|---|---|---|
| `field_info.default` | not `PydanticUndefined` | `load_default` | The default value |
| `field_info.default_factory` | not `None` | `load_default` | `"<factory>"` (not serialisable) |

Pydantic v2 does not distinguish load vs dump defaults — emitting under `load_default` is
consistent with what the Marshmallow parser produces for `field.load_default`.

---

## Parser Architecture

```
SchemaParser (ABC)      ← adapters/schema_parsers/parser.py  (unchanged)
├── MarshmallowParser   ← adapters/schema_parsers/marshmallow.py  (unchanged)
└── PydanticParser      ← adapters/schema_parsers/pydantic.py  (new)
```

`PydanticParser.__init__` lazy-imports `pydantic` — same pattern as `MarshmallowParser`.
The `ImportError` is caught and re-raised as `MissingDependencyError` in `factory.py`.

`annotated_types` is **not** imported — the `model_json_schema()` approach renders it
unnecessary.

---

## Full File Changeset

| File | Action |
|---|---|
| `contract_sentinel/domain/framework.py` | Add `PYDANTIC = "pydantic"`; add `hasattr(cls, "model_fields")` probe to `detect_framework` |
| `contract_sentinel/adapters/schema_parsers/pydantic.py` | **Create** — `PydanticParser` |
| `contract_sentinel/factory.py` | Add `case Framework.PYDANTIC` branch to `get_parser` |
| `pyproject.toml` | Add `pydantic = ["pydantic>=2.0,<3.0"]` optional dep; update `all`; add pydantic to dev group |
| `tests/unit/test_domain/test_framework.py` | Add `Framework.PYDANTIC` detection test; update `UnsupportedFrameworkError` message assertion |
| `tests/unit/test_factory.py` | Add `Framework.PYDANTIC` factory tests; update `UnsupportedFrameworkError` message assertion |
| `tests/integration/test_adapters/test_pydantic_parser.py` | **Create** — `TestPydanticParser` |
