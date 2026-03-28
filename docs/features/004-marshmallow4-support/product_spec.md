# Product Spec — Marshmallow 4 Support

**Feature slug:** `004-marshmallow4-support`
**Status:** `complete`
**Created:** 2026-03-28

---

## Problem

Contract Sentinel's marshmallow integration was pinned to `>=3.13,<4.0`. Teams upgrading
to marshmallow 4 could not adopt — or keep — Contract Sentinel without staying on ma3 or
maintaining a fork. Critically, the `<4.0` pin in `[project.optional-dependencies]` would
**downgrade** a user's marshmallow 4 installation on `pip install contract-sentinel[marshmallow]`.

---

## Goals

- Installing `contract-sentinel[marshmallow]` never downgrades or conflicts with the user's
  existing marshmallow installation, whether ma3 or ma4. ✅
- Marshmallow 4.x schemas parse correctly with zero user-facing changes. ✅
- Marshmallow 3 support is unchanged — existing ma3 users are unaffected. ✅

---

## Non-Goals (V1)

- Supporting marshmallow 3 and marshmallow 4 simultaneously in the same runtime environment.
- Supporting marshmallow 2.x or earlier — end-of-life.

---

## User-Facing Changes

None. The `@contract` decorator, CLI commands, and published JSON contract format are
identical across marshmallow versions.

---

## Acceptance Criteria

- [x] `pip install contract-sentinel[marshmallow]` with marshmallow 4 installed does not
  downgrade or conflict — constraint is `>=3.13,<5.0`.
- [x] `sentinel publish` against a marshmallow 4 codebase produces a valid contract JSON
  with correct field types, nullability flags, validators, and nested structure.
- [x] `List` fields resolve correctly under ma4 — `List.inner` is unchanged in ma4.2.3,
  no special handling required.
- [x] `Schema.unknown` defaults resolve correctly — `RAISE` / `EXCLUDE` / `INCLUDE` are
  all present and unchanged in ma4.2.3.
- [x] `just check` passes against the pinned ma4.2.3 — 303 tests pass.
