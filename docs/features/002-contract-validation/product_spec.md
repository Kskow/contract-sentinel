# Product Spec — Contract Validation

**Feature slug:** `002-contract-validation`
**Status:** `in-progress`
**Created:** 2026-03-16

---

## Problem

Teams using event-driven architectures have no lightweight way to verify that a producer's schema
is still compatible with what its consumers expect — without standing up a central broker like
Pact Broker. Breaking schema changes (renamed fields, type changes, removed required fields) go
undetected until runtime, causing production incidents.

Contract Sentinel solves this by letting teams mark their schema classes directly in code, store
contracts in their own S3 bucket, and validate compatibility automatically on every PR.

---

## Goals

- Let developers mark any Marshmallow schema class with a decorator that declares its topic and
  role (producer / consumer).
- Scan a repository at runtime to discover all marked schema classes under a configured path.
- Parse Marshmallow schemas into a canonical, framework-agnostic JSON contract format.
- Store and retrieve contract files in S3 so producer and consumer services can exchange
  contracts without sharing a codebase.
- Validate producer–consumer contract compatibility using the following rules: `TYPE_MISMATCH`,
  `REQUIREMENT_MISMATCH`, `NULLABILITY_MISMATCH`, `MISSING_FIELD`, `UNDECLARED_FIELD`,
  `DIRECTION_MISMATCH`, and four metadata rules all handled by `MetadataMismatchRule`:
  `METADATA_KEY_MISMATCH`, `METADATA_ALLOWED_VALUES_MISMATCH`, `METADATA_RANGE_MISMATCH`,
  `METADATA_LENGTH_MISMATCH`.
- Provide a `sentinel validate` CLI command that acts as a PR gate (exits `1` on violations).
- Provide a `sentinel publish` CLI command that pushes changed contracts to S3 after merge.
- Detect the schema framework automatically from each schema class at runtime — no framework
  configuration variable required. MVP supports Marshmallow only.

---

## Out of Scope

- Pydantic, dataclasses, and attrs parsers — deferred to post-release.
- Azure Blob and GCS storage adapters — deferred to post-release.
- AI Semantic Audit / Dual-Layer Validation — separate future feature.
- Schema drift detection and `WARNING`-severity rules (Postel's Law) — documented in
  `post-release.md`.
- Orphaned contract management / `sentinel prune` command — documented in `post-release.md`.
- GitHub Actions Step Summary Markdown output — documented in `post-release.md`.
- Local-only / offline validation mode — documented in `post-release.md`.
- `LocalContractStore` in-memory adapter — deferred; adapter integration tests use LocalStack
  directly.

---

## Acceptance Criteria

1. A class decorated with `@contract(topic="orders.created", role=Role.PRODUCER)` has a
   `__contract__` attribute containing the correct metadata.

2. The Loader discovers all marked classes under a configured path and returns their metadata;
   classes without the decorator are ignored.

3. `detect_framework(cls)` returns `Framework.MARSHMALLOW` for a Marshmallow schema class and
   raises `UnsupportedFrameworkError` for any other class, without importing any framework.

4. A Marshmallow schema is parsed into a `ContractSchema` value object with correct `name`, `type`,
   `is_required`, `is_nullable`, `default`, `metadata`, and nested `fields` for each field.

5. `sentinel publish-contracts` writes a canonical JSON contract file to S3 at the key
   `<topic>/<role>/<repo>/<class>.json` (the `SENTINEL_S3_PATH` prefix is prepended by
   `S3ContractStore` and never appears in the relative key exposed to callers).

6. `sentinel publish` is idempotent: running it twice on an unchanged schema produces exactly one
   S3 write (on the first run) and zero writes on the second.

7. `sentinel validate` exits `1` and prints a violation report when any breaking rule is triggered
   between a producer–consumer pair.

8. `sentinel validate` exits `0` and prints a passing summary when all contracts on all topics are
   compatible.

9. `sentinel validate-published-contracts` compares contracts already stored in S3 without
   scanning or parsing local files.

10. Supplying `framework = "unsupported"` or `storage.type = "unsupported"` in `pyproject.toml`
    raises a typed domain error with a message that lists the valid options.

11. All configuration is read from `pyproject.toml` and environment variables; no configuration is
    hardcoded.
