# How to Add a New Schema Parser

## Overview

Parsers live in `contract_sentinel/adapters/schema_parsers/`. Each parser is a class that extends `SchemaParser(ABC)` and converts a framework-specific schema class into a `ContractSchema` understood by the domain. Parsers are the only place that imports a third-party schema framework.

---

## 1. Create the Parser File

**File:** `contract_sentinel/adapters/schema_parsers/<framework>.py`

Extend `SchemaParser` and implement `parse(cls)`. The method receives the decorated class at runtime and must return a fully populated `ContractSchema`.

```python
from __future__ import annotations

from contract_sentinel.adapters.schema_parsers.parser import SchemaParser
from contract_sentinel.domain.schema import (
    ContractField,
    ContractSchema,
    UnknownFieldBehaviour,
)


class MyFrameworkParser(SchemaParser):
    def __init__(self, repository: str) -> None:
        self._repository = repository

    def parse(self, cls: type) -> ContractSchema:
        meta = cls.__contract_meta__  # set by the @contract decorator
        fields: list[ContractField] = []

        for field_name, field_obj in cls.<framework_fields_accessor>.items():
            fields.append(
                ContractField(
                    name=field_name,
                    type=<resolve_type(field_obj)>,
                    is_required=<bool>,
                    is_nullable=<bool>,
                )
            )

        return ContractSchema(
            topic=meta.topic,
            role=meta.role,
            repository=self._repository,
            class_name=cls.__name__,
            unknown=UnknownFieldBehaviour.FORBID,
            fields=fields,
        )
```

---

## 2. Register the Framework

**File:** `contract_sentinel/domain/framework.py`

Add a new member to the `Framework` enum:

```python
class Framework(StrEnum):
    MARSHMALLOW = "marshmallow"
    MY_FRAMEWORK = "my_framework"   # add here
```

Also update `detect_framework(cls)` in the same file to return the new member when it recognises the framework's base class or characteristic attribute.

---

## 3. Register in the Factory

**File:** `contract_sentinel/factory.py`

Add a `case Framework.MY_FRAMEWORK:` branch to `get_parser()`. Use a lazy import and wrap the instantiation in a `try/except ImportError` — this ensures the optional extra is only required when the parser is actually used.

```python
def get_parser(framework: Framework, repository: str) -> SchemaParser:
    match framework:
        case Framework.MARSHMALLOW:
            ...
        case Framework.MY_FRAMEWORK:
            from contract_sentinel.adapters.schema_parsers.my_framework import MyFrameworkParser

            try:
                return MyFrameworkParser(repository=repository)
            except ImportError as exc:
                raise MissingDependencyError(
                    "framework 'my_framework' requires the my-framework extra.\n"
                    "Install it with: pip install contract-sentinel[my-framework]"
                ) from exc
        case _:
            raise UnsupportedFrameworkError(...)
```

---

## 4. Add to `pyproject.toml`

Add the framework package as a named optional dependency and include it in the `all` group:

```toml
[project.optional-dependencies]
my-framework = [
    "my-framework-package>=1.0",
]
all = [
    "boto3>=1.42.70",
    "marshmallow>=3.13,<5.0",
    "my-framework-package>=1.0",   # add here
]
```

---

## 5. Write Integration Tests

**File:** `tests/integration/test_adapters/test_<framework>_parser.py`

Test against a real schema class — no mocking. Follow the pattern in `tests/integration/test_adapters/test_schema_parser.py`.

```python
from contract_sentinel.adapters.schema_parsers.my_framework import MyFrameworkParser

class TestMyFrameworkParser:
    def test_parses_required_field(self) -> None:
        class MySchema:
            ...  # real framework schema definition

        result = MyFrameworkParser(repository="test-repo").parse(MySchema)

        assert result.fields[0].name == "id"
        assert result.fields[0].type == "integer"
        assert result.fields[0].is_required is True
```

---

## Checklist

- [ ] `contract_sentinel/adapters/schema_parsers/<framework>.py` — parser class created, `parse()` implemented
- [ ] `contract_sentinel/domain/framework.py` — new `Framework` member added; `detect_framework` updated
- [ ] `contract_sentinel/factory.py` — `case Framework.MY_FRAMEWORK:` branch added with lazy import and `MissingDependencyError`
- [ ] `pyproject.toml` — new optional dependency group added; package included in `all`
- [ ] `tests/integration/test_adapters/test_<framework>_parser.py` — integration tests against a real schema class
- [ ] `just check` passes
