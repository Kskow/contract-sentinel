# Design — Additional Contract Stores

## Adapter Boundary

Both new stores extend `ContractStore(ABC)` from `adapters/contract_store.py` — the same
abstract base that `S3ContractStore` implements. No domain, service, or CLI changes. The only
wiring points are `factory.py` (new `case` branches) and `config.py` (new env var fields).
This is the pattern documented in `contributors/how-to-add-a-contract-store.md`.

---

## Store Names (SENTINEL_STORE)

| Value | Store class | Extra |
|---|---|---|
| `s3` | `S3ContractStore` (existing) | `contract-sentinel[s3]` |
| `gcs` | `GCSContractStore` (new) | `contract-sentinel[gcs]` |
| `azure-blob` | `AzureContractStore` (new) | `contract-sentinel[azure-blob]` |

---

## GCS — Design

### SDK and auth

Package: `google-cloud-storage>=2.0,<3.0`. Lazy-imported inside `GCSContractStore.__init__`.

For production, the standard `google.cloud.storage.Client()` constructor respects
`GOOGLE_APPLICATION_CREDENTIALS` and Application Default Credentials automatically — no
explicit credential fields are needed in `Config` or the constructor.

For local development (against `fake-gcs-server`), the client must be constructed with
`AnonymousCredentials` and pointed at the emulator endpoint:

```python
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

client = storage.Client(
    credentials=AnonymousCredentials(),
    project="local",
    client_options={"api_endpoint": endpoint_url},
)
```

`GCSContractStore.__init__` accepts an optional `endpoint_url: str | None` parameter. When
`None`, a standard credential-discovery client is constructed; when set, the anonymous
emulator client is constructed. The factory reads this from `config.gcs_endpoint_url`.

### Key semantics

Keys are relative — `GCSContractStore` prepends `self._path + "/"` for every GCS operation,
identical to how `S3ContractStore._full_key` works.

### `delete_file` — no-op contract

`bucket.blob(full_key).delete()` raises `google.cloud.exceptions.NotFound` when the blob is
absent. Catch it and return silently.

### `list_files` — sort order

`client.list_blobs(bucket_name, prefix=full_prefix)` returns an iterator of `Blob` objects.
Sort by `blob.updated` (a `datetime`) descending before stripping the path prefix and
returning the relative key list.

### Config fields

| `Config` attribute | Env var | Default | Notes |
|---|---|---|---|
| `gcs_bucket` | `SENTINEL_GCS_BUCKET` | `None` | Required; raises `ValueError` if absent |
| `gcs_path` | `SENTINEL_GCS_PATH` | `"contract_tests"` | |
| `gcs_endpoint_url` | `GCS_ENDPOINT_URL` | `None` | Set only for local emulator |

### Emulator — `fake-gcs-server`

Docker image: `fsouza/fake-gcs-server`. Port: `4443`.

The image requires `-external-url` to match the hostname containers use to reach it, so
GCS client redirect URLs resolve correctly:

```yaml
fake-gcs-server:
  image: fsouza/fake-gcs-server:latest
  ports:
    - "4443:4443"
  command: -scheme http -port 4443 -external-url http://fake-gcs-server:4443
```

The `app` service `depends_on` list must include `fake-gcs-server`.

`.env.local` additions:
```
GCS_ENDPOINT_URL=http://fake-gcs-server:4443
SENTINEL_GCS_BUCKET=contract-sentinel-local-gcs
```

---

## Azure Blob — Design

### SDK and auth

Package: `azure-storage-blob>=12.0,<13.0`. Lazy-imported inside `AzureContractStore.__init__`.

A **connection string** is used as the single auth mechanism for V1 — it covers both Azurite
(dev) and production (account key or SAS). The full `BlobServiceClient` is constructed via
`BlobServiceClient.from_connection_string(connection_string)`.

`AzureContractStore.__init__` accepts `connection_string: str`, `container: str`, and
`path: str`. The factory reads these from `config`.

### Key semantics

Same relative-key / internal-prefix pattern as S3 and GCS.

### `delete_file` — no-op contract

`blob_client.delete_blob()` raises `azure.core.exceptions.ResourceNotFoundError` when the
blob is absent. Catch it and return silently.

### `list_files` — sort order

`container_client.list_blobs(name_starts_with=full_prefix)` returns an iterable of
`BlobProperties` objects. Sort by `props.last_modified` (a timezone-aware `datetime`)
descending, strip the path prefix, return relative keys.

### Config fields

| `Config` attribute | Env var | Default | Notes |
|---|---|---|---|
| `azure_connection_string` | `AZURE_STORAGE_CONNECTION_STRING` | `None` | Required when `SENTINEL_STORE=azure-blob` |
| `azure_container` | `SENTINEL_AZURE_CONTAINER` | `None` | Required; raises `ValueError` if absent |
| `azure_path` | `SENTINEL_AZURE_PATH` | `"contract_tests"` | |

### Emulator — Azurite

Docker image: `mcr.microsoft.com/azure-storage/azurite`. Port: `10000` (Blob service only).

```yaml
azurite:
  image: mcr.microsoft.com/azure-storage/azurite:latest
  ports:
    - "10000:10000"
  command: azurite-blob --blobHost 0.0.0.0
```

The `app` service `depends_on` list must include `azurite`.

Azurite well-known connection string (static, safe to commit):
```
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;
```

`.env.local` additions:
```
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;
SENTINEL_AZURE_CONTAINER=contract-sentinel-local-azure
```

---

## `UnsupportedStorageError` Message — Incremental Updates

The error message in `get_store()` lists valid options. It must be updated in each wiring
ticket so it stays accurate:

| After ticket | Message |
|---|---|
| Baseline | `"Valid options: 's3'."` |
| TICKET-02 (GCS wired) | `"Valid options: 's3', 'gcs'."` |
| TICKET-05 (Azure wired) | `"Valid options: 's3', 'gcs', 'azure-blob'."` |

The unit test in `test_factory.py` that asserts the exact error string must be updated in each
of those tickets.

---

## Integration Test Fixture Pattern

Follow the `s3_store` / `s3_bucket` fixture pattern in `tests/integration/conftest.py`:

- A bucket/container fixture creates a uniquely-named resource, yields the name, and deletes
  all contents + the resource in teardown.
- A store fixture depends on the bucket/container fixture and yields a fully-configured store
  instance.
- Both fixtures use `function` scope (default) so tests are isolated.

The `_ENDPOINT_URL`-style constant pattern should be replicated for each new emulator:
```python
_GCS_ENDPOINT_URL = os.environ.get("GCS_ENDPOINT_URL", "http://fake-gcs-server:4443")
_AZURE_CONNECTION_STRING = os.environ.get(
    "AZURE_STORAGE_CONNECTION_STRING",
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;..."
)
```

---

## Full File Changeset

| File | Action |
|---|---|
| `contract_sentinel/adapters/gcs_contract_store.py` | **Create** — `GCSContractStore` |
| `contract_sentinel/adapters/azure_contract_store.py` | **Create** — `AzureContractStore` |
| `contract_sentinel/config.py` | Add GCS and Azure config fields |
| `contract_sentinel/factory.py` | Add `case "gcs":` and `case "azure-blob":` branches |
| `pyproject.toml` | Add `gcs` and `azure-blob` optional dep groups; update `all`; add to dev group |
| `docker-compose.yml` | Add `fake-gcs-server` and `azurite` services; update `app.depends_on` |
| `.env.local` | Add GCS and Azure env var defaults |
| `tests/integration/conftest.py` | Add `gcs_bucket`, `gcs_store`, `azure_container`, `azure_store` fixtures |
| `tests/integration/test_adapters/test_gcs_contract_store.py` | **Create** — `TestGCSContractStore` |
| `tests/integration/test_adapters/test_azure_contract_store.py` | **Create** — `TestAzureContractStore` |
| `tests/unit/test_factory.py` | Add GCS and Azure store tests; update `UnsupportedStorageError` message assertion |
| `tests/unit/test_config.py` | Add tests for new GCS and Azure config fields |
