# Rule DX Improvements — Dev Tickets

**Feature slug:** `005-rule-dx`
**Created:** 2026-03-28

---

## Architecture Notes

Three independent quality-of-life improvements targeting the rule authoring experience.

### TICKET-01 — RuleName StrEnum

`Violation.rule` is currently a bare `str`. A typo anywhere in the codebase (rule file, match case, test helper) fails silently. Making `rule` typed as `RuleName(StrEnum)` turns every such mistake into a `ty` error at zero runtime cost — `StrEnum` inherits from `str`, so `to_dict()` and all JSON serialisation continue to work unchanged.

`test_engine.py` constructs a `Violation(rule="TEST_RULE", ...)` as a test double. Since `RuleName` won't carry a `TEST_RULE` member, that helper must be updated to use any real `RuleName` value (e.g. `RuleName.TYPE_MISMATCH`).

### TICKET-02 — Co-locate `suggest_fix` in each Rule class

The fix suggestion for a rule currently lives in a `match violation.rule:` block in `fix_suggestions.py`, disconnected from the rule that raises it. The `case _: return None` fallthrough means a CRITICAL rule added without a matching case silently produces no suggestion — undetectable until a user notices the missing output.

The fix: add an optional `suggest_fix(violation: Violation) -> FixSuggestion | None` method to `Rule(ABC)` (default `return None`), override it in every CRITICAL rule, and replace `_instruction_for` with a `RULE_REGISTRY` dict lookup.

**Circular import to resolve:** if rule files import `FixSuggestion` from `fix_suggestions.py`, and `fix_suggestions.py` imports `RULE_REGISTRY` from `engine.py`, and `engine.py` imports rule files → cycle. Fix: move the `FixSuggestion` dataclass from `fix_suggestions.py` into `report.py`, which already holds the other suggestion-related dataclasses and is not imported by rule files at runtime.

**`MetadataMismatchRule` is a special case:** it is one class but emits four distinct `rule` strings (`METADATA_ALLOWED_VALUES_MISMATCH`, `METADATA_RANGE_MISMATCH`, `METADATA_LENGTH_MISMATCH`, `METADATA_KEY_MISMATCH`). The `RULE_REGISTRY` in `engine.py` maps all four keys to the same `MetadataMismatchRule()` instance. `MetadataMismatchRule.suggest_fix()` internally branches on `violation.rule` — the logic is still co-located, just not a flat override.

### TICKET-03 — Prune `rules/__init__.py`

The `__init__.py` re-exports every rule class and `Violation` as a convenience layer. In practice it creates a second place to maintain every time a rule is added, and the convenience is minimal — direct imports from the concrete module are just as readable and far more navigable. Gutting the file removes the maintenance burden without changing any production behaviour.

### New files
None — all tickets modify existing files only.

### Ticket order
TICKET-01 and TICKET-03 are independent and can be done in either order or in parallel. TICKET-02 depends on TICKET-01 (needs `RuleName` for the registry key type and for `suggest_fix` signatures).

---

## Tickets

### TICKET-01 — Introduce `RuleName` StrEnum and type `Violation.rule`

**Depends on:** —
**Type:** Domain

**Goal:**
Replace the bare `str` on `Violation.rule` with a `RuleName(StrEnum)` so that rule name mismatches are caught by `ty` rather than silently falling through at runtime.

**Files to create / modify:**
- `contract_sentinel/domain/rules/rule_name.py` — create; define `RuleName(StrEnum)` with one member per existing rule string: `TYPE_MISMATCH`, `MISSING_FIELD`, `REQUIREMENT_MISMATCH`, `NULLABILITY_MISMATCH`, `DIRECTION_MISMATCH`, `STRUCTURE_MISMATCH`, `UNDECLARED_FIELD`, `COUNTERPART_MISMATCH`, `METADATA_ALLOWED_VALUES_MISMATCH`, `METADATA_RANGE_MISMATCH`, `METADATA_LENGTH_MISMATCH`, `METADATA_KEY_MISMATCH`
- `contract_sentinel/domain/rules/violation.py` — modify; `rule: str` → `rule: RuleName`
- `contract_sentinel/domain/rules/type_mismatch.py` — modify; `rule="TYPE_MISMATCH"` → `rule=RuleName.TYPE_MISMATCH`
- `contract_sentinel/domain/rules/missing_field.py` — same pattern
- `contract_sentinel/domain/rules/requirement_mismatch.py` — same pattern
- `contract_sentinel/domain/rules/nullability_mismatch.py` — same pattern
- `contract_sentinel/domain/rules/direction_mismatch.py` — same pattern
- `contract_sentinel/domain/rules/structure_mismatch.py` — same pattern
- `contract_sentinel/domain/rules/undeclared_field.py` — same pattern
- `contract_sentinel/domain/rules/metadata_mismatch.py` — same pattern (4 distinct members)
- `contract_sentinel/domain/rules/counterpart_mismatch.py` — same pattern
- `contract_sentinel/domain/fix_suggestions.py` — modify; all `case "RULE_NAME":` literals → `case RuleName.RULE_NAME:`
- `tests/unit/helpers.py` — modify; `create_violation(rule: str, ...)` → `rule: RuleName`; update all existing `create_violation("RULE_NAME", ...)` call sites in the file if any exist
- `tests/unit/test_domain/test_rules/test_engine.py` — modify; `_violation()` helper uses `rule="TEST_RULE"` — change to `rule=RuleName.TYPE_MISMATCH` (or any valid member; the test does not assert on the rule name)
- All `tests/unit/test_domain/test_rules/test_*.py` — modify; `create_violation("RULE_NAME", ...)` call sites → `create_violation(RuleName.RULE_NAME, ...)`

**Done when:**
- [x] `RuleName` is defined in `rule.py` (co-located with `Rule`) with all 12 members listed above
- [x] `Violation.rule` is annotated `RuleName`, not `str`
- [x] Every `Violation(rule=..., ...)` construction in production code passes a `RuleName` member, not a string literal
- [x] Every `case "..."` in `fix_suggestions._instruction_for` is replaced with `case RuleName.X:`
- [x] `create_violation` in `tests/unit/helpers.py` accepts `RuleName`, not `str`
- [x] `just check` passes (lint, typecheck, all tests green)

---

### TICKET-02 — Co-locate `suggest_fix` in each Rule class

**Depends on:** TICKET-01
**Type:** Domain

**Goal:**
Move fix suggestion logic into the rule class that raises the violation, eliminating the disconnected `match` block in `fix_suggestions.py` and making it structurally impossible to add a CRITICAL rule without also shipping its suggestion.

**Files to create / modify:**
- `contract_sentinel/domain/report.py` — modify; move the `FixSuggestion` dataclass here from `fix_suggestions.py` (place it alongside `PairFixSuggestion` which is already there)
- `contract_sentinel/domain/rules/rule.py` — modify; add `suggest_fix(self, violation: Violation) -> FixSuggestion | None` with a default `return None`; both types are `TYPE_CHECKING`-only imports in the ABC since the default body never constructs either
- `contract_sentinel/domain/rules/type_mismatch.py` — modify; implement `suggest_fix`; import `FixSuggestion` from `report.py` at runtime
- `contract_sentinel/domain/rules/missing_field.py` — same
- `contract_sentinel/domain/rules/requirement_mismatch.py` — same
- `contract_sentinel/domain/rules/nullability_mismatch.py` — same
- `contract_sentinel/domain/rules/direction_mismatch.py` — same
- `contract_sentinel/domain/rules/structure_mismatch.py` — same
- `contract_sentinel/domain/rules/undeclared_field.py` — same
- `contract_sentinel/domain/rules/metadata_mismatch.py` — same; `suggest_fix` branches internally on `violation.rule` across the 4 metadata rule names since one class owns all four
- `contract_sentinel/domain/rules/engine.py` — modify; add `RULE_REGISTRY: dict[RuleName, Rule]` — a manually constructed dict mapping every `RuleName` to its rule instance; all four metadata names map to the same `MetadataMismatchRule()` instance; `CounterpartMismatchRule` is excluded (WARNING-only, never reaches `suggest_fix`)
- `contract_sentinel/domain/fix_suggestions.py` — modify; remove the `FixSuggestion` dataclass (now in `report.py`); replace the entire `_instruction_for` match block with a `RULE_REGISTRY` lookup + `rule.suggest_fix(violation)` call; import `RULE_REGISTRY` from `engine`; import `FixSuggestion` from `report`
- `tests/unit/test_domain/test_fix_suggestions.py` — modify; update `FixSuggestion` import to come from `report.py`
- `tests/unit/test_domain/test_rules/test_type_mismatch.py` — modify; add test cases asserting `TypeMismatchRule().suggest_fix(violation)` returns the correct `FixSuggestion`
- All other `tests/unit/test_domain/test_rules/test_<rule>.py` for CRITICAL rules — same: add `suggest_fix` test cases

**Done when:**
- [x] `FixSuggestion` is defined in `report.py`; the definition is removed from `fix_suggestions.py`
- [x] `Rule.suggest_fix` exists with a default `return None`; all 8 CRITICAL rule classes override it
- [x] `RULE_REGISTRY` is defined in `engine.py` and covers all 12 `RuleName` members except `COUNTERPART_MISMATCH`
- [x] `fix_suggestions._instruction_for` contains no `match` block; it delegates entirely to `RULE_REGISTRY` lookup
- [x] Each CRITICAL rule's unit test file asserts the correct `FixSuggestion` is returned from `suggest_fix`
- [x] `just check` passes

---

### TICKET-03 — Remove re-exports from `rules/__init__.py`

**Depends on:** —
**Type:** Domain

**Goal:**
Gut `rules/__init__.py` down to an empty package marker, eliminating the second place that must be updated every time a rule is added or renamed.

**Files to create / modify:**
- `contract_sentinel/domain/rules/__init__.py` — modify; remove the module docstring, all imports, and `__all__`; leave the file empty
- `tests/unit/test_domain/test_rules/test_counterpart_mismatch.py` — modify; change `from contract_sentinel.domain.rules import ...` to direct module imports
- `tests/unit/test_domain/test_rules/test_direction_mismatch.py` — same
- `tests/unit/test_domain/test_rules/test_metadata_mismatch.py` — same
- `tests/unit/test_domain/test_rules/test_missing_field.py` — same
- `tests/unit/test_domain/test_rules/test_nullability_mismatch.py` — same
- `tests/unit/test_domain/test_rules/test_requirement_mismatch.py` — same
- `tests/unit/test_domain/test_rules/test_structure_mismatch.py` — same
- `tests/unit/test_domain/test_rules/test_type_mismatch.py` — same
- `tests/unit/test_domain/test_rules/test_undeclared_field.py` — same
- `tests/unit/test_domain/test_rules/test_violation.py` — same if it imports from the package level

**Done when:**
- [x] `rules/__init__.py` contains no imports and no `__all__`
- [x] Every test file that previously imported from `contract_sentinel.domain.rules` now imports from the concrete module (e.g. `contract_sentinel.domain.rules.type_mismatch`)
- [x] No production file is broken (engine and fix_suggestions already import directly — verify with `just check`)
- [x] `just check` passes
