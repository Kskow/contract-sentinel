# How to Add a New Validation Rule

## Overview

Rules live in `contract_sentinel/domain/rules/`. Each rule is a class that extends `Rule(ABC)` and implements a single `check()` method. Rules are pure domain logic — no I/O, no cloud SDK imports.

---

## 1. Create the Rule File

**File:** `contract_sentinel/domain/rules/<rule_name>.py`

Extend `Rule` and implement `check(producer, consumer)`. Either side may be `None` — guard explicitly.

```python
from contract_sentinel.domain.rules.rule import Rule
from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField


class MyNewRule(Rule):
    def check(
        self, producer: ContractField | None, consumer: ContractField | None
    ) -> list[Violation]:
        if producer is None or consumer is None:
            return []
        # ... your logic
        return [
            Violation(
                rule="MY_NEW_RULE",          # SCREAMING_SNAKE_CASE string
                severity="CRITICAL",          # "CRITICAL" or "WARNING"
                field_path=producer.name,
                producer={...},               # only the fields relevant to this rule
                consumer={...},
                message=f"Field '{producer.name}' ...",
            )
        ]
```

**Severity guide:**
- `CRITICAL` — a consumer will fail at runtime if not fixed; fix suggestions are generated.
- `WARNING` — a schema smell or best-practice issue; no fix suggestions are generated.

---

## 2. Register the Rule in the Engine

**File:** `contract_sentinel/domain/rules/engine.py`

Import the class and append an instance to `PAIR_RULES`. The engine iterates this list for every matched field pair.

```python
from contract_sentinel.domain.rules.my_new import MyNewRule

PAIR_RULES: list[Rule] = [
    TypeMismatchRule(),
    ...
    MyNewRule(),   # ← add here
]
```

Rules in `PAIR_RULES` receive `(producer_field, consumer_field)` where either side can be `None` (consumer-only field → `producer` is `None`). If your rule targets producer-only fields (like `UndeclaredFieldRule`), it bypasses `PAIR_RULES` and is called directly in `_validate_pair` — add it there instead, following the same pattern as the existing undeclared-field call.

---

## 3. Export from the Package

**File:** `contract_sentinel/domain/rules/__init__.py`

Add the import and include it in `__all__`:

```python
from contract_sentinel.domain.rules.my_new import MyNewRule

__all__ = [
    ...
    "MyNewRule",
]
```

---

## 4. Add Fix Suggestions (CRITICAL rules only)

**File:** `contract_sentinel/domain/fix_suggestions.py`

Add a `case` to the `match violation.rule` block inside `_instruction_for()`. The `violation.producer` and `violation.consumer` dicts contain exactly the keys you set when constructing the `Violation`.

```python
case "MY_NEW_RULE":
    return FixSuggestion(
        producer_suggestion=f"...",
        consumer_suggestion=f"...",
    )
```

Rules with `severity="WARNING"` are filtered out before `_instruction_for` is ever called (see `suggest_fixes`), so no `case` is needed for them. If you add a CRITICAL rule and omit a `case`, it falls through to `case _: return None` — it will silently produce no suggestion. Always add the case.

---

## 5. Write Unit Tests

### Rule test

**File:** `tests/unit/test_domain/test_rules/test_<rule_name>.py`

Use `create_field()` and `create_violation()` from `tests/unit/helpers.py`. Group cases in a single class.

Required cases for every rule:

| Case | What to assert |
|---|---|
| Violation fires when condition is met | `len(violations) == 1`; assert the full `to_dict()` snapshot |
| No violation when condition is not met | `violations == []` |
| `producer is None` | `violations == []` (unless the rule is specifically designed for that) |
| `consumer is None` | `violations == []` (same caveat) |

```python
from contract_sentinel.domain.rules import MyNewRule
from tests.unit.helpers import create_field

class TestMyNewRule:
    def test_returns_violation_when_condition_is_met(self) -> None:
        producer = create_field(...)
        consumer = create_field(...)

        violations = MyNewRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "MY_NEW_RULE",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {...},
            "consumer": {...},
            "message": "...",
        }

    def test_returns_empty_when_no_violation(self) -> None:
        ...

    def test_returns_empty_when_producer_is_none(self) -> None:
        assert MyNewRule().check(None, create_field()) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        assert MyNewRule().check(create_field(), None) == []
```

### Fix suggestion test

**File:** `tests/unit/test_domain/test_fix_suggestions.py`

Add a test class (or cases to an existing class) that constructs a `PairViolations` with a `create_violation(rule="MY_NEW_RULE", ...)` and asserts the rendered suggestion strings in the returned `PairFixSuggestion`.

Use `create_violation()` from `tests/unit/helpers.py` — it accepts `producer=` and `consumer=` dicts matching what your rule puts in the `Violation`.

---

## Checklist

- [ ] `contract_sentinel/domain/rules/<rule_name>.py` — rule class created
- [ ] `contract_sentinel/domain/rules/engine.py` — instance added to `PAIR_RULES` (or wired directly for producer-only rules)
- [ ] `contract_sentinel/domain/rules/__init__.py` — exported from package
- [ ] `contract_sentinel/domain/fix_suggestions.py` — `case` added for CRITICAL rules
- [ ] `tests/unit/test_domain/test_rules/test_<rule_name>.py` — rule unit tests
- [ ] `tests/unit/test_domain/test_fix_suggestions.py` — fix suggestion tests (CRITICAL only)
- [ ] `just check` passes
