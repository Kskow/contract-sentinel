# Product Spec — Pydantic v2 Parser

**Feature slug:** `006-pydantic-v2-parser`
**Status:** `ready-for-dev`
**Created:** 2026-03-29

---

## Problem

Contract Sentinel only supports Marshmallow schemas. Teams using Pydantic v2 — the dominant
validation library in the Python ecosystem — cannot adopt Contract Sentinel without migrating
their entire schema layer to Marshmallow. That is a non-starter for most real projects.

---

## Goals

- Teams using Pydantic v2 `BaseModel` subclasses can decorate them with `@contract` and run
  `sentinel publish` / `sentinel validate` without any changes to their Pydantic schema code.
- The published contract JSON format is identical to what Marshmallow produces — no downstream
  rule, store, or CLI changes are needed.
- Installing `contract-sentinel[pydantic]` never conflicts with or downgrades a user's existing
  `pydantic` installation.
- Pydantic v1 is explicitly out of scope — it is end-of-life and uses a different API
  (`__fields__` instead of `model_fields`).

---

## Non-Goals (V1)

- Pydantic v1 support.
- `@computed_field` (runtime-computed, not statically introspectable).
- Pydantic `RootModel` (no named fields — out of scope for contract diffing).
- Custom `@field_validator` / `@model_validator` logic — validators are runtime callables and
  not statically extractable; they are silently ignored.
- Pydantic Settings (`pydantic-settings`) — a different concern.

---

## User-Facing Changes

Users add `@contract(topic=..., role=...)` to their `BaseModel` subclass exactly as they would
to a Marshmallow `Schema`. No other change to their Pydantic code is required.

```python
from pydantic import BaseModel, Field
from contract_sentinel import contract, Role

@contract(topic="orders.created", role=Role.PRODUCER)
class OrderSchema(BaseModel):
    order_id: UUID
    amount: Decimal = Field(ge=0)
    status: Literal["pending", "confirmed", "cancelled"]
    customer: CustomerSchema
```

---

## Acceptance Criteria

- [ ] `pip install contract-sentinel[pydantic]` with any `pydantic>=2.0,<3.0` installed does
  not downgrade or conflict.
- [ ] `@contract` decorator attaches `__contract__` to a `BaseModel` subclass without
  interfering with Pydantic's metaclass or field resolution.
- [ ] `detect_framework` returns `Framework.PYDANTIC` for any `BaseModel` subclass without
  importing pydantic.
- [ ] `sentinel publish` against a Pydantic v2 codebase produces a valid contract JSON with
  correct field types, nullability flags, defaults, and nested structure.
- [ ] Primitive types (`str`, `int`, `float`, `bool`, `Decimal`, `datetime.*`, `UUID`,
  `bytes`) map to their canonical JSON Schema types.
- [ ] Pydantic semantic string types (`EmailStr`, `AnyUrl`/`HttpUrl`, `IPv4Address`,
  `IPv6Address`) map to `string` with the correct format.
- [ ] `Optional[T]` and `T | None` annotations set `is_nullable=True` on the field.
- [ ] Nested `BaseModel` fields produce `type="object"` with a populated `fields` list and
  `unknown` policy.
- [ ] `list[T]` produces `type="array"` with `item_type` (primitives) or `fields` (models).
- [ ] `dict[K, V]` produces `type="object"` with `key_type` and `value_type` / `fields`.
- [ ] `Literal[v1, v2]` produces `metadata.allowed_values`.
- [ ] `enum.Enum` subclass produces `type="string"`, `format="enum"`, `metadata.allowed_values`.
- [ ] Field constraints from `Field(ge=..., le=..., min_length=..., max_length=..., pattern=...)`
  are captured in `metadata.range`, `metadata.length`, `metadata.pattern`.
- [ ] `model_config['extra']` maps to `UnknownFieldBehaviour` correctly; the default (unset)
  maps to `IGNORE`.
- [ ] `just check` passes with `pydantic` pinned in the dev dependency group.
