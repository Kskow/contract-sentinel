# How to Add a New Validation Rule

## Overview

Rules live in `contract_sentinel/domain/rules/`. Each rule is a class that extends `Rule(ABC)` and implements `check()` and, for CRITICAL rules, `suggest_fix()`. Rules are pure domain logic — no I/O, no cloud SDK imports.

---

## 1. Create the Rule File

**File:** `contract_sentinel/domain/rules/<rule_name>.py`

Extend `Rule`, implement `check(producer, consumer)`, and override `suggest_fix` if the rule is CRITICAL. Either side of `check` may be `None` — guard explicitly.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.report import FixSuggestion
from contract_sentinel.domain.rules.rule import Rule, RuleName
from contract_sentinel.domain.rules.violation import Violation

if TYPE_CHECKING:
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
                rule=RuleName.MY_NEW_RULE,
                severity="CRITICAL",          # "CRITICAL" or "WARNING"
                field_path=producer.name,
                producer={...},               # only the fields relevant to this rule
                consumer={...},
                message=f"Field '{producer.name}' ...",
            )
        ]

    def suggest_fix(self, violation: Violation) -> FixSuggestion | None:
        path = violation.field_path
        return FixSuggestion(
            producer_suggestion=f"...",
            consumer_suggestion=f"...",
        )
```

**Severity guide:**
- `CRITICAL` — a consumer will fail at runtime if not fixed; override `suggest_fix` to provide instructions.
- `WARNING` — a schema smell or best-practice issue; leave `suggest_fix` at its default `return None`.

---

## 2. Add the Name to `RuleName`

**File:** `contract_sentinel/domain/rules/rule.py`

Add a new member to the `RuleName` StrEnum:

```python
class RuleName(StrEnum):
    ...
    MY_NEW_RULE = "MY_NEW_RULE"
```

---

## 3. Register the Rule in the Engine

**File:** `contract_sentinel/domain/rules/engine.py`

Import the class and append an instance to `PAIR_RULES`. The engine iterates this list for every matched field pair.

```python
from contract_sentinel.domain.rules.my_new import MyNewRule

PAIR_RULES: list[Rule] = [
    TypeMismatchRule(),
    ...
    MyNewRule(),   # add here
]
```

Rules in `PAIR_RULES` receive `(producer_field, consumer_field)` where either side can be `None` (consumer-only field → `producer` is `None`). If your rule targets producer-only fields (like `UndeclaredFieldRule`), it bypasses `PAIR_RULES` and is called directly in `_validate_pair` — add it there instead, following the same pattern as the existing undeclared-field call.

---

## 4. Register the Rule in `RULE_REGISTRY`

**File:** `contract_sentinel/domain/fix_suggestions.py`

Import the class and add an entry to `RULE_REGISTRY`. This is what wires the rule's `suggest_fix` into the fix suggestion pipeline.

```python
from contract_sentinel.domain.rules.my_new import MyNewRule

RULE_REGISTRY: dict[RuleName, Rule | UndeclaredFieldRule] = {
    ...
    RuleName.MY_NEW_RULE: MyNewRule(),   # add here
}
```

WARNING rules can be omitted from the registry — `suggest_fixes` filters them out before the registry is consulted. If you add a CRITICAL rule and forget the registry entry, it will silently produce no suggestion. Always add the entry.

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
from contract_sentinel.domain.rules.my_new import MyNewRule
from contract_sentinel.domain.rules.rule import RuleName
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

Add a test method that constructs a `PairViolations` with a `create_violation(RuleName.MY_NEW_RULE, ...)` and asserts the rendered suggestion strings in the returned `PairFixSuggestion`.

Use `create_violation()` from `tests/unit/helpers.py` — it accepts `producer=` and `consumer=` dicts matching what your rule puts in the `Violation`.

---

## Checklist

- [ ] `contract_sentinel/domain/rules/rule.py` — `RuleName.MY_NEW_RULE` added to the enum
- [ ] `contract_sentinel/domain/rules/<rule_name>.py` — rule class created with `check` and `suggest_fix`
- [ ] `contract_sentinel/domain/rules/engine.py` — instance added to `PAIR_RULES` (or wired directly for producer-only rules)
- [ ] `contract_sentinel/domain/fix_suggestions.py` — instance added to `RULE_REGISTRY` (CRITICAL rules only)
- [ ] `tests/unit/test_domain/test_rules/test_<rule_name>.py` — rule unit tests
- [ ] `tests/unit/test_domain/test_fix_suggestions.py` — fix suggestion tests (CRITICAL only)
- [ ] `just check` passes
