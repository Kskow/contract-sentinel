# TICKET — Parser + Rule: `Equal`, `NoneOf`, `ContainsOnly`, `ContainsNoneOf` validators

**Created:** 2026-03-30

---

## Context

`MarshmallowParser._extract_single_validator` currently handles five validators: `And`, `Length`,
`Range`, `Regexp`, and `OneOf`. Four built-in validators are silently skipped: `Equal`, `NoneOf`,
`ContainsOnly`, and `ContainsNoneOf`. Their constraints never reach the contract, so the diff
engine cannot detect mismatches that involve them.

This work adds support in two layers:

**Parser layer (TICKET-01)** — extract the four validators into well-known metadata keys so the
contract captures their constraints:

| Validator | Metadata key | Stored value |
|---|---|---|
| `Equal(comparable)` | `"equal"` | `validator.comparable` |
| `NoneOf(iterable)` | `"forbidden_values"` | `list(validator.iterable)` |
| `ContainsOnly(choices)` | `"contains_only"` | `list(validator.choices)` |
| `ContainsNoneOf(iterable)` | `"contains_none_of"` | `list(validator.iterable)` |

**Rule layer (TICKET-02)** — add semantic comparison logic in `MetadataMismatchRule` for three of
the four new keys. `"equal"` needs no new rule: the existing `_check_key_mismatch` fallback
already performs strict equality comparison, which is the correct semantic for a field that must
always hold a single specific value.

The three keys that need dedicated handlers have set-based semantics that the generic fallback
cannot express:

- `"forbidden_values"` / `"contains_none_of"` — producer's forbidden set must be a **superset**
  of consumer's (consumer cannot forbid values the producer is still allowed to emit).
- `"contains_only"` — producer's allowed-item set must be a **subset** of consumer's (producer
  cannot emit items the consumer rejects).

`ContainsNoneOf` was introduced in marshmallow 3.19.0. The `isinstance` check in
`_extract_single_validator` will simply never match on older versions, so no version guard is
needed — the validator is silently skipped on pre-3.19 installs, which is already the current
behaviour.

---

## TICKET-01 — Parser: extract `Equal`, `NoneOf`, `ContainsOnly`, `ContainsNoneOf` into metadata

**Depends on:** —
**Type:** Adapter

**Goal:**
Add four `elif` branches to `_extract_single_validator` so that `Equal`, `NoneOf`,
`ContainsOnly`, and `ContainsNoneOf` validators are stored as named metadata keys in the
produced `ContractField`.

**Files to modify:**
- `contract_sentinel/adapters/schema_parsers/marshmallow.py`
- `tests/integration/test_adapters/test_schema_parser.py`

**Implementation notes:**
- All four branches follow the same pattern as the existing `OneOf` branch: access the
  relevant attribute on the validator object and store it in `metadata`.
- `ContainsNoneOf` is accessed as `self._validate.ContainsNoneOf`; all others are already
  available in the `self._validate` module reference that is set up in `__init__`.
- For `NoneOf` and `ContainsNoneOf`, the attribute holding the forbidden values is
  `validator.iterable`; for `ContainsOnly`, it is `validator.choices`; for `Equal`, it is
  `validator.comparable`.
- `list()` must be called on `iterable` and `choices` to ensure the stored value is always a
  plain list, not an arbitrary iterable type.
- `Equal.comparable` is a scalar — store it as-is, no conversion needed.
- The four branches must be inserted before the final `else` / implicit fall-through in
  `_extract_single_validator`.

**Done when:**
- [x] A field with `validate=mv.Equal("active")` produces `metadata={"equal": "active"}`.
- [x] A field with `validate=mv.NoneOf(["deleted", "banned"])` produces
      `metadata={"forbidden_values": ["deleted", "banned"]}`.
- [x] A field with `validate=mv.ContainsOnly(["red", "green", "blue"])` produces
      `metadata={"contains_only": ["red", "green", "blue"]}`.
- [x] A field with `validate=mv.ContainsNoneOf(["profanity"])` produces
      `metadata={"contains_none_of": ["profanity"]}`.
- [x] All four cases are covered by dedicated tests in `test_schema_parser.py`, each following
      the same structure as `test_one_of_validator_appears_as_allowed_values_in_metadata`.
- [x] Each new validator also works when wrapped in `mv.And(...)` — the `And` unwrapping in
      `_extract_single_validator` recurses, so no extra code is needed, but one combined test
      should verify this for at least one of the four validators.
- [x] `just check` passes.

---

## TICKET-02 — Rule: comparison handlers for `forbidden_values`, `contains_only`, `contains_none_of`

**Depends on:** TICKET-01
**Type:** Domain

**Goal:**
Add three `RuleName` values and three dedicated comparison methods to `MetadataMismatchRule` so
that the diff engine applies the correct set-based semantics to the three new metadata keys that
the generic `_check_key_mismatch` fallback cannot express correctly. Also add `suggest_fix`
branches for all three.

**Files to modify:**
- `contract_sentinel/domain/rules/rule.py`
- `contract_sentinel/domain/rules/metadata_mismatch.py`
- `tests/unit/test_domain/test_rules/test_metadata_mismatch.py`

**Implementation notes:**

New `RuleName` entries:
- `METADATA_FORBIDDEN_VALUES_MISMATCH`
- `METADATA_CONTAINS_ONLY_MISMATCH`
- `METADATA_CONTAINS_NONE_OF_MISMATCH`

**`forbidden_values` comparison logic** (`_compare_forbidden_values`):

Consumer declares values it will reject (e.g. `["deleted", "banned"]`). The producer must also
reject at least those same values — its `forbidden_values` set must be a superset of the
consumer's. Violation fires when `set(consumer_forbidden) - set(producer_forbidden)` is
non-empty (producer can still emit values the consumer rejects). If the producer has no
`forbidden_values` key at all, fire a single violation covering the entire consumer set.

**`contains_only` comparison logic** (`_compare_contains_only`):

Consumer accepts list items only from its `choices` set. The producer's `choices` must be a
subset of the consumer's — the producer cannot emit items the consumer won't accept. Violation
fires when `set(producer_choices) - set(consumer_choices)` is non-empty. This is structurally
identical to `_compare_allowed_values` but operates on a different metadata key and uses the
`METADATA_CONTAINS_ONLY_MISMATCH` rule name. If the producer has no `contains_only` key, fire a
single violation (producer is unconstrained; it could emit any item).

**`contains_none_of` comparison logic** (`_compare_contains_none_of`):

Consumer forbids specific values from appearing in the list. The producer must also forbid at
least those values. Violation fires when `set(consumer_none_of) - set(producer_none_of)` is
non-empty. Structurally identical to `_compare_forbidden_values` but uses the
`METADATA_CONTAINS_NONE_OF_MISMATCH` rule name.

**Wire-up in `MetadataMismatchRule.check`:**

Add three new `case` branches to the `match key:` block:
```
case "forbidden_values":  → self._compare_forbidden_values(...)
case "contains_only":     → self._compare_contains_only(...)
case "contains_none_of":  → self._compare_contains_none_of(...)
```

**`suggest_fix` branches:**

- `METADATA_FORBIDDEN_VALUES_MISMATCH` (producer unconstrained):
  - Producer: `"Add a NoneOf constraint to field '{path}' that forbids at least {consumer['forbidden_values']}."`
  - Consumer: `"Reduce the forbidden_values constraint on field '{path}' to only include values the producer also forbids."`
- `METADATA_FORBIDDEN_VALUES_MISMATCH` (producer has partial constraint):
  - Producer: `"Expand the NoneOf constraint on field '{path}' to also forbid {consumer['forbidden_values']}."`
  - Consumer: same as above
- `METADATA_CONTAINS_ONLY_MISMATCH` (producer unconstrained):
  - Producer: `"Add a ContainsOnly constraint to field '{path}' restricting emitted items to a subset of {consumer['contains_only']}."`
  - Consumer: `"Expand the ContainsOnly constraint on field '{path}' to include all items the producer may emit."`
- `METADATA_CONTAINS_ONLY_MISMATCH` (producer has wider set):
  - Producer: `"Restrict the ContainsOnly constraint on field '{path}' to {consumer['contains_only']}."`
  - Consumer: same as above
- `METADATA_CONTAINS_NONE_OF_MISMATCH` (producer unconstrained):
  - Producer: `"Add a ContainsNoneOf constraint to field '{path}' that excludes at least {consumer['contains_none_of']}."`
  - Consumer: `"Reduce the ContainsNoneOf constraint on field '{path}' to only include values the producer also excludes."`
- `METADATA_CONTAINS_NONE_OF_MISMATCH` (producer has partial constraint):
  - Producer: `"Expand the ContainsNoneOf constraint on field '{path}' to also exclude {consumer['contains_none_of']}."`
  - Consumer: same as above

**Done when:**
- [x] `RuleName` has three new entries: `METADATA_FORBIDDEN_VALUES_MISMATCH`,
      `METADATA_CONTAINS_ONLY_MISMATCH`, `METADATA_CONTAINS_NONE_OF_MISMATCH`.
- [x] `forbidden_values`: violation fires with `METADATA_FORBIDDEN_VALUES_MISMATCH` when
      consumer forbids values that the producer's `forbidden_values` does not cover.
- [x] `forbidden_values`: violation fires when producer has no `forbidden_values` but consumer
      does.
- [x] `forbidden_values`: no violation when producer's `forbidden_values` is a superset of
      consumer's.
- [x] `forbidden_values`: no violation when consumer has no `forbidden_values`.
- [x] `contains_only`: violation fires with `METADATA_CONTAINS_ONLY_MISMATCH` when producer's
      choices set is not a subset of consumer's choices set.
- [x] `contains_only`: violation fires when producer has no `contains_only` but consumer does.
- [x] `contains_only`: no violation when producer's choices are a subset of consumer's.
- [x] `contains_only`: no violation when consumer has no `contains_only`.
- [x] `contains_none_of`: violation fires with `METADATA_CONTAINS_NONE_OF_MISMATCH` when
      consumer's forbidden-item set is not covered by producer's `contains_none_of`.
- [x] `contains_none_of`: violation fires when producer has no `contains_none_of` but consumer
      does.
- [x] `contains_none_of`: no violation when producer's excluded set is a superset of consumer's.
- [x] `contains_none_of`: no violation when consumer has no `contains_none_of`.
- [x] `equal` (via generic fallback): confirm with one test that a producer with
      `metadata={"equal": "active"}` and a consumer with `metadata={"equal": "pending"}` raises
      `METADATA_KEY_MISMATCH` — no new rule code required, test documents the existing behaviour.
- [x] All `suggest_fix` branches return a `FixSuggestion` with both `producer_suggestion` and
      `consumer_suggestion` set; one test per rule name covers the unconstrained-producer case.
- [x] All new tests use `create_field(metadata=...)` and follow the existing test style in
      `test_metadata_mismatch.py`.
- [x] `just check` passes.
