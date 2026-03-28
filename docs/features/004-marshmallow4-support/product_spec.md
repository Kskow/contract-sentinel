# Product Spec — Marshmallow 4 Support

**Feature slug:** `004-marshmallow4-support`
**Status:** `ready-for-dev`
**Created:** 2026-03-28

---

## Problem

Contract Sentinel's marshmallow integration is pinned to `>=3.13,<4.0`. Marshmallow 4 is a
released major version with a small but breaking API surface. Teams upgrading their projects to
marshmallow 4 cannot adopt — or keep — Contract Sentinel without either:

- Staying on marshmallow 3 indefinitely, or
- Maintaining a fork.

Neither is acceptable for an open-source tool that aims to be easy to drop into any Python
project. Critically, the current `<4.0` pin in `[project.optional-dependencies]` would
**downgrade** a user's marshmallow 4 installation the moment they run
`pip install contract-sentinel[marshmallow]`.

---

## Goals

- Support marshmallow 4.x schemas with zero changes to user-facing code (same `@contract`
  decorator, same `sentinel publish` CLI, same canonical contract JSON format).
- Installing `contract-sentinel[marshmallow]` never downgrades or conflicts with the user's
  existing marshmallow installation, whether ma3 or ma4.
- Parser selection is **automatic** — the tool detects the installed marshmallow major version
  at runtime and routes to the correct parser. Users do not configure this.
- Marshmallow 3 support is **unchanged** — existing ma3 users are unaffected.
- Both marshmallow versions are verified on every CI run and locally via `just test`, with
  both versions pinned reproducibly in `uv.lock`.

---

## Non-Goals (V1)

- Supporting marshmallow 3 and marshmallow 4 installed simultaneously in the same runtime
  environment — Python does not allow two versions of the same package.
- Supporting marshmallow 2.x or earlier — these are end-of-life.

---

## User-Facing Changes

None. The `@contract` decorator, CLI commands, and published JSON contract format are
identical across marshmallow versions.

The only observable difference is that marshmallow 4 schemas **without** an explicit
`Meta.unknown` setting now default to `EXCLUDE` (i.e., `"unknown": "ignore"` in the contract
JSON) instead of `RAISE` (`"unknown": "forbid"`). This reflects marshmallow 4's own behaviour
change and is correct — it is not a Contract Sentinel regression.

---

## Acceptance Criteria

- [ ] `pip install contract-sentinel[marshmallow]` with marshmallow 4 already installed does
  not downgrade or conflict — the constraint is `>=3.13,<5.0`.
- [ ] Running `sentinel publish` against a marshmallow 4 codebase produces a valid contract
  JSON file with the correct field types, nullability flags, validators, and nested structure.
- [ ] `List(String())` fields are correctly resolved under ma4 (the `List.inner` →
  `List.value_field` rename is handled).
- [ ] `Schema.unknown` defaults are correctly resolved for both ma3 (`RAISE` → `"forbid"`)
  and ma4 (`EXCLUDE` → `"ignore"`).
- [ ] Both marshmallow 3 and marshmallow 4 are pinned in `uv.lock` via conflicting dependency
  groups — the tested versions are deterministic and visible in git.
- [ ] `just test` verifies both versions: ma3 full suite + ma4 schema parser suite.
- [ ] CI verifies both versions on every push and pull request.

---

## Out of Scope

- Pydantic support — separate feature.
- AI Semantic Audit — separate feature.
