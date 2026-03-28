# Marshmallow 4 Support — Dev Tickets

**Feature slug:** `004-marshmallow4-support`
**Spec:** `docs/features/004-marshmallow4-support/product_spec.md`
**Design:** `docs/features/004-marshmallow4-support/design.md`
**Created:** 2026-03-28

---

## Architecture Notes

### Two separate constraint concerns

`[project.optional-dependencies]` is the published package contract — it must accept both
ma3 and ma4 (`>=3.13,<5.0`) so users are never downgraded. `[dependency-groups]` is
dev-only, never published — `dev` holds tooling only, `ma3` pins marshmallow 3, `ma4` pins
marshmallow 4. `ma3` and `ma4` are declared as conflicting so uv resolves and pins both
independently in `uv.lock`. `default-groups = ["dev", "ma3"]` gives contributors ma3 by
default without any extra flags.

### Adapter restructure

`adapters/schema_parser.py` is split into a `schema_parsers/` package. The ABC lives alone
in `schema_parser.py`; both marshmallow parsers live in `marshmallow.py`. This is the
foundational layout for future framework adapters (pydantic, dataclasses).

### Only two breaking ma4 changes require code

1. `List.inner` → `List.value_field` — `Marshmallow4Parser` overrides `_resolve_list` only.
2. `Schema.unknown` default `RAISE` → `EXCLUDE` — handled entirely in test expectations,
   no production logic change.

### Multi-version test separation: pytest marker

`test_schema_parser_ma4.py` carries `pytestmark = pytest.mark.ma4`. The ma3 run uses
`-m "not ma4"`, the ma4 run uses `-m "ma4"`. No `skipif`. No `--ignore`. The marker lives
with the test and scales to future version-specific test files without touching any recipe.

### Import sites changed by TICKET-02

| File | Change |
|---|---|
| `contract_sentinel/factory.py` | TYPE_CHECKING + runtime imports |
| `tests/unit/test_factory.py` | Import path |
| `tests/integration/test_adapters/test_schema_parser_ma3.py` | Renamed file + import |

### New files

| File | Purpose |
|---|---|
| `contract_sentinel/adapters/schema_parsers/__init__.py` | Re-exports public symbols |
| `contract_sentinel/adapters/schema_parsers/schema_parser.py` | SchemaParser ABC |
| `contract_sentinel/adapters/schema_parsers/marshmallow.py` | Marshmallow3Parser + Marshmallow4Parser |
| `tests/integration/test_adapters/test_schema_parser_ma4.py` | TestMarshmallow4Parser |

---

## Tickets

---

### TICKET-01 — Update `pyproject.toml`: published constraint, ma4 dev group, pytest marker ✅

**Depends on:** –
**Type:** Infra
**Status:** Done

**Goal:**
Establish the correct dependency constraints for both end users and the dev environment, and
register the `ma4` pytest marker so the test separation works from the start.

**Files to create / modify:**
- `pyproject.toml` — modify
- Run `uv lock` after changes

**Changes in detail:**

*Published extras — user-facing, no downgrade:*
```toml
[project.optional-dependencies]
marshmallow = ["marshmallow>=3.13,<5.0"]   # was <4.0
all = ["boto3>=1.42.70", "marshmallow>=3.13,<5.0"]   # was <4.0
```

*Dev groups — internal, never published:*

> **Implementation note:** The ticket originally placed `marshmallow>=3.13,<4.0` inside the
> `dev` group and declared `[dev, ma4]` as the conflicting pair. This caused `uv run --group
> ma4` to fail immediately because uv auto-includes `dev` (which carries `marshmallow<4.0`),
> making the conflict unresolvable at runtime.
>
> The fix: `dev` holds tooling only (no marshmallow). A dedicated `ma3` group holds the
> marshmallow 3 pin. `default-groups = ["dev", "ma3"]` preserves the daily-dev experience.
> The conflict is correctly declared between `ma3` ↔ `ma4` — the two things that actually
> conflict. Downstream invocations become:
> - ma3 run (default): `uv run pytest tests/ -m "not ma4"`
> - ma4 run: `uv run --no-group ma3 --group ma4 pytest tests/ -m "ma4"`

```toml
[dependency-groups]
dev = [
    # tooling only — no marshmallow here
    ...
]
ma3 = [
    "marshmallow>=3.13,<4.0",
]
ma4 = [
    "marshmallow>=4.0,<5.0",
]
```

*Conflict declaration — tells uv to resolve ma3 and ma4 independently:*
```toml
[tool.uv]
default-groups = ["dev", "ma3"]
conflicts = [
    [{ group = "ma3" }, { group = "ma4" }],
]
```

*Pytest marker registration:*
```toml
[tool.pytest.ini_options]
markers = ["ma4: tests that require marshmallow 4"]
```

**Done when:**
- [x] `[project.optional-dependencies]` reads `>=3.13,<5.0` in both `marshmallow` and `all`.
- [x] `[dependency-groups]` has a new `ma4` group with `marshmallow>=4.0,<5.0`.
- [x] `[tool.uv] conflicts` is declared between `ma3` and `ma4` groups.
- [x] `uv lock` succeeds and `uv.lock` contains pinned entries for both a marshmallow 3.x
  version (ma3 group, `3.26.2`) and a marshmallow 4.x version (ma4 group, `4.2.3`).
- [x] `uv run --no-group ma3 --group ma4 pytest --collect-only` resolves without dependency
  errors — 303 tests collected inside the app container.
- [x] `ma4` marker is registered in `[tool.pytest.ini_options]`.

---

### TICKET-02 — Restructure schema_parser adapter into `schema_parsers/` package ✅

**Depends on:** –
**Type:** Adapter
**Status:** Done

**Goal:**
Split `adapters/schema_parser.py` into a proper package that hosts the ABC and marshmallow
implementations separately. Zero logic changes — this is a pure structural refactor.

**Files created / modified:**
- `contract_sentinel/adapters/schema_parsers/__init__.py` — created (empty package marker, no re-exports)
- `contract_sentinel/adapters/schema_parsers/schema_parser.py` — created
- `contract_sentinel/adapters/schema_parsers/marshmallow.py` — created
- `contract_sentinel/adapters/schema_parser.py` — deleted
- `contract_sentinel/factory.py` — imports updated
- `contract_sentinel/services/publish.py` — import updated (not in original ticket scope but needed)
- `contract_sentinel/services/validate.py` — import updated (not in original ticket scope but needed)
- `tests/unit/test_factory.py` — import updated
- `tests/unit/test_services/test_publish.py` — import updated (not in original ticket scope but needed)
- `tests/unit/test_services/test_validate.py` — import updated (not in original ticket scope but needed)
- `tests/integration/test_adapters/test_schema_parser_ma3.py` — renamed + import updated

**Content split (deviations from ticket noted):**

`schema_parsers/schema_parser.py` receives:
- `SchemaParser(ABC)`
- `ResolvedFieldType` NamedTuple — kept here (not in `marshmallow.py`) so future parsers can reuse it
- `TypeMapEntry` NamedTuple — same rationale

> **Deviation:** The ticket placed `ResolvedFieldType` and `TypeMapEntry` in `marshmallow.py`.
> Moved to `schema_parser.py` so they're available to any future parser (pydantic, dataclasses)
> without importing from the marshmallow module.
>
> **Deviation:** The ticket called for `_ResolvedFieldType` / `_TypeMapEntry` (private names).
> Prefix removed — they're now public helpers intended for reuse across parser implementations.
>
> **Deviation:** `__init__.py` is an empty package marker. No re-exports — import the concrete
> class you need directly from its module.

`schema_parsers/marshmallow.py` receives:
- The `TYPE_CHECKING` block with marshmallow type imports
- `Marshmallow3Parser`

**Done when:**
- [x] `contract_sentinel/adapters/schema_parser.py` no longer exists.
- [x] `contract_sentinel/adapters/schema_parsers/` contains `__init__.py`, `schema_parser.py`,
  `marshmallow.py`.
- [x] `tests/integration/test_adapters/test_schema_parser_ma3.py` exists (renamed).
- [x] `uv run pytest tests/ -m "not ma4"` passes with zero failures — 303 passed.
- [x] `uv run ty check` passes with no new errors.

---

### TICKET-03 — Add `Marshmallow4Parser`

**Depends on:** TICKET-02
**Type:** Adapter

**Goal:**
Add `Marshmallow4Parser` to `marshmallow.py` and export it — a subclass of
`Marshmallow3Parser` that overrides `_resolve_list` to use `field.value_field`.

**Files to create / modify:**
- `contract_sentinel/adapters/schema_parsers/marshmallow.py` — modify (append class)
- `contract_sentinel/adapters/schema_parsers/__init__.py` — modify (add export)

**Implementation notes:**
- The class body is a single method override of `_resolve_list`.
- `field.value_field` is the ma4 attribute name for the inner element field of `List`.
- Before committing: read the marshmallow 4 CHANGELOG in full and confirm no field
  attribute renames exist beyond `List.inner`. Add overrides for any that do and open
  a follow-up ticket for each.
- Verify `marshmallow.missing` sentinel is still accessible in ma4 (`self._ma.missing`
  in `_build_metadata`). If removed, fall back to `marshmallow.utils.missing`.

**Done when:**
- [ ] `Marshmallow4Parser` exists in `marshmallow.py`, extends `Marshmallow3Parser`.
- [ ] `Marshmallow4Parser._resolve_list` accesses `field.value_field`, not `field.inner`.
- [ ] `Marshmallow4Parser` is in `schema_parsers/__init__.py` exports and `__all__`.
- [ ] `uv run ty check` passes with no new errors.

---

### TICKET-04 — Route factory to correct parser by marshmallow major version

**Depends on:** TICKET-03
**Type:** Adapter

**Goal:**
Update `factory.get_parser` to automatically select `Marshmallow3Parser` or
`Marshmallow4Parser` based on the installed marshmallow version, and update
`test_factory.py` to cover both routing paths.

**Files to create / modify:**
- `contract_sentinel/factory.py` — modify
- `tests/unit/test_factory.py` — modify

**Implementation notes:**
- Detect version: `importlib.metadata.version("marshmallow")` + `packaging.version.Version(...).major`.
- `packaging` is a transitive dep of marshmallow — no new dependency needed.
- Version detection and class selection live inside the `Framework.MARSHMALLOW` branch.
  No new public API is added.
- The `MissingDependencyError` guard is unchanged.

**`test_factory.py` changes:**
- `test_returns_marshmallow3_parser_for_marshmallow_framework`: mock
  `importlib.metadata.version` to return `"3.26.2"` → assert `isinstance(parser, Marshmallow3Parser)`.
- `test_marshmallow_parser_carries_the_supplied_repository`: same mock applied.
- Add `test_returns_marshmallow4_parser_when_ma4_is_installed`: mock version to `"4.0.0"`
  → assert `isinstance(parser, Marshmallow4Parser)`.
- `test_raises_missing_dependency_error_when_marshmallow_not_installed`: unchanged.

**Done when:**
- [ ] With ma3 mocked, `get_parser` returns `Marshmallow3Parser`.
- [ ] With ma4 mocked, `get_parser` returns `Marshmallow4Parser`.
- [ ] All tests in `test_factory.py` pass.
- [ ] `uv run ty check` passes.

---

### TICKET-05 — Update `just test`, `just check`, and CI for two-version test runs

**Depends on:** TICKET-01
**Type:** Infra

**Goal:**
Wire the two-step test invocation into `justfile` and CI so both marshmallow versions are
always verified — locally and on every push.

**Files to create / modify:**
- `justfile` — modify
- `.github/workflows/quality.yml` — modify

**`justfile` changes:**

```
# Run full test suite in parallel (-n auto via addopts)
test:
    docker compose run --rm app uv run pytest tests/ -m "not ma4"
    docker compose run --rm app uv run --group ma4 pytest tests/ -m "ma4" -v

# Run tests sequentially — use when debugging with --pdb
test-seq:
    docker compose run --rm app uv run pytest -n0

# Run tests with coverage report
test-cov:
    docker compose run --rm app uv run pytest tests/ -m "not ma4" --cov=contract_sentinel --cov-report=term-missing

# Full quality gate — mirrors CI
check:
    docker compose run --rm app sh -c "\
        uv run ruff check . && \
        uv run ruff format --check . && \
        uv run ty check && \
        uv run pytest tests/ -m 'not ma4' && \
        uv run --group ma4 pytest tests/ -m 'ma4' -v"
```

`test-seq` intentionally runs only the ma3 suite (`-m "not ma4"` via `addopts` is not set,
so it collects everything except ma4-marked tests naturally) — it is the escape hatch for
single-session debugging only.

**`quality.yml` changes:**

Replace the single `Test` step with two steps:

```yaml
- name: Test (ma3)
  run: uv run pytest tests/ -m "not ma4"

- name: Test (ma4)
  run: uv run --group ma4 pytest tests/ -m "ma4" -v
```

The LocalStack service already present in the job serves the ma3 step. The ma4 step makes
no AWS calls and needs no LocalStack.

**Done when:**
- [ ] `just test` runs both steps sequentially; the ma4 step exits with code 5 (no tests
  collected yet — expected before TICKET-06) and the recipe continues without error.
- [ ] `just check` includes both test steps after typecheck.
- [ ] `quality.yml` has two test steps: `Test (ma3)` and `Test (ma4)`.
- [ ] A CI run triggered at this point shows `Test (ma3)` green and `Test (ma4)` green
  (0 collected is a passing run in pytest terms for the ma4 step at this stage).

---

### TICKET-06 — Write `TestMarshmallow4Parser` integration tests

**Depends on:** TICKET-03, TICKET-04, TICKET-05
**Type:** Adapter

**Goal:**
Create `test_schema_parser_ma4.py` with a self-contained `TestMarshmallow4Parser` class and
confirm `just test` passes both steps end-to-end with zero failures.

**Files to create / modify:**
- `tests/integration/test_adapters/test_schema_parser_ma4.py` — create

**Coverage requirements:**

Mirror every test in `TestMarshmallow3Parser`. The only assertions that differ are those on
schemas without an explicit `Meta.unknown`:

| Scenario | Ma3 | Ma4 |
|---|---|---|
| Any schema without `Meta.unknown` | `"unknown": "forbid"` | `"unknown": "ignore"` |

All other assertions — types, formats, nullability, required, load/dump only, data_key, all
validators (Length, Range, Regexp, OneOf, And), nested, dict, tuple, method, function,
constant, enum, `unknown_policy_inherited_from_parent_schema` — are identical and must be
present verbatim. The file must be runnable in total isolation from `test_schema_parser_ma3.py`.

**Implementation notes:**
- Module-level: `pytestmark = pytest.mark.ma4`.
- Imports `Marshmallow4Parser` from `contract_sentinel.adapters.schema_parsers.marshmallow`.
- No `skipif` markers anywhere in this file.
- `uv run --group ma4 pytest` installs marshmallow 4, so `field.value_field` is the live
  attribute — `List` tests exercise the override for real.

**Done when:**
- [ ] `test_schema_parser_ma4.py` exists with `pytestmark = pytest.mark.ma4` and
  `TestMarshmallow4Parser` covering all scenarios listed above.
- [ ] `just test` runs both steps to completion with zero failures and zero errors.
- [ ] `just test` (ma3 step) continues to pass `test_schema_parser_ma3.py` unmodified.
- [ ] CI passes both `Test (ma3)` and `Test (ma4)` steps green.
