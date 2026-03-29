# Additional Contract Stores — Dev Tickets

**Feature slug:** `007-additional-contract-stores`
**Spec:** `docs/features/007-additional-contract-stores/product_spec.md`
**Design:** `docs/features/007-additional-contract-stores/design.md`
**Created:** 2026-03-29

---

## Architecture Notes

### Adapter boundary

Both new stores extend `ContractStore(ABC)` in `adapters/contract_store.py`. No domain,
service, or CLI code changes anywhere. The two wiring points are `config.py` (new env var
fields) and `factory.py` (new `case` branches).

### Data flow

```
SENTINEL_STORE=gcs / azure-blob
  → Config()                     # reads new env var fields
  → factory.get_store(config)    # case "gcs" → GCSContractStore(...)
                                 # case "azure-blob" → AzureContractStore(...)
  → ContractStore ABC            # same interface as S3ContractStore
  → services/publish, validate   # unchanged
```

### New files

- `contract_sentinel/adapters/gcs_contract_store.py`
- `contract_sentinel/adapters/azure_contract_store.py`
- `tests/integration/test_adapters/test_gcs_contract_store.py`
- `tests/integration/test_adapters/test_azure_contract_store.py`

### Emulators

- GCS → `fake-gcs-server` (`fsouza/fake-gcs-server`) at port `4443`
- Azure Blob → `Azurite` (`mcr.microsoft.com/azure-storage/azurite`) at port `10000`

Both are added to `docker-compose.yml`. The `app` service `depends_on` list is extended.

### Patterns to reuse

- `S3ContractStore` — exact structural model: lazy SDK import in `__init__`, `_full_key`
  helper, `ValueError` guards on required constructor args.
- `tests/integration/conftest.py` — `s3_bucket` / `s3_store` fixture pattern replicated for
  each new store.
- `factory.py` — lazy import inside `case` branch + `MissingDependencyError` on `ImportError`.

### No distributed systems concerns

All five `ContractStore` methods are synchronous and stateless within a request. No
idempotency, retry, or DLQ considerations beyond what the underlying SDK handles.

### IAM / env var requirements

See the design doc for the full env var table. New variables added to `.env.local` use static
fake credentials safe to commit (Azurite well-known key, anonymous GCS emulator).

---

## Tickets

### TICKET-01 — `GCSContractStore` adapter and `Config` GCS fields

**Depends on:** –
**Type:** Adapter

**Goal:**
Implement the full `GCSContractStore` and the three GCS config fields it needs, following the
pattern in `contributors/how-to-add-a-contract-store.md`.

**Files to create / modify:**
- `contract_sentinel/adapters/gcs_contract_store.py` — create
- `contract_sentinel/config.py` — modify

**Done when:**
- [ ] `GCSContractStore(ContractStore)` exists with `__init__(self, bucket: str | None, path: str, endpoint_url: str | None)`.
- [ ] `google.cloud.storage` is lazy-imported inside `__init__` (not at module level).
- [ ] When `endpoint_url` is `None`, a standard `google.cloud.storage.Client()` is constructed
  (uses Application Default Credentials / `GOOGLE_APPLICATION_CREDENTIALS`).
- [ ] When `endpoint_url` is set, the client is constructed with `AnonymousCredentials` and
  `client_options={"api_endpoint": endpoint_url}` for emulator use.
- [ ] `__init__` raises `ValueError` with a descriptive message when `bucket` is falsy.
- [ ] `get_file(key)` returns the blob content as a UTF-8 string.
- [ ] `put_file(key, content)` uploads the string as UTF-8 bytes, overwriting any existing blob.
- [ ] `list_files(prefix)` returns all relative keys under the prefix, sorted by
  `blob.updated` descending.
- [ ] `file_exists(key)` returns `True` / `False` without raising.
- [ ] `delete_file(key)` deletes the blob; catches `google.cloud.exceptions.NotFound` and
  returns silently — no exception raised.
- [ ] All keys passed to and returned from every method are relative — the store prepends
  `self._path + "/"` internally.
- [ ] `config.py` gains `gcs_bucket` (from `SENTINEL_GCS_BUCKET`, `None` if absent),
  `gcs_path` (from `SENTINEL_GCS_PATH`, default `"contract_tests"`), and `gcs_endpoint_url`
  (from `GCS_ENDPOINT_URL`, `None` if absent).

---

### TICKET-02 — GCS wiring: `docker-compose.yml`, `factory.py`, `pyproject.toml`

**Depends on:** TICKET-01
**Type:** Infra

**Goal:**
Wire `GCSContractStore` into the factory, add the `fake-gcs-server` emulator to Docker
Compose, and register the `gcs` optional dependency.

**Files to create / modify:**
- `docker-compose.yml` — modify
- `contract_sentinel/factory.py` — modify
- `pyproject.toml` — modify
- `.env.local` — modify
- `tests/unit/test_factory.py` — modify
- `tests/unit/test_config.py` — modify

**Done when:**
- [ ] `docker-compose.yml` has a `fake-gcs-server` service using image
  `fsouza/fake-gcs-server:latest`, port `4443:4443`, and command
  `-scheme http -port 4443 -external-url http://fake-gcs-server:4443`.
- [ ] The `app` service `depends_on` includes `fake-gcs-server`.
- [ ] `factory.get_store()` has a `case "gcs":` branch that lazy-imports `GCSContractStore`,
  passes `config.gcs_bucket`, `config.gcs_path`, and `config.gcs_endpoint_url`, and catches
  `ImportError` → `MissingDependencyError` with the message:
  `"store 'gcs' requires the gcs extra.\nInstall it with: pip install contract-sentinel[gcs]"`.
- [ ] `UnsupportedStorageError` message updated to `"Valid options: 's3', 'gcs'."`.
- [ ] `pyproject.toml` has a `gcs = ["google-cloud-storage>=2.0,<3.0"]` entry under
  `[project.optional-dependencies]`.
- [ ] `google-cloud-storage>=2.0,<3.0` is added to the `all` optional dep group.
- [ ] `google-cloud-storage>=2.0,<3.0` is added to `[dependency-groups] dev`.
- [ ] `.env.local` has `GCS_ENDPOINT_URL=http://fake-gcs-server:4443` and
  `SENTINEL_GCS_BUCKET=contract-sentinel-local-gcs`.
- [ ] `test_factory.py` — new test: `get_store` with `SENTINEL_STORE=gcs` returns a
  `GCSContractStore` instance.
- [ ] `test_factory.py` — new test: `MissingDependencyError` raised when
  `google.cloud.storage` is absent (`monkeypatch.setitem(sys.modules, "google.cloud.storage", None)`).
- [ ] `test_factory.py` — existing `UnsupportedStorageError` message assertion updated to
  `"Valid options: 's3', 'gcs'."`.
- [ ] `test_config.py` — new tests asserting `config.gcs_bucket`, `config.gcs_path`, and
  `config.gcs_endpoint_url` read from the correct env vars with correct defaults.
- [ ] `just check` passes (`uv` picks up the newly added dev dependency).

---

### TICKET-03 — GCS integration tests

**Depends on:** TICKET-02
**Type:** Adapter

**Goal:**
Write the full integration test suite for `GCSContractStore` against `fake-gcs-server`, using
the same test cases as `TestS3ContractStore`.

**Files to create / modify:**
- `tests/integration/conftest.py` — modify
- `tests/integration/test_adapters/test_gcs_contract_store.py` — create

**Done when:**
- [ ] `conftest.py` has a `gcs_bucket` fixture that creates a uniquely-named GCS bucket in
  `fake-gcs-server` via the `google.cloud.storage` client, yields the bucket name, and deletes
  all blobs + the bucket in teardown.
- [ ] `conftest.py` has a `gcs_store` fixture that depends on `gcs_bucket` and returns a
  `GCSContractStore` pointed at the test bucket with `_GCS_ENDPOINT_URL` from the environment
  (defaulting to `"http://fake-gcs-server:4443"`).
- [ ] `TestGCSContractStore` covers the following cases — each as a separate test method:
  - `put_file` then `get_file` returns the same content.
  - `file_exists` returns `True` after a `put_file`.
  - `file_exists` returns `False` for a key that was never written.
  - `list_files` returns all keys under the given prefix.
  - `list_files` returns `[]` for an unknown prefix.
  - `list_files` does not return keys outside the prefix.
  - A second `put_file` to the same key overwrites the content (`put_file` is idempotent).
  - `delete_file` removes the blob so `file_exists` returns `False` afterwards.
  - `delete_file` on a non-existent key does not raise.
- [ ] `just check` passes with the new tests running inside Docker Compose.

---

### TICKET-04 — `AzureContractStore` adapter and `Config` Azure fields

**Depends on:** TICKET-01 (establishes the pattern; no code dependency)
**Type:** Adapter

**Goal:**
Implement the full `AzureContractStore` and the three Azure config fields it needs.

**Files to create / modify:**
- `contract_sentinel/adapters/azure_contract_store.py` — create
- `contract_sentinel/config.py` — modify

**Done when:**
- [ ] `AzureContractStore(ContractStore)` exists with
  `__init__(self, connection_string: str | None, container: str | None, path: str)`.
- [ ] `azure.storage.blob` is lazy-imported inside `__init__` (not at module level).
- [ ] `__init__` raises `ValueError` with a descriptive message when `connection_string` is
  falsy, and separately when `container` is falsy.
- [ ] A `BlobServiceClient` is constructed via
  `BlobServiceClient.from_connection_string(connection_string)`.
- [ ] `get_file(key)` downloads the blob and returns content as a UTF-8 string.
- [ ] `put_file(key, content)` uploads the string with `overwrite=True`.
- [ ] `list_files(prefix)` returns all relative keys under the prefix, sorted by
  `props.last_modified` descending.
- [ ] `file_exists(key)` returns `True` / `False` without raising.
- [ ] `delete_file(key)` deletes the blob; catches
  `azure.core.exceptions.ResourceNotFoundError` and returns silently.
- [ ] All keys are relative — the store prepends `self._path + "/"` internally.
- [ ] `config.py` gains `azure_connection_string` (from `AZURE_STORAGE_CONNECTION_STRING`,
  `None` if absent), `azure_container` (from `SENTINEL_AZURE_CONTAINER`, `None` if absent),
  and `azure_path` (from `SENTINEL_AZURE_PATH`, default `"contract_tests"`).

---

### TICKET-05 — Azure wiring: `docker-compose.yml`, `factory.py`, `pyproject.toml`

**Depends on:** TICKET-04
**Type:** Infra

**Goal:**
Wire `AzureContractStore` into the factory, add the `Azurite` emulator to Docker Compose,
and register the `azure-blob` optional dependency.

**Files to create / modify:**
- `docker-compose.yml` — modify
- `contract_sentinel/factory.py` — modify
- `pyproject.toml` — modify
- `.env.local` — modify
- `tests/unit/test_factory.py` — modify
- `tests/unit/test_config.py` — modify

**Done when:**
- [ ] `docker-compose.yml` has an `azurite` service using image
  `mcr.microsoft.com/azure-storage/azurite:latest`, port `10000:10000`, and command
  `azurite-blob --blobHost 0.0.0.0`.
- [ ] The `app` service `depends_on` includes `azurite`.
- [ ] `factory.get_store()` has a `case "azure-blob":` branch that lazy-imports
  `AzureContractStore`, passes `config.azure_connection_string`, `config.azure_container`,
  and `config.azure_path`, and catches `ImportError` → `MissingDependencyError` with the
  message:
  `"store 'azure-blob' requires the azure-blob extra.\nInstall it with: pip install contract-sentinel[azure-blob]"`.
- [ ] `UnsupportedStorageError` message updated to
  `"Valid options: 's3', 'gcs', 'azure-blob'."`.
- [ ] `pyproject.toml` has an `azure-blob = ["azure-storage-blob>=12.0,<13.0"]` entry under
  `[project.optional-dependencies]`.
- [ ] `azure-storage-blob>=12.0,<13.0` is added to the `all` optional dep group.
- [ ] `azure-storage-blob>=12.0,<13.0` is added to `[dependency-groups] dev`.
- [ ] `.env.local` has `AZURE_STORAGE_CONNECTION_STRING` set to the Azurite well-known
  connection string (see design doc) and
  `SENTINEL_AZURE_CONTAINER=contract-sentinel-local-azure`.
- [ ] `test_factory.py` — new test: `get_store` with `SENTINEL_STORE=azure-blob` returns an
  `AzureContractStore` instance.
- [ ] `test_factory.py` — new test: `MissingDependencyError` raised when `azure.storage.blob`
  is absent (`monkeypatch.setitem(sys.modules, "azure.storage.blob", None)`).
- [ ] `test_factory.py` — existing `UnsupportedStorageError` message assertion updated to
  `"Valid options: 's3', 'gcs', 'azure-blob'."`.
- [ ] `test_config.py` — new tests asserting `config.azure_connection_string`,
  `config.azure_container`, and `config.azure_path` read from the correct env vars with
  correct defaults.
- [ ] `just check` passes.

---

### TICKET-06 — Azure integration tests

**Depends on:** TICKET-05
**Type:** Adapter

**Goal:**
Write the full integration test suite for `AzureContractStore` against Azurite, mirroring
the GCS and S3 test suites.

**Files to create / modify:**
- `tests/integration/conftest.py` — modify
- `tests/integration/test_adapters/test_azure_contract_store.py` — create

**Done when:**
- [ ] `conftest.py` has an `azure_container` fixture that creates a uniquely-named Blob
  container in Azurite via the `azure.storage.blob` client, yields the container name, and
  deletes all blobs + the container in teardown.
- [ ] `conftest.py` has an `azure_store` fixture that depends on `azure_container` and returns
  an `AzureContractStore` pointed at the test container with the Azurite connection string
  from `_AZURE_CONNECTION_STRING` (read from env with a hardcoded Azurite default fallback).
- [ ] `TestAzureContractStore` covers all the same cases as `TestGCSContractStore` (nine test
  methods — see TICKET-03 done-when list for the full enumeration).
- [ ] `just check` passes with the new tests running inside Docker Compose.
