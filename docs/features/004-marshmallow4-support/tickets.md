# Marshmallow 4 Support — Dev Tickets

**Feature slug:** `004-marshmallow4-support`
**Spec:** `docs/features/004-marshmallow4-support/product_spec.md`
**Design:** `docs/features/004-marshmallow4-support/design.md`
**Created:** 2026-03-28
**Status:** Complete

---

## Architecture Notes

### Single parser covers both versions

Verified against ma4.2.3: no API differences between ma3 and ma4 affect our code.
`MarshmallowParser` handles both versions without branching or subclassing.

### Adapter restructure

`adapters/schema_parser.py` was split into a `schema_parsers/` package:

- `parser.py` — `SchemaParser` ABC + `ResolvedFieldType` + `TypeMapEntry`
- `marshmallow.py` — `MarshmallowParser`
- `__init__.py` — empty package marker

`ResolvedFieldType` and `TypeMapEntry` live in `parser.py` so future parsers
(`pydantic.py`, `dataclasses.py`) can reuse them without depending on the marshmallow module.

### Import sites changed

| File | Change |
|---|---|
| `contract_sentinel/factory.py` | Import paths updated |
| `contract_sentinel/services/publish.py` | Import path updated |
| `contract_sentinel/services/validate.py` | Import path updated |
| `tests/unit/test_factory.py` | Import path updated |
| `tests/unit/test_services/test_publish.py` | Import path updated |
| `tests/unit/test_services/test_validate.py` | Import path updated |
| `tests/integration/test_adapters/test_schema_parser.py` | Import + class renamed |

---

## Tickets

---

### TICKET-01 — Update `pyproject.toml`: widen published constraint ✅

**Type:** Infra
**Status:** Done

**Goal:**
Widen the marshmallow optional dependency from `<4.0` to `<5.0` so users on ma4 are never
downgraded when installing `contract-sentinel[marshmallow]`.

**Changes:**

```toml
[project.optional-dependencies]
marshmallow = ["marshmallow>=3.13,<5.0"]   # was <4.0
all = ["boto3>=1.42.70", "marshmallow>=3.13,<5.0"]   # was <4.0

[dependency-groups]
dev = [
    "marshmallow>=3.13,<5.0",   # was <4.0; uv.lock pins 4.2.3
    ...
]
```

**Done when:**
- [x] `[project.optional-dependencies]` reads `>=3.13,<5.0` in both `marshmallow` and `all`.
- [x] `[dependency-groups] dev` reads `>=3.13,<5.0`.
- [x] `uv lock` succeeds — `uv.lock` pins `marshmallow 4.2.3`.

---

### TICKET-02 — Restructure schema_parser adapter into `schema_parsers/` package ✅

**Type:** Adapter
**Status:** Done

**Goal:**
Split `adapters/schema_parser.py` into a proper package. Zero logic changes.

**Files created / modified:**
- `contract_sentinel/adapters/schema_parsers/__init__.py` — created (empty package marker)
- `contract_sentinel/adapters/schema_parsers/parser.py` — created (`SchemaParser` ABC + `ResolvedFieldType` + `TypeMapEntry`)
- `contract_sentinel/adapters/schema_parsers/marshmallow.py` — created (`MarshmallowParser`)
- `contract_sentinel/adapters/schema_parser.py` — deleted
- All import sites updated (see Architecture Notes above)

**Deviations from original design:**
- `parser.py` (not `schema_parser.py`) — eliminates the `schema_parsers/schema_parser.py` redundancy
- `ResolvedFieldType` / `TypeMapEntry` live in `parser.py`, not `marshmallow.py` — shared helpers for future parsers
- Both made public (no `_` prefix)
- `__init__.py` is an empty package marker — no re-exports

**Done when:**
- [x] `contract_sentinel/adapters/schema_parser.py` no longer exists.
- [x] `contract_sentinel/adapters/schema_parsers/` contains `__init__.py`, `parser.py`, `marshmallow.py`.
- [x] `just check` passes with zero failures — 303 passed.

---

### TICKET-03 — Add `MarshmallowParser` (replaces planned Marshmallow3/4Parser split) ✅

**Type:** Adapter
**Status:** Done

**Original goal:** Add `Marshmallow4Parser` as a subclass of `Marshmallow3Parser` overriding
`_resolve_list` to use `field.value_field`.

**What actually happened:** Full runtime verification against ma4.2.3 found no API differences
requiring a separate class. See `design.md` for the full compatibility matrix.

**Changes made:**
- `Marshmallow3Parser` renamed to `MarshmallowParser`
- Docstring updated to explain ma3/ma4 compatibility and why no split is needed
- No `Marshmallow4Parser` created

**Done when:**
- [x] `MarshmallowParser` exists in `marshmallow.py`, handles both ma3 and ma4.
- [x] `just check` passes — 303 passed.

---

### TICKET-04 — Route factory by marshmallow major version ~~cancelled~~

**Status:** Not needed — single `MarshmallowParser` covers both versions. No version
detection required in the factory.

---

### TICKET-05 — Two-version CI test runs ~~cancelled~~

**Status:** Not needed — `MarshmallowParser` is identical across versions. Running the
test suite once (against the pinned ma4.2.3) provides complete coverage. A second run
against ma3 would produce identical results.

---

### TICKET-06 — Write `TestMarshmallow4Parser` ~~cancelled~~

**Status:** Not needed — behaviour is identical across versions. `TestMarshmallowParser`
in `test_schema_parser.py` covers both.
