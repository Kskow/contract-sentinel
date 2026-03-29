# How to Add a New Contract Store

## Overview

Contract stores live in `contract_sentinel/adapters/`. Each store is a class that extends `ContractStore(ABC)` and implements five methods for reading, writing, and listing contract documents. The store is the only place that imports a cloud provider SDK.

---

## 1. Create the Store File

**File:** `contract_sentinel/adapters/<provider>_contract_store.py`

Extend `ContractStore` and implement all five abstract methods. The SDK import must be lazy (inside `__init__`) so the module loads safely without the optional extra installed.

```python
from __future__ import annotations

from contract_sentinel.adapters.contract_store import ContractStore


class MyProviderContractStore(ContractStore):
    def __init__(self, bucket: str, path: str, ...) -> None:
        import my_provider_sdk   # lazy — only required when this store is used

        self._bucket = bucket
        self._path = path
        self._client = my_provider_sdk.Client(...)

    def get_file(self, key: str) -> str:
        """Return the string content stored at *key*."""
        ...

    def put_file(self, key: str, content: str) -> None:
        """Write *content* (UTF-8 string) to *key*, overwriting any existing value."""
        ...

    def list_files(self, prefix: str) -> list[str]:
        """Return all keys that share *prefix*, ordered by last-modified descending."""
        ...

    def file_exists(self, key: str) -> bool:
        """Return True if an object exists at *key*, False otherwise."""
        ...

    def delete_file(self, key: str) -> None:
        """Permanently remove the object at *key*. No-op if the key does not exist."""
        ...
```

**Method contracts:**
- `list_files` — must return keys ordered by last-modified **descending** (newest first). The publish service relies on this to resolve the latest contract.
- `delete_file` — must be a **no-op** when the key does not exist; must not raise.
- All keys passed to and returned from every method are **relative** — the store prepends any path prefix internally.

---

## 2. Register in the Factory

**File:** `contract_sentinel/factory.py`

Add a `case "provider":` branch to `get_store()`. The store name string is what users set via the `SENTINEL_STORE` environment variable (defaults to `"s3"`).

```python
def get_store(config: Config) -> ContractStore:
    match config.store:
        case "s3":
            ...
        case "my-provider":
            from contract_sentinel.adapters.my_provider_contract_store import (
                MyProviderContractStore,
            )

            try:
                return MyProviderContractStore(
                    bucket=config.s3_bucket,
                    path=config.s3_path,
                    ...
                )
            except ImportError as exc:
                raise MissingDependencyError(
                    "store 'my-provider' requires the my-provider extra.\n"
                    "Install it with: pip install contract-sentinel[my-provider]"
                ) from exc
        case _:
            raise UnsupportedStorageError(
                f"Unrecognised store '{config.store}'. Valid options: 's3', 'my-provider'."
            )
```

Users select the store by setting `SENTINEL_STORE=my-provider` in their environment.

---

## 3. Add to `pyproject.toml`

Add the provider SDK as a named optional dependency and include it in the `all` group:

```toml
[project.optional-dependencies]
my-provider = [
    "my-provider-sdk>=1.0",
]
all = [
    "boto3>=1.42.70",
    "marshmallow>=3.13,<5.0",
    "my-provider-sdk>=1.0",   # add here
]
```

---

## 4. Write Integration Tests

**File:** `tests/integration/test_adapters/test_<provider>_store.py`

Test all five methods against a real or emulated endpoint. Follow the pattern in `tests/integration/test_adapters/test_contract_store.py`.

```python
class TestMyProviderContractStore:
    def test_put_and_get_file(self, store: MyProviderContractStore) -> None:
        store.put_file("topic/schema.json", '{"key": "value"}')
        assert store.get_file("topic/schema.json") == '{"key": "value"}'

    def test_list_files_returns_newest_first(self, store: MyProviderContractStore) -> None:
        ...

    def test_file_exists(self, store: MyProviderContractStore) -> None:
        ...

    def test_delete_file(self, store: MyProviderContractStore) -> None:
        ...

    def test_delete_file_is_noop_when_key_missing(self, store: MyProviderContractStore) -> None:
        store.delete_file("nonexistent/key.json")  # must not raise
```

---

## Checklist

- [ ] `contract_sentinel/adapters/<provider>_contract_store.py` — store class created, all five methods implemented
- [ ] `contract_sentinel/factory.py` — `case "my-provider":` branch added with lazy import and `MissingDependencyError`; `UnsupportedStorageError` message updated to list the new option
- [ ] `pyproject.toml` — new optional dependency group added; SDK included in `all`
- [ ] `tests/integration/test_adapters/test_<provider>_store.py` — all five methods tested against a real or emulated endpoint
- [ ] `just check` passes
