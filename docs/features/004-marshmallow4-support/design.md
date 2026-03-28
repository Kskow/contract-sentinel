# Design — Marshmallow 4 Support

## Marshmallow 3 → 4: Compatibility Findings

The feature was originally designed around two assumed breaking changes. Both were verified
against the actual ma4.2.3 release before any code was written.

### Finding 1 — `List.inner` was NOT renamed

The design assumed `List.inner` was renamed to `List.value_field`. Verified from source:
`self.inner` is still the attribute name in ma4.2.3. No override needed.

### Finding 2 — `Schema.unknown` default did NOT change

The design assumed the default changed from `RAISE` to `EXCLUDE`. Verified at runtime:
both ma3.26.2 and ma4.2.3 default to `RAISE` when no `Meta.unknown` is set.

### Full Compatibility Matrix (verified at runtime against ma4.2.3)

| Concern | Status | Notes |
|---|---|---|
| `List.inner` | Unchanged | Still `inner`, not `value_field` |
| `Schema.unknown` default | Unchanged | Still `RAISE` in both versions |
| `marshmallow.missing` sentinel | Present | Same object as `marshmallow.utils.missing` |
| `NaiveDateTime` / `AwareDateTime` | Present | Both in ma4 `__all__` |
| `Enum`, `Constant`, `Tuple`, `Method`, `Function` | Present | All field types intact |
| All IP fields | Present | `IPv4`, `IPv6`, `IP`, `IPv4Interface`, etc. |
| `RAISE` / `EXCLUDE` / `INCLUDE` constants | Present | Unchanged |
| `marshmallow.pprint` | Removed | Never used by our code |
| `missing=` / `default=` field kwargs | Removed in ma4 | We read `field.load_default` / `field.dump_default`, which ma3 normalises from the old kwargs internally |

**Conclusion:** `MarshmallowParser` (formerly `Marshmallow3Parser`) works correctly against
both ma3 and ma4 with zero code changes. A separate `Marshmallow4Parser` is not needed.

---

## Dependency Constraints: Published vs Dev

### Published package (`[project.optional-dependencies]`)

This is what end users install. It accepts both ma3 and ma4:

```toml
[project.optional-dependencies]
marshmallow = ["marshmallow>=3.13,<5.0"]
all = ["boto3>=1.42.70", "marshmallow>=3.13,<5.0"]
```

`<5.0` guards against a hypothetical ma5 with unknown breaking changes. The `>=3.13` floor
means a user with either version installs without a downgrade or conflict.

### Dev environment (`[dependency-groups]`)

```toml
[dependency-groups]
dev = [
    "marshmallow>=3.13,<5.0",
    ...
]
```

A single group, no conflicts. `uv.lock` pins `4.2.3` (latest satisfying version).
Contributors run ma4 by default — intentional, since ma4 is the current release and
our code is verified to work identically across both versions.

---

## Adapter Package Restructure

### Before

```
contract_sentinel/adapters/
    __init__.py
    contract_store.py        # ContractStore(ABC) + S3ContractStore
    schema_parser.py         # SchemaParser(ABC) + MarshmallowParser
```

### After

```
contract_sentinel/adapters/
    __init__.py
    contract_store.py                  # unchanged
    schema_parsers/
        __init__.py                    # empty package marker
        parser.py                      # SchemaParser(ABC) + ResolvedFieldType + TypeMapEntry
        marshmallow.py                 # MarshmallowParser
```

`ResolvedFieldType` and `TypeMapEntry` live in `parser.py` (not `marshmallow.py`) so future
parsers (`pydantic.py`, `dataclasses.py`) can reuse them without importing from the marshmallow
module. Both are public — the `_` prefix was removed.

`__init__.py` is an empty package marker. No re-exports — callers import directly from the
module they need.

### Import sites changed

| File | Old | New |
|---|---|---|
| `factory.py` (TYPE_CHECKING) | `adapters.schema_parser.SchemaParser` | `adapters.schema_parsers.parser.SchemaParser` |
| `factory.py` (runtime) | `adapters.schema_parser.MarshmallowParser` | `adapters.schema_parsers.marshmallow.MarshmallowParser` |
| `services/publish.py` | `adapters.schema_parser.SchemaParser` | `adapters.schema_parsers.parser.SchemaParser` |
| `services/validate.py` | `adapters.schema_parser.SchemaParser` | `adapters.schema_parsers.parser.SchemaParser` |
| `tests/unit/test_factory.py` | `adapters.schema_parser.MarshmallowParser` | `adapters.schema_parsers.marshmallow.MarshmallowParser` |
| `tests/unit/test_services/test_publish.py` | `adapters.schema_parser.SchemaParser` | `adapters.schema_parsers.parser.SchemaParser` |
| `tests/unit/test_services/test_validate.py` | `adapters.schema_parser.SchemaParser` | `adapters.schema_parsers.parser.SchemaParser` |
| `tests/integration/.../test_schema_parser.py` | `adapters.schema_parser.MarshmallowParser` | `adapters.schema_parsers.marshmallow.MarshmallowParser` |

---

## Parser Architecture

```
SchemaParser (ABC)      ← schema_parsers/parser.py
└── MarshmallowParser   ← schema_parsers/marshmallow.py  (handles ma3 + ma4)
```

A single parser class handles both marshmallow versions. No version detection in the factory,
no subclass hierarchy. If a future ma4.x or ma5 release introduces a real breaking change,
`MarshmallowParser` is the right place to add conditional logic or a subclass.

---

## Full File Changeset

| File | Action |
|---|---|
| `pyproject.toml` | Published constraint widened to `<5.0`; dev group updated to `>=3.13,<5.0` |
| `contract_sentinel/adapters/schema_parser.py` | **Deleted** |
| `contract_sentinel/adapters/schema_parsers/__init__.py` | **Created** — empty package marker |
| `contract_sentinel/adapters/schema_parsers/parser.py` | **Created** — `SchemaParser` ABC + `ResolvedFieldType` + `TypeMapEntry` |
| `contract_sentinel/adapters/schema_parsers/marshmallow.py` | **Created** — `MarshmallowParser` |
| `contract_sentinel/factory.py` | Import paths updated |
| `contract_sentinel/services/publish.py` | Import path updated |
| `contract_sentinel/services/validate.py` | Import path updated |
| `tests/integration/test_adapters/test_schema_parser.py` | Renamed from `test_schema_parser.py`; class renamed to `TestMarshmallowParser` |
| `tests/unit/test_factory.py` | Import path + class reference updated |
| `tests/unit/test_services/test_publish.py` | Import path updated |
| `tests/unit/test_services/test_validate.py` | Import path updated |
