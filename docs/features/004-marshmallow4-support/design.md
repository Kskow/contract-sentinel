# Design — Marshmallow 4 Support

## Marshmallow 3 → 4: Breaking Changes That Hit Our Code

Only two marshmallow 4 changes require code modifications in Contract Sentinel.
Everything else is either irrelevant to us or already handled.

### Change 1 — `List.inner` renamed to `List.value_field`

In marshmallow 3, the inner element field of a `List` is accessed via `field.inner`.
In marshmallow 4 it is `field.value_field`, consistent with `Dict.value_field` and
`Mapping.value_field` which already used that name in ma3.

**Affected code:** `Marshmallow3Parser._resolve_list` — single attribute access.

### Change 2 — `Schema.unknown` default: `RAISE` → `EXCLUDE`

In marshmallow 3, a schema with no explicit `Meta.unknown` setting defaults to `RAISE`.
In marshmallow 4 the default is `EXCLUDE`. Our `_map_unknown` method reads the live
`schema_instance.unknown` attribute, so it automatically returns the correct
`UnknownFieldBehaviour` with no logic change needed. However, every integration test that
asserts `"unknown": "forbid"` against a schema with no explicit `Meta.unknown` will produce
`"unknown": "ignore"` when marshmallow 4 is installed. The test expectations must reflect
the version under test.

**Affected code:** test expectations only, not production logic.

### Changes That Do NOT Affect Our Code

| Ma4 change | Why it doesn't matter |
|---|---|
| `marshmallow.pprint` removed | We never call or import `pprint` |
| `missing` / `default` field kwargs removed | Our parser never passes these deprecated kwargs |
| `Mapping` cannot be directly instantiated | We only use `Mapping` in `isinstance` checks in the type_map — `Dict` is a subclass of `Mapping`, so the check still resolves correctly. `Dict` appears before `Mapping` in the map so any `Dict` instance is matched first anyway |
| `Number` field direct instantiation removed | We never put `Number` in the type-map |
| `Field` direct instantiation removed | Our fallback unknown-type path does `type(field).__name__` — no instantiation |
| `marshmallow.missing` sentinel | Still exported from `marshmallow.utils` and re-exported by `marshmallow`; our sentinel comparison in `_build_metadata` continues to work |

---

## Dependency Constraints: Published vs Dev

These are two entirely separate concerns with different audiences and different constraints.

### Published package (`[project.optional-dependencies]`)

This is what end users install. It must accept both ma3 and ma4:

```toml
[project.optional-dependencies]
marshmallow = ["marshmallow>=3.13,<5.0"]
all = ["boto3>=1.42.70", "marshmallow>=3.13,<5.0"]
```

`<5.0` guards against a hypothetical ma5 with unknown breaking changes. The wide `>=3.13`
floor means a user with either version can install `contract-sentinel[marshmallow]` without
any downgrade or conflict.

### Dev environment (`[dependency-groups]`)

Never published. Never seen by end users. Controls what the contributor's venv contains:

```toml
[dependency-groups]
dev = [
    "marshmallow>=3.13,<4.0",   # daily dev uses ma3 (pinned in uv.lock)
    ...
]
ma4 = [
    "marshmallow>=4.0,<5.0",    # used only for the ma4 test run
]

[tool.uv]
conflicts = [
    [{ group = "dev" }, { group = "ma4" }],
]
```

Declaring the groups as `conflicts` tells uv to resolve them independently. Both ma3 and ma4
are pinned in `uv.lock` — both test runs are fully reproducible. To advance the tested ma4
version: `uv lock --upgrade-package marshmallow`.

---

## Adapter Package Restructure

### Before

```
contract_sentinel/adapters/
    __init__.py
    contract_store.py          # ContractStore(ABC) + S3ContractStore
    schema_parser.py           # SchemaParser(ABC) + Marshmallow3Parser
```

### After

```
contract_sentinel/adapters/
    __init__.py
    contract_store.py                      # unchanged
    schema_parsers/
        __init__.py                        # re-exports public symbols
        schema_parser.py                   # SchemaParser(ABC) only
        marshmallow.py                     # Marshmallow3Parser + Marshmallow4Parser
```

This structure scales to future parsers (`pydantic.py`, `dataclasses.py`) without touching
the ABC or the factory interface. Each framework gets its own module; `__init__.py` provides
a stable import surface.

`_ResolvedFieldType` and `_TypeMapEntry` are private implementation helpers used only by the
marshmallow parsers — they stay in `marshmallow.py`.

### Import sites that change

| File | Old | New |
|---|---|---|
| `factory.py` (TYPE_CHECKING) | `adapters.schema_parser.SchemaParser` | `adapters.schema_parsers.schema_parser.SchemaParser` |
| `factory.py` (runtime) | `adapters.schema_parser.Marshmallow3Parser` | `adapters.schema_parsers.marshmallow.Marshmallow3/4Parser` |
| `tests/unit/test_factory.py` | `adapters.schema_parser.Marshmallow3Parser` | `adapters.schema_parsers.marshmallow.Marshmallow3Parser` |
| `tests/integration/.../test_schema_parser_ma3.py` | `adapters.schema_parser.Marshmallow3Parser` | `adapters.schema_parsers.marshmallow.Marshmallow3Parser` |

---

## Parser Architecture

### `Marshmallow4Parser` is a one-method subclass

`Marshmallow4Parser` extends `Marshmallow3Parser` and overrides **one method**: `_resolve_list`.
Everything else is inherited. Both classes live in `marshmallow.py`.

```
SchemaParser (ABC)                     ← schema_parsers/schema_parser.py
└── Marshmallow3Parser                 ← schema_parsers/marshmallow.py
    └── Marshmallow4Parser             ← schema_parsers/marshmallow.py
```

### Version detection in the factory

`factory.get_parser` keeps `Framework.MARSHMALLOW` as the single enum value. The user never
specifies which marshmallow version they're on. The factory reads the installed version via
`importlib.metadata.version("marshmallow")` and `packaging.version.Version(...).major`.
`packaging` is already a transitive dependency of marshmallow — no new dependency.

---

## Multi-Version Test Strategy

### Test file naming

```
tests/integration/test_adapters/
    test_schema_parser_ma3.py    # renamed from test_schema_parser.py
    test_schema_parser_ma4.py    # new
```

Symmetric names. Each file is self-contained and independently runnable.

### Separation mechanism: pytest marker

`test_schema_parser_ma4.py` carries a module-level marker:

```python
pytestmark = pytest.mark.ma4
```

The marker is registered in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["ma4: tests that require marshmallow 4"]
```

No `skipif` guards. Marker-based selection is explicit, lives with the test, and scales to
future `pydantic`, `dataclasses` markers without touching any recipe or config flag.

### Test runs

```bash
# ma3: full suite, excludes ma4-marked tests
uv run pytest tests/ -m "not ma4"

# ma4: only ma4-marked tests, marshmallow 4 injected from the ma4 dependency group
uv run --group ma4 pytest tests/ -m "ma4" -v
```

`uv run --group ma4` switches the marshmallow resolution to the ma4-pinned version from
`uv.lock` without affecting anything else in the environment.

### `just test` always runs both

```
test:
    docker compose run --rm app uv run pytest tests/ -m "not ma4"
    docker compose run --rm app uv run --group ma4 pytest tests/ -m "ma4" -v
```

There is no separate `just test-all`. A test run always covers both versions.
`just test-seq` is preserved for `--pdb` debugging (single sequential run, ma3 only).

### `TestMarshmallow4Parser` scope

The new class mirrors `TestMarshmallow3Parser` in structure. The only assertions that differ
are on schemas **without** an explicit `Meta.unknown`:

| Scenario | Ma3 assertion | Ma4 assertion |
|---|---|---|
| Schema with no `Meta.unknown` | `"unknown": "forbid"` | `"unknown": "ignore"` |

All other assertions (field types, formats, nullability, required, load/dump only, data_key,
validators, nested, dict, tuple, method, function, constant, enum) are identical and present
verbatim — the file must be runnable without any reference to the ma3 file.

---

## Full File Changeset

| File | Action |
|---|---|
| `pyproject.toml` | Update published constraint to `<5.0`; add `ma4` dev group; add `[tool.uv] conflicts`; register `ma4` pytest marker |
| `contract_sentinel/adapters/schema_parser.py` | **Delete** |
| `contract_sentinel/adapters/schema_parsers/__init__.py` | **Create** |
| `contract_sentinel/adapters/schema_parsers/schema_parser.py` | **Create** — SchemaParser ABC |
| `contract_sentinel/adapters/schema_parsers/marshmallow.py` | **Create** — both parsers |
| `contract_sentinel/factory.py` | Update imports + version-routing logic |
| `justfile` | Update `test` and `check` recipes |
| `tests/integration/test_adapters/test_schema_parser.py` | **Rename** → `test_schema_parser_ma3.py` + update import |
| `tests/unit/test_factory.py` | Update import path + add ma4 routing assertion |
| `tests/integration/test_adapters/test_schema_parser_ma4.py` | **Create** |
| `.github/workflows/quality.yml` | Add ma4 test step |

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `marshmallow.missing` removed in ma4 | Low — still in `marshmallow.utils` | Verify against actual ma4 install in TICKET-03; fall back to `marshmallow.utils.missing` if needed |
| `NaiveDateTime` / `AwareDateTime` removed in ma4 | Low — both still in ma4 `__all__` | Confirm during TICKET-03; add `hasattr` guard if removed |
| `packaging` not available in a user's environment | Very low — marshmallow itself imports it | Add `packaging` as explicit dep if TICKET-04 fails in CI |
| Ma4 introduces field renames beyond `List.inner` | Low | Review ma4 CHANGELOG in full during TICKET-03 before proceeding |
| `uv run --group ma4` includes dev group + ma4 group — conflict at install time | Low — `[tool.uv] conflicts` handles this | Verify `uv lock` succeeds and both versions appear in `uv.lock` in TICKET-01 |
