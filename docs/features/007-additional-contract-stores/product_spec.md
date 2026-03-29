# Product Spec — Additional Contract Stores

**Feature slug:** `007-additional-contract-stores`
**Status:** `ready-for-dev`
**Created:** 2026-03-29

---

## Problem

Contract Sentinel only supports AWS S3 as a storage backend. Teams running on GCP or Azure
cannot adopt it without either spinning up S3 (a foreign cloud dependency) or maintaining a
fork. Adding GCS and Azure Blob removes the single biggest infrastructure blocker for
non-AWS shops.

---

## Goals

- Teams on GCP can point Contract Sentinel at a GCS bucket via `SENTINEL_STORE=gcs` and a
  handful of env vars, with zero code changes.
- Teams on Azure can do the same via `SENTINEL_STORE=azure-blob`.
- Existing S3 users are completely unaffected — no behaviour, interface, or env var changes.
- Installing `contract-sentinel[gcs]` or `contract-sentinel[azure-blob]` never conflicts with
  or downgrades the user's existing SDK installations.

---

## Non-Goals (V1)

- Multi-region or cross-provider replication.
- SQL/NoSQL backends — out of scope per `ideas.md`.
- Service-account JSON file auth for GCS — Application Default Credentials and explicit
  credentials via `GOOGLE_APPLICATION_CREDENTIALS` cover all practical cases.
- Azure Managed Identity auth — connection string covers Azurite (dev) and SAS/account-key
  (prod). Managed Identity is a follow-up.

---

## User-Facing Changes

Set `SENTINEL_STORE` to select the backend. No other CLI, decorator, or contract format
changes.

```bash
# GCS
SENTINEL_STORE=gcs
SENTINEL_GCS_BUCKET=my-contracts
SENTINEL_GCS_PATH=contract_tests          # optional, default: contract_tests

# Azure Blob
SENTINEL_STORE=azure-blob
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;
SENTINEL_AZURE_CONTAINER=my-contracts
SENTINEL_AZURE_PATH=contract_tests        # optional, default: contract_tests
```

---

## Acceptance Criteria

### GCS

- [ ] `pip install contract-sentinel[gcs]` with any `google-cloud-storage>=2.0,<3.0` installed
  does not downgrade or conflict.
- [ ] `sentinel publish` and `sentinel validate` work end-to-end against a real GCS bucket
  when `SENTINEL_STORE=gcs`.
- [ ] `GCSContractStore` passes the same five-method integration test suite as `S3ContractStore`,
  running against `fake-gcs-server` in Docker Compose.
- [ ] `get_file`, `put_file`, `list_files`, `file_exists`, `delete_file` all behave per the
  `ContractStore` ABC contracts — in particular `delete_file` is a no-op when the key does
  not exist.
- [ ] `list_files` returns keys ordered by last-modified descending.
- [ ] `just check` passes with `google-cloud-storage` in the dev dependency group.

### Azure Blob

- [ ] `pip install contract-sentinel[azure-blob]` with any `azure-storage-blob>=12.0,<13.0`
  installed does not downgrade or conflict.
- [ ] `sentinel publish` and `sentinel validate` work end-to-end against a real Azure Blob
  container when `SENTINEL_STORE=azure-blob`.
- [ ] `AzureContractStore` passes the same five-method integration test suite, running against
  `Azurite` in Docker Compose.
- [ ] `delete_file` is a no-op when the key does not exist.
- [ ] `list_files` returns keys ordered by last-modified descending.
- [ ] `just check` passes with `azure-storage-blob` in the dev dependency group.
