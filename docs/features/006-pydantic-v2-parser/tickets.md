# Pydantic v2 Parser — Dev Tickets

**Feature slug:** `006-pydantic-v2-parser`
**Spec:** `docs/features/006-pydantic-v2-parser/product_spec.md`
**Design:** `docs/features/006-pydantic-v2-parser/design.md`
**Created:** 2026-03-29

---

## Architecture Notes

### Adapter boundary

`PydanticParser` sits behind the existing `SchemaParser(ABC)` interface. No service, CLI, or
rule code changes. The only wiring points are `domain/framework.py` (detection) and
`factory.py` (instantiation).

### Data flow

```
@contract BaseModel subclass
  → detect_framework()          # hasattr(cls, "model_fields") probe
  → factory.get_parser()        # case Framework.PYDANTIC → PydanticParser(repository)
  → PydanticParser.parse(cls)
      ├── cls.model_json_schema(mode='serialization')   # full type + constraint resolution
      ├── _build_class_registry(cls)                    # {ClassName: cls} for model_config lookup
      └── _parse_property(name, prop_schema, defs, registry, required_set)
            ├── anyOf unwrap          → is_nullable
            ├── $ref resolve          → nested fields + unknown
            ├── type/format map       → ContractField.type + metadata.format
            ├── enum/Literal          → metadata.allowed_values
            ├── list/dict items       → metadata.item_type / value_type / fields
            ├── constraint keys       → metadata.range / length / pattern
            └── model_fields lookup   → is_required, load_default
  → ContractSchema
```

### New files

- `contract_sentinel/adapters/schema_parsers/pydantic.py`
- `tests/integration/test_adapters/test_pydantic_parser.py`

### Patterns to reuse

- `ResolvedFieldType` and `TypeMapEntry` from `adapters/schema_parsers/parser.py` are
  **not used** — the JSON Schema output approach does not need a field-class type map.
- `UnknownFieldBehaviour`, `ContractField`, `ContractSchema` from `domain/` are used
  identically to the Marshmallow parser.
- `MissingDependencyError` / lazy import pattern in `factory.py` — copy exactly.

### Distributed systems / compatibility notes

- No IAM or environment variable changes.
- `annotated_types` is **not** imported — the `model_json_schema()` approach makes it
  unnecessary.
- The published JSON contract format is unchanged — the Pydantic parser produces the same
  `ContractSchema.to_dict()` structure that existing rules and stores already consume.

---

## Tickets

### TICKET-01 — Add `Framework.PYDANTIC` and update `detect_framework`

**Depends on:** –
**Type:** Domain

**Goal:**
Make the domain layer aware of Pydantic v2 as a supported framework and detect it from a class
attribute probe that requires no pydantic import.

**Files to create / modify:**
- `contract_sentinel/domain/framework.py` — modify
- `tests/unit/test_domain/test_framework.py` — modify

**Done when:**
- [ ] `Framework.PYDANTIC = "pydantic"` is present in the `Framework` `StrEnum`.
- [ ] `detect_framework` checks `hasattr(cls, "model_fields")` **before** the Marshmallow
  probe and returns `Framework.PYDANTIC` when the check passes.
- [ ] `detect_framework` does **not** import pydantic at any point.
- [ ] The `UnsupportedFrameworkError` message produced by `detect_framework` now reads
  `"Supported frameworks: marshmallow, pydantic."` (automatic via `', '.join(Framework)`).
- [ ] A new test asserts `detect_framework` returns `Framework.PYDANTIC` for a class that has
  `model_fields` as a class attribute (no real pydantic import needed — a stub class suffices).
- [ ] The existing `UnsupportedFrameworkError` message assertion in `test_framework.py` is
  updated to match the new two-framework string.

---

### TICKET-02 — `PydanticParser` — core field parsing

**Depends on:** TICKET-01
**Type:** Adapter

**Goal:**
Implement `PydanticParser` with `parse()`, covering the top-level model schema, per-field
wire name resolution, `is_required`, `is_nullable` (via `anyOf` unwrap), `unknown` policy,
and default value extraction. Type resolution covers leaf types and their formats only —
structural types (nested models, lists, dicts) are handled in TICKET-03.

**Files to create / modify:**
- `contract_sentinel/adapters/schema_parsers/pydantic.py` — create

**Done when:**
- [ ] `PydanticParser(SchemaParser)` exists with `__init__(self, repository: str)` that
  lazy-imports `pydantic` (import inside `__init__`, not at module level).
- [ ] `parse(cls)` calls `cls.model_json_schema(mode='serialization')`, reads `"properties"`
  and `"required"` from the output, and returns a `ContractSchema`.
- [ ] `unknown` is read from `cls.model_config.get('extra')`: `None` / `'ignore'` → `IGNORE`,
  `'forbid'` → `FORBID`, `'allow'` → `ALLOW`. Verify the `None` default at runtime and note
  the finding in a code comment.
- [ ] Wire name is the property key from `"properties"` (Pydantic already applies
  `serialization_alias > alias` in `mode='serialization'` output).
- [ ] `is_required` is `True` when the property key appears in the `"required"` array.
- [ ] `is_nullable` is `True` when the property schema is `{"anyOf": [T, {"type": "null"}]}`;
  the non-null member is unwrapped and used as the effective schema.
- [ ] A `anyOf` with more than one non-null member maps to `type="any"`, `is_supported=False`.
- [ ] `load_default` is added to `metadata` when `field_info.default` is not
  `PydanticUndefined`; `"<factory>"` is used when `field_info.default_factory` is not `None`.
- [ ] `is_load_only` and `is_dump_only` are always `False`.
- [ ] All leaf JSON Schema type/format combinations in the design's translation table are
  handled: `string`, `string+date-time`, `string+date`, `string+time`, `string+uuid`,
  `string+email`, `string+uri`, `string+ipv4`, `string+ipv6`, `integer`, `number`,
  `boolean`, `any` (empty schema `{}`).
- [ ] Unrecognised patterns map to `type="string"`, `format=<title_lower or "unknown">`,
  `is_supported=False`.

---

### TICKET-03 — `PydanticParser` — structural types, `$ref` resolution, `enum`/`Literal`

**Depends on:** TICKET-02
**Type:** Adapter

**Goal:**
Extend `PydanticParser` to handle nested `BaseModel` fields (via `$ref`/`$defs`), `list[T]`,
`dict[K, V]`, `Literal`, and `Enum` — everything that produces nested `fields`, `item_type`,
`value_type`, or `allowed_values`.

**Files to create / modify:**
- `contract_sentinel/adapters/schema_parsers/pydantic.py` — modify

**Done when:**
- [ ] `_build_class_registry(cls)` shallow-walks `model_fields` of `cls` (and recursively of
  any nested `BaseModel`) to build a `dict[str, type]` keyed by `cls.__name__`.
- [ ] `_resolve_ref(ref, defs)` splits `"#/$defs/Name"` on `"/"` and returns `defs["Name"]`;
  unknown refs map to `type="any"`, `is_supported=False`.
- [ ] A `$ref` property schema resolves to `type="object"`, a populated `fields` list (via
  recursive `_parse_property` calls on the resolved schema's `"properties"`), and `unknown`
  read from the class registry (defaults to `IGNORE` when the class is absent).
- [ ] `{"type": "array", "items": <primitive_schema>}` → `type="array"`,
  `metadata.item_type = <type string>`.
- [ ] `{"type": "array", "items": {"$ref": …}}` → `type="array"`, nested `fields` + `unknown`.
- [ ] `{"type": "object", "additionalProperties": <primitive_schema>}` → `type="object"`,
  `metadata.key_type="string"`, `metadata.value_type = <type string>`.
- [ ] `{"type": "object", "additionalProperties": {"$ref": …}}` → `type="object"`,
  `metadata.key_type="string"`, nested `fields` + `unknown`.
- [ ] `{"enum": ["a", "b"]}` (all-string values) → `type="string"`, `format="enum"`,
  `metadata.allowed_values = ["a", "b"]`.
- [ ] `{"enum": [1, 2, 3]}` (all-integer values) → `type="integer"`,
  `metadata.allowed_values = [1, 2, 3]`.
- [ ] `{"enum": […]}` with mixed Python types → `type="any"`, `metadata.allowed_values`,
  `is_supported=False`.
- [ ] An inline `{"type": "object", "properties": {…}}` (no `$ref`) is handled the same as a
  resolved ref — parse its properties recursively with `unknown=IGNORE` as the fallback.

---

### TICKET-04 — `PydanticParser` — constraint metadata extraction

**Depends on:** TICKET-03
**Type:** Adapter

**Goal:**
Extract range, length, and pattern constraints from JSON Schema keywords on the property
schema and populate `metadata.range`, `metadata.length`, and `metadata.pattern`.

**Files to create / modify:**
- `contract_sentinel/adapters/schema_parsers/pydantic.py` — modify

**Done when:**
- [ ] `"minimum"` → `metadata.range.min`, `min_inclusive=True`.
- [ ] `"exclusiveMinimum"` → `metadata.range.min`, `min_inclusive=False`.
- [ ] `"maximum"` → `metadata.range.max`, `max_inclusive=True`.
- [ ] `"exclusiveMaximum"` → `metadata.range.max`, `max_inclusive=False`.
- [ ] `metadata.range` is only emitted when at least one of the four keys is present.
- [ ] `"minLength"` → `metadata.length.min`.
- [ ] `"maxLength"` → `metadata.length.max`.
- [ ] When `"minLength" == "maxLength"`, emit `metadata.length = {"equal": N}` instead.
- [ ] `metadata.length` is only emitted when at least one of the two keys is present.
- [ ] `"pattern"` → `metadata.pattern` (string, verbatim).
- [ ] Constraints are extracted **after** `anyOf` unwrapping — constraint keys live on the
  unwrapped schema, not on the `anyOf` wrapper.

---

### TICKET-05 — Factory wiring and `pyproject.toml` dependency

**Depends on:** TICKET-04
**Type:** Infra / Adapter

**Goal:**
Wire `PydanticParser` into the factory, add the `pydantic` optional dependency to
`pyproject.toml`, and update the unit tests that assert on `UnsupportedFrameworkError`
messages now that two frameworks are listed.

**Files to create / modify:**
- `contract_sentinel/factory.py` — modify
- `pyproject.toml` — modify
- `tests/unit/test_factory.py` — modify

**Done when:**
- [ ] `pyproject.toml` has a `pydantic = ["pydantic>=2.0,<3.0"]` entry under
  `[project.optional-dependencies]`.
- [ ] `pydantic>=2.0,<3.0` is added to the `all` optional dependency group.
- [ ] `pydantic>=2.0,<3.0` is added to the `[dependency-groups] dev` list.
- [ ] `case Framework.PYDANTIC` in `get_parser()` lazy-imports `PydanticParser`, catches
  `ImportError`, and raises `MissingDependencyError` with the message:
  `"framework 'pydantic' requires the pydantic extra.\nInstall it with: pip install contract-sentinel[pydantic]"`.
- [ ] The existing `test_raises_unsupported_framework_error_with_descriptive_message` test in
  `test_factory.py` is updated — the message now ends with `"marshmallow, pydantic."`.
- [ ] A new test asserts `get_parser(Framework.PYDANTIC, "svc")` returns a `PydanticParser`
  instance.
- [ ] A new test asserts `get_parser(Framework.PYDANTIC, "order-service")._repository` is
  `"order-service"`.
- [ ] A new test asserts `MissingDependencyError` is raised when `pydantic` is absent from
  `sys.modules` (use `monkeypatch.setitem(sys.modules, "pydantic", None)`).
- [ ] `just check` passes (`uv run` picks up the newly added pydantic dev dependency).

---

### TICKET-06 — Integration tests for `PydanticParser`

**Depends on:** TICKET-05
**Type:** Adapter

**Goal:**
Write the full integration test suite for `PydanticParser`, covering every translation rule
documented in `design.md` — one focused test per behaviour.

**Files to create / modify:**
- `tests/integration/test_adapters/test_pydantic_parser.py` — create

**Done when:**
- [ ] `TestPydanticParser` class exists.
- [ ] `@contract` decorator attaches `__contract__` to a `BaseModel` subclass without error.
- [ ] Test for each primitive type and its format: `str`, `int`, `float`, `bool`, `Decimal`,
  `datetime`, `date`, `time`, `timedelta`, `UUID`, `bytes`, `EmailStr`, `HttpUrl`,
  `IPv4Address`, `IPv6Address`, `Any`.
- [ ] `Optional[str]` / `str | None` sets `is_nullable=True` and `type="string"`.
- [ ] A required field (no default) has `is_required=True`; a field with a default has
  `is_required=False`.
- [ ] `load_default` appears in metadata when `Field(default=…)` is set.
- [ ] `load_default="<factory>"` appears in metadata when `Field(default_factory=…)` is set.
- [ ] `model_config = ConfigDict(extra='forbid')` maps to `unknown="forbid"`.
- [ ] `model_config = ConfigDict(extra='allow')` maps to `unknown="allow"`.
- [ ] Default (no `extra` in config) maps to `unknown="ignore"`.
- [ ] Wire name uses `serialization_alias` when set, falling back to `alias`, then field name.
- [ ] Nested `BaseModel` field produces `type="object"` with correct nested `fields` list and
  `unknown` from the nested model's `model_config`.
- [ ] `list[str]` produces `type="array"`, `metadata.item_type="string"`.
- [ ] `list[NestedModel]` produces `type="array"` with nested `fields` and `unknown`.
- [ ] `dict[str, int]` produces `type="object"`, `metadata.key_type="string"`,
  `metadata.value_type="integer"`.
- [ ] `dict[str, NestedModel]` produces `type="object"`, `metadata.key_type="string"`, nested
  `fields`, `unknown`.
- [ ] `Literal["a", "b"]` produces `type="string"`, `format="enum"`,
  `metadata.allowed_values=["a", "b"]`.
- [ ] `Literal[1, 2]` produces `type="integer"`, `metadata.allowed_values=[1, 2]`.
- [ ] `enum.Enum` subclass (string values) produces `type="string"`, `format="enum"`,
  `metadata.allowed_values`.
- [ ] `Field(ge=0, le=100)` → `metadata.range = {"min": 0, "min_inclusive": True, "max": 100, "max_inclusive": True}`.
- [ ] `Field(gt=0)` → `metadata.range = {"min": 0, "min_inclusive": False}`.
- [ ] `Field(min_length=1, max_length=50)` → `metadata.length = {"min": 1, "max": 50}`.
- [ ] `Field(min_length=5, max_length=5)` → `metadata.length = {"equal": 5}`.
- [ ] `Field(pattern=r"^\d+$")` → `metadata.pattern = r"^\d+$"`.
- [ ] `str | int` (non-nullable union) maps to `type="any"`, `is_supported=False`.
