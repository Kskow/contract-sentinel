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
versioned contracts in their own S3 bucket, and validate compatibility automatically on every PR.

---

## Goals

- Let developers mark any Marshmallow schema class with a decorator that declares its topic, role
  (producer / consumer), and version.
- Scan a repository at runtime to discover all marked schema classes under a configured path.
- Parse Marshmallow schemas into a canonical, framework-agnostic JSON contract format.
- Store and retrieve versioned contract files in S3 so producer and consumer services can exchange
  contracts without sharing a codebase.
- Validate producer–consumer contract compatibility using five rules: `TYPE_MISMATCH`,
  `REQUIREMENT_MISMATCH`, `NULLABILITY_MISMATCH`, `MISSING_FIELD`, `UNDECLARED_FIELD`, and
  `METADATA_MISMATCH`.
- Provide a `sentinel validate` CLI command that acts as a PR gate (exits `1` on violations).
- Provide a `sentinel publish` CLI command that pushes changed contracts to S3 after merge.
- Read all tool configuration from `[tool.sentinel]` in `pyproject.toml`, with environment
  variable overrides for secrets.

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

1. A class decorated with `@contract(topic="orders.created", role=Role.PRODUCER,
   version="1.0.0")` has a `__contract__` attribute containing the correct metadata.

2. The Loader discovers all marked classes under a configured path and returns their metadata;
   classes without the decorator are ignored.

3. A Marshmallow schema is parsed into a `ContractSchema` value object with correct `name`, `type`,
   `is_required`, `is_nullable`, `default`, `metadata`, and nested `fields` for each field.

4. `sentinel publish` writes a canonical JSON contract file to S3 at the path
   `contract_tests/<topic>/<version>/<role>_<repo>_<class>.json`.

5. `sentinel publish` is idempotent: running it twice on an unchanged schema produces exactly one
   S3 write (on the first run) and zero writes on the second.

6. `sentinel validate` exits `1` and prints a violation report when any breaking rule is triggered
   between a producer–consumer pair.

7. `sentinel validate` exits `0` and prints a passing summary when all contracts on all topics are
   compatible.

8. `sentinel validate --skip-scan` compares contracts already stored in S3 without scanning or
   parsing local files.

9. Supplying `framework = "unsupported"` or `storage.type = "unsupported"` in `pyproject.toml`
   raises a typed domain error with a message that lists the valid options.

10. All configuration is read from `pyproject.toml` and environment variables; no configuration is
    hardcoded.
