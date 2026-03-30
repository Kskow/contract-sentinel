# TICKET — Parser: guard against callable `load_default` / `dump_default`

**Created:** 2026-03-30

---

## Context

In `MarshmallowParser._build_metadata`, `load_default` and `dump_default` are stored in
metadata when they are not the Marshmallow `missing` sentinel:

```python
if field.load_default is not self._ma.missing:
    metadata["load_default"] = field.load_default
if field.dump_default is not self._ma.missing:
    metadata["dump_default"] = field.dump_default
```

This guard only excludes the sentinel. When a user sets a callable as a default
(e.g. `load_default=list` or `load_default=lambda: {}`), the callable object passes through and
is stored in the metadata dict. It then hits `json.dumps` during the publish step and raises:

```
TypeError: Object of type type is not JSON serializable
```

The fix is to also exclude callables. A callable default is a runtime factory — its behaviour
cannot be expressed as a static JSON value and therefore carries no meaningful contract
information. The correct action is to silently skip it, consistent with how `Method` and
`Function` fields are handled elsewhere in the parser.

---

## TICKET-01 — Parser: skip callable `load_default` and `dump_default`

**Depends on:** —
**Type:** Adapter

**Goal:**
Add a `callable()` guard to both default-capture branches in `_build_metadata` so that callable
defaults are silently omitted from the contract metadata, preventing a `TypeError` during
serialisation.

**Files to modify:**
- `contract_sentinel/adapters/schema_parsers/marshmallow.py`
- `tests/integration/test_adapters/test_schema_parser.py`

**Implementation notes:**
- The guard must be added to both the `load_default` and `dump_default` branches:
  `if field.load_default is not self._ma.missing and not callable(field.load_default)`.
- Scalar and compound JSON-serialisable defaults (strings, ints, booleans, lists, dicts) must
  still be stored — the guard must only skip callables, not all defaults.
- Do not emit a warning or a placeholder string. The silent skip matches the precedent set by
  `is_supported=False` fields (introspection failure is recorded structurally, not as a runtime
  message).

**Done when:**
- [x] A field with `load_default=list` produces no `load_default` key in metadata.
- [x] A field with `dump_default=dict` produces no `dump_default` key in metadata.
- [x] A field with `load_default=lambda: "x"` produces no `load_default` key in metadata.
- [x] A field with `load_default="active"` (scalar) still produces `metadata={"load_default": "active"}` — existing behaviour unchanged.
- [x] A field with `dump_default=0` (scalar) still produces `metadata={"dump_default": 0}` — existing behaviour unchanged.
- [x] Each of the above cases is covered by a test in `test_schema_parser.py`. The callable tests
      assert that the `metadata` dict either is `None` or does not contain the relevant key.
- [x] `just check` passes.
