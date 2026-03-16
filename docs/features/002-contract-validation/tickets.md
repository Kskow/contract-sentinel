# Contract Validation — Dev Tickets

**Feature slug:** `002-contract-validation`
**Spec:** `docs/features/002-contract-validation/product_spec.md`
**Design:** `docs/features/002-contract-validation/design.md`
**Created:** 2026-03-16

---

## Architecture Notes

### Adapter Boundaries

Two external systems are abstracted behind ports:

- **S3** → `ContractStore` port → `S3ContractStore` adapter. Handles all object storage: read,
  write, list, existence check. The service layer never touches boto3 directly.
- **Marshmallow** → `SchemaParser` port → `MarshmallowParser` adapter. Converts a schema class
  into a `ContractSchema` domain object. The service layer never imports marshmallow directly.

### Data Flow

```
User decorates schema class with @contract_sentinel(...)
         ↓
sentinel validate / sentinel publish  (CLI entry)
         ↓
Load Settings (env vars — AWS_* + SENTINEL_* prefix)
         ↓
Factory → picks MarshmallowParser + S3ContractStore based on config
         ↓
Loader  → walks .py files, imports modules, returns marked classes
         ↓
Parser  → converts each class to ContractSchema (canonical format)
         ↓
  [validate]                          [publish]
Fetch latest S3 contracts           Hash local ContractSchema JSON
Run ValidationRules per pair        Compare hash vs current S3 object
Build ViolationReport               Write to S3 only if hash differs
Print report                        Log "no change" if identical
Exit 1 (violations) / 0 (pass)      Exit 0 always
```

### New Files

```
contract_sentinel/
├── settings.py
├── factory.py
├── domain/
│   ├── __init__.py
│   ├── marker.py
│   ├── loader.py
│   ├── contract.py
│   ├── validation.py
│   └── errors.py
├── ports/
│   ├── __init__.py
│   ├── contract_store.py
│   └── schema_parser.py
├── adapters/
│   ├── __init__.py
│   ├── s3_contract_store.py
│   └── marshmallow_parser.py
├── services/
│   ├── __init__.py
│   ├── validate.py
│   └── publish.py
└── cli/
    ├── __init__.py
    ├── main.py
    ├── validate.py
    └── publish.py

tests/
├── unit/
│   ├── test_settings.py
│   ├── test_marker.py
│   ├── test_contract.py
│   ├── test_validation_rules.py
│   ├── test_loader.py
│   ├── test_factory.py
│   ├── test_validate_service.py
│   └── test_publish_service.py
└── integration/
    ├── conftest.py            ← S3 bucket fixture (created in TICKET-08)
    ├── test_marshmallow_parser.py
    ├── test_s3_contract_store.py
    ├── test_cli_validate.py
    └── test_cli_publish.py
```

### Existing Patterns to Reuse

- Docker Compose + LocalStack are already running (`just docker-up`). Integration tests connect
  to LocalStack automatically via standard AWS SDK environment variables in `.env`.
- `just check` runs the full quality gate including integration tests — no new CI config needed
  for this feature.

### Distributed Systems Considerations

- **Idempotency (`publish`):** SHA-256 hash of canonical JSON (keys sorted with `sort_keys=True`)
  is computed locally and compared against the stored object before any write. Safe to run on
  every merge.
- **Version resolution:** `S3ContractStore.list(prefix)` returns keys sorted by `LastModified`
  descending — the first result is always the latest contract. No version string parsing needed.
- **Multi-producer:** The service layer fetches all objects under
  `contract_tests/<topic>/` and groups them by role. Each consumer is validated against every
  producer. Failure of any pair fails the run.

### IAM / Environment Variables Required

| Variable | Where set | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `.env` (local), CI secret | `"test"` for LocalStack |
| `AWS_SECRET_ACCESS_KEY` | `.env` (local), CI secret | `"test"` for LocalStack |
| `AWS_DEFAULT_REGION` | `.env` (local), CI env | `"us-east-1"` |
| `AWS_ENDPOINT_URL` | `.env` (local) | `"http://localhost:4566"` for LocalStack; absent in prod |
| `SENTINEL_NAME` | `.env` (local), CI env | Repository / project name; required |
| `SENTINEL_FRAMEWORK` | `.env` (local), CI env | Schema framework; defaults to `"marshmallow"` |
| `SENTINEL_S3_BUCKET` | `.env` (local), CI env | S3 bucket for contract storage; required |
| `SENTINEL_S3_PATH` | `.env` (local), CI env | S3 key prefix; defaults to `"contract_tests"` |

All AWS vars are already present in `.env.local`. Add the `SENTINEL_*` vars to `.env.local` for local dev. No new CI secrets needed for this feature.

---

## Tickets

### TICKET-01 — Config: Settings

**Depends on:** —
**Type:** Infra config

**Goal:**
Establish the single `Settings` class that every other layer depends on. All configuration comes
from environment variables — standard `AWS_*` vars for AWS credentials, and `SENTINEL_`-prefixed
vars for sentinel-specific options. No config files are read at runtime.

**Files to create / modify:**
- `contract_sentinel/settings.py` — create
- `tests/unit/test_settings.py` — create
- `pyproject.toml` — modify (add `pydantic-settings` via `uv add pydantic-settings`)

**Done when:**
- [ ] `settings.py` defines the `Settings` class only — no module-level instantiation.
      `Settings()` is only constructed inside CLI command handlers, never on import, so that
      importing any `contract_sentinel` module never crashes a user's environment
- [ ] `Settings` uses `pydantic-settings` `BaseSettings` with `env_prefix="SENTINEL_"`;
      AWS vars override the prefix via `validation_alias` (e.g. `Field(validation_alias="AWS_ACCESS_KEY_ID")`)
- [ ] Sentinel env vars map to clean attribute names without the prefix:
      `SENTINEL_NAME` → `name`, `SENTINEL_FRAMEWORK` → `framework`,
      `SENTINEL_S3_BUCKET` → `s3_bucket`, `SENTINEL_S3_PATH` → `s3_path`
- [ ] `Settings()` raises `ValidationError` at instantiation when `AWS_ACCESS_KEY_ID`,
      `AWS_SECRET_ACCESS_KEY`, `SENTINEL_NAME`, or `SENTINEL_S3_BUCKET` are absent
- [ ] `Settings()` defaults `aws_default_region` to `"us-east-1"` when `AWS_DEFAULT_REGION` is not set
- [ ] `Settings()` defaults `aws_endpoint_url` to `None` when `AWS_ENDPOINT_URL` is not set
- [ ] `Settings()` defaults `framework` to `"marshmallow"` when `SENTINEL_FRAMEWORK` is not set
- [ ] `Settings()` defaults `s3_path` to `"contract_tests"` when `SENTINEL_S3_PATH` is not set
- [ ] `just check` passes

---

### TICKET-02 — Domain: Marker

**Depends on:** —
**Type:** Domain

**Goal:**
Implement the `@contract_sentinel` decorator and `Role` enum that users apply to their schema
classes.

**Files to create / modify:**
- `contract_sentinel/domain/__init__.py` — create (empty)
- `contract_sentinel/domain/marker.py` — create
- `tests/unit/test_marker.py` — create

**Done when:**
- [ ] `Role` enum has exactly two members: `PRODUCER` and `CONSUMER`
- [ ] `@contract_sentinel(topic="t", role=Role.PRODUCER, version="1.0.0")` sets
      `__contract_sentinel__` on the decorated class
- [ ] `__contract_sentinel__` contains the exact `topic`, `role`, and `version` values
- [ ] Applying the decorator to a class does not alter any other class attribute
- [ ] `contract_sentinel/__init__.py` exports `contract_sentinel` and `Role` in `__all__` —
      these are the only public API symbols users need to import
- [ ] `just check` passes

---

### TICKET-03 — Domain: Contract Value Objects + Errors

**Depends on:** —
**Type:** Domain

**Goal:**
Define the canonical `ContractField` and `ContractSchema` value objects that every other layer
exchanges, plus the typed domain errors used by the factory.

**Files to create / modify:**
- `contract_sentinel/domain/contract.py` — create
- `contract_sentinel/domain/errors.py` — create
- `tests/unit/test_contract.py` — create

**Done when:**
- [ ] `UnknownFieldBehaviour` is a `str`-based `Enum` in `contract.py` with three members:
      `FORBID = "forbid"`, `IGNORE = "ignore"`, `ALLOW = "allow"` — these are the only values
      that appear in the canonical JSON format; no Marshmallow constants appear in this file
- [ ] `ContractField` is a dataclass with fields: `name`, `type`, `required`, `allow_none`,
      `default` (optional), `fields` (optional list of `ContractField`), `members` (optional list),
      `unknown` (`UnknownFieldBehaviour | None`, default `None` — only populated when
      `type == "object"`, carries the nested schema's own policy)
- [ ] `ContractSchema` is a dataclass with fields: `topic`, `role`, `version`, `repository`,
      `class_name`, `unknown` (`UnknownFieldBehaviour`, default `UnknownFieldBehaviour.FORBID`),
      `fields` (list of `ContractField`)
- [ ] `ContractSchema` can be serialised to a dict and round-tripped back without data loss
- [ ] `UnsupportedFrameworkError` and `UnsupportedStorageError` are defined as domain exceptions
      (subclass `Exception`) in `errors.py`
- [ ] `MissingDependencyError` is defined in `errors.py` — raised when an optional extra is
      required but not installed; message must include the `pip install` command as a hint
- [ ] `just check` passes

---

### TICKET-04 — Domain: Validation Rules

**Depends on:** TICKET-03
**Type:** Domain

**Goal:**
Implement the `Violation` dataclass, the `ValidationRule` Protocol, and all four MVP rule classes.

**Files to create / modify:**
- `contract_sentinel/domain/validation.py` — create
- `tests/unit/test_validation_rules.py` — create

**Done when:**
- [ ] `Violation` is a dataclass with fields: `rule`, `severity`, `field_path`, `producer` (dict),
      `consumer` (dict), `message`
- [ ] `ValidationRule` is a `Protocol` with method
      `check(producer_field, consumer_field) -> list[Violation]`
- [ ] `TypeMismatchRule.check()` returns a `CRITICAL` `Violation` when producer and consumer
      `type` differ, and returns `[]` when they match
- [ ] `RequirementMismatchRule.check()` returns a `CRITICAL` `Violation` when producer
      `required=False` and consumer `required=True` with no default, and returns `[]` otherwise
- [ ] `NullabilityMismatchRule.check()` returns a `CRITICAL` `Violation` when producer
      `allow_none=True` and consumer `allow_none=False`, and returns `[]` otherwise
- [ ] `MissingFieldRule.check()` returns a `CRITICAL` `Violation` when the field is absent from
      the producer but `required=True` with no default on the consumer, and returns `[]` otherwise
- [ ] `UndeclaredFieldRule` is instantiated with `consumer_unknown: UnknownFieldBehaviour`;
      `check()` returns a `CRITICAL` `Violation` when `consumer_field is None` (field absent from
      consumer) and `consumer_unknown == UnknownFieldBehaviour.FORBID`, and returns `[]` when
      `consumer_unknown` is `IGNORE` or `ALLOW` — no Marshmallow constants appear in this file
- [ ] Unit tests cover all three branches: `FORBID` produces a violation, `IGNORE` and `ALLOW`
      each return `[]`
- [ ] `just check` passes

---

### TICKET-05 — Ports: ContractStore + SchemaParser

**Depends on:** TICKET-03
**Type:** Port

**Goal:**
Define the two `Protocol` interfaces that decouple the service layer from all cloud and framework
dependencies.

**Files to create / modify:**
- `contract_sentinel/ports/__init__.py` — create (empty)
- `contract_sentinel/ports/contract_store.py` — create
- `contract_sentinel/ports/schema_parser.py` — create

**Done when:**
- [ ] `ContractStore` is a `Protocol` with methods: `get(key: str) -> str`,
      `put(key: str, content: str) -> None`, `list(prefix: str) -> list[str]`,
      `exists(key: str) -> bool`
- [ ] `SchemaParser` is a `Protocol` with method `parse(cls: type) -> ContractSchema`
- [ ] Both protocols are importable from `contract_sentinel.ports`
- [ ] `just check` passes

---

### TICKET-06 — Domain: Loader

**Depends on:** TICKET-02
**Type:** Domain

**Goal:**
Implement the import-based scanner that walks `.py` files and returns all classes marked with
`@contract_sentinel`.

**Files to create / modify:**
- `contract_sentinel/domain/loader.py` — create
- `tests/unit/test_loader.py` — create (uses temporary `.py` files via `tmp_path` fixture)

**Done when:**
- [ ] `load_marked_classes(path)` returns a list of classes whose `__contract_sentinel__`
      attribute is set, for all `.py` files under `path`
- [ ] Classes without `__contract_sentinel__` are not included in the result
- [ ] Non-`.py` files under `path` are silently skipped
- [ ] Classes in nested subdirectories under `path` are discovered
- [ ] `load_marked_classes` does not raise if a `.py` file fails to import — it logs a warning
      and continues
- [ ] `just check` passes

---

### TICKET-07 — Adapter: MarshmallowParser

**Depends on:** TICKET-03, TICKET-05
**Type:** Adapter

**Goal:**
Implement `MarshmallowParser`, the concrete `SchemaParser` adapter that converts a Marshmallow
schema class into a `ContractSchema`.

**Files to create / modify:**
- `contract_sentinel/adapters/__init__.py` — create (empty)
- `contract_sentinel/adapters/marshmallow_parser.py` — create
- `tests/integration/test_marshmallow_parser.py` — create
- `pyproject.toml` — modify (add `marshmallow` as optional extra via
  `uv add --optional marshmallow marshmallow`; also add convenience
  `all = ["marshmallow>=3.0", "boto3>=1.0"]` extra under `[project.optional-dependencies]`)

**Done when:**
- [ ] `marshmallow` is listed under `[project.optional-dependencies]` in `pyproject.toml`,
      not under `[project.dependencies]`
- [ ] `marshmallow_parser.py` does **not** import marshmallow at the top level — the import
      lives inside the class methods so that the module loads safely without the extra installed
- [ ] `MarshmallowParser` satisfies the `SchemaParser` Protocol (type-checker must agree)
- [ ] `parse(cls)` maps Marshmallow field types to canonical strings: `fields.String` → `"string"`,
      `fields.Integer` → `"integer"`, `fields.Boolean` → `"boolean"`, `fields.List` → `"list"`,
      `fields.Dict` → `"dict"`, nested `Schema` → `"object"`
- [ ] `parse(cls)` correctly sets `required=True` for fields with no default and `allow_none=False`
- [ ] `parse(cls)` correctly captures `default` when a marshmallow field has one
- [ ] `parse(cls)` populates `fields` recursively for a nested `Schema` field
- [ ] `parse(cls)` populates `members` with string values for an `EnumField`
- [ ] `parse(cls)` reads the top-level schema's effective unknown-field policy from the instantiated
      schema's `_meta.unknown` attribute (not from `class Meta` directly — inheritance must be
      respected) and maps it to `UnknownFieldBehaviour`: `marshmallow.RAISE → FORBID`,
      `marshmallow.EXCLUDE → IGNORE`, `marshmallow.INCLUDE → ALLOW`; defaults to `FORBID` when
      unset. The strings `"RAISE"`, `"EXCLUDE"`, `"INCLUDE"` must not appear outside this file.
- [ ] `parse(cls)` sets `ContractField.unknown` for any field whose `type == "object"` by applying
      the same mapping to that nested schema's `_meta.unknown`; leaves `None` for all other types
- [ ] Integration test: a Marshmallow schema defined inline in the test is parsed and the resulting
      `ContractSchema.fields` list matches the expected structure exactly
- [ ] Integration test: a schema with `class Meta: unknown = EXCLUDE` produces
      `ContractSchema.unknown == UnknownFieldBehaviour.IGNORE`
- [ ] Integration test: a schema with a nested schema carrying `class Meta: unknown = INCLUDE`
      produces the corresponding `ContractField.unknown == UnknownFieldBehaviour.ALLOW` on the
      object field
- [ ] `just check` passes

---

### TICKET-08 — Adapter: S3ContractStore

**Depends on:** TICKET-01, TICKET-05
**Type:** Adapter

**Goal:**
Implement `S3ContractStore`, the concrete `ContractStore` adapter that reads and writes contract
JSON files to S3, and set up the shared integration test fixture for LocalStack.

**Files to create / modify:**
- `contract_sentinel/adapters/s3_contract_store.py` — create
- `tests/integration/conftest.py` — create (S3 client + bucket fixture, reused by CLI tests)
- `tests/integration/test_s3_contract_store.py` — create
- `pyproject.toml` — modify (add `boto3` as optional extra via `uv add --optional s3 boto3`;
  also add `boto3>=1.0` to the `all` extra created in TICKET-07)

**Done when:**
- [ ] `boto3` is listed under `[project.optional-dependencies]` in `pyproject.toml`,
      not under `[project.dependencies]`
- [ ] `s3_contract_store.py` does **not** import boto3 at the top level — the import lives
      inside `__init__` so that the module loads safely without the extra installed
- [ ] `S3ContractStore` satisfies the `ContractStore` Protocol (type-checker must agree)
- [ ] `S3ContractStore` is constructed with a `path` argument (the `storage.path` config value)
      and prepends it to every S3 key — no S3 path segment is hardcoded inside the adapter
- [ ] `put(key, content)` writes `content` as a UTF-8 string to the correct S3 key
- [ ] `get(key)` returns the exact string previously written by `put`
- [ ] `exists(key)` returns `True` after a `put` and `False` for a key that was never written
- [ ] `list(prefix)` returns all keys sharing the prefix, ordered by `LastModified` descending
      (most recently written first)
- [ ] `list(prefix)` returns `[]` when no keys match the prefix
- [ ] Integration test: `put` → `get` → `exists` → `list` sequence asserts all of the above
      against a real LocalStack S3 bucket created by the `conftest.py` fixture
- [ ] `conftest.py` creates the test bucket before each test and deletes all objects after
- [ ] `just check` passes

---

### TICKET-09 — Factory

**Depends on:** TICKET-01, TICKET-03, TICKET-07, TICKET-08
**Type:** Service

**Goal:**
Implement the adapter factory that maps `Settings` values to concrete adapter instances —
the single place in the codebase that knows which config value means which class, and the single
place that handles missing optional extras with actionable error messages.

**Files to create / modify:**
- `contract_sentinel/factory.py` — create
- `tests/unit/test_factory.py` — create

**Done when:**
- [ ] `get_parser(settings)` uses a **lazy import** inside the `if` branch — marshmallow is only
      imported if `settings.framework == "marshmallow"`, so the factory module itself is safe to
      import without the extra installed
- [ ] `get_parser(settings)` returns a `MarshmallowParser` instance when `settings.framework == "marshmallow"`
- [ ] `get_parser(settings)` raises `MissingDependencyError` (not a bare `ImportError`) with the
      message `"framework='marshmallow' requires the marshmallow extra.\nInstall it with: pip install contract-sentinel[marshmallow]"`
      when marshmallow is not installed
- [ ] `get_parser(settings)` raises `UnsupportedFrameworkError` for an unrecognised `framework`
      value, with a message listing `"marshmallow"` as the valid option
- [ ] `get_store(settings)` uses a **lazy import** inside the `if` branch — boto3 is only
      imported when the `s3` extra is the active storage backend
- [ ] `get_store(settings)` returns an `S3ContractStore` instance constructed with
      `bucket=settings.s3_bucket`, `path=settings.s3_path`, and AWS credentials from `settings`
- [ ] `get_store(settings)` raises `MissingDependencyError` with the message
      `"storage backend 's3' requires the s3 extra.\nInstall it with: pip install contract-sentinel[s3]"`
      when boto3 is not installed
- [ ] `get_store(settings)` raises `UnsupportedStorageError` for an unrecognised storage backend,
      with a message listing `"s3"` as the valid option
- [ ] `just check` passes

---

### TICKET-10 — Service: validate_contracts

**Depends on:** TICKET-04, TICKET-05, TICKET-06, TICKET-09
**Type:** Service

**Goal:**
Implement the `validate_contracts` use-case that orchestrates scanning, fetching remote contracts,
running all validation rules, and returning a structured report.

**Files to create / modify:**
- `contract_sentinel/services/__init__.py` — create (empty)
- `contract_sentinel/services/validate.py` — create
- `tests/unit/test_validate_service.py` — create

**Done when:**
- [ ] `validate_contracts(store, parser, loader, settings)` returns a `ValidationReport` dataclass
      with `status="PASSED"`, empty `violations`, when producer and consumer schemas are compatible
- [ ] Returns `status="FAILED"` with the correct `Violation` objects when a breaking rule fires
- [ ] Each consumer is validated against every producer sharing the same topic — a violation in
      any pair sets `status="FAILED"`
- [ ] When `skip_scan=True`, the function fetches contracts from `store` only and skips calling
      `loader` and `parser`
- [ ] Unit tests inject `create_autospec(ContractStore)` and `create_autospec(SchemaParser)` —
      no LocalStack required
- [ ] `just check` passes

---

### TICKET-11 — Service: publish_contracts

**Depends on:** TICKET-05, TICKET-06, TICKET-09
**Type:** Service

**Goal:**
Implement the `publish_contracts` use-case that writes new or changed contracts to S3 and skips
unchanged ones using SHA-256 content hashing.

**Files to create / modify:**
- `contract_sentinel/services/publish.py` — create
- `tests/unit/test_publish_service.py` — create

**Done when:**
- [ ] `publish_contracts(store, parser, loader, settings)` calls `store.put()` for each
      `ContractSchema` whose SHA-256 hash (of `sort_keys=True` JSON) differs from the current
      S3 object
- [ ] `store.put()` is **not** called for a schema whose hash matches the current S3 object
- [ ] `publish_contracts` returns a `PublishReport` with counts of `written` and `skipped` schemas
- [ ] When a schema does not yet exist in S3 (`store.exists()` returns `False`), it is always
      written
- [ ] Unit tests inject `create_autospec(ContractStore)` — no LocalStack required
- [ ] `just check` passes

---

### TICKET-12 — CLI: sentinel validate

**Depends on:** TICKET-01, TICKET-10
**Type:** CLI

**Goal:**
Expose `validate_contracts` as the `sentinel validate` CLI command, wire config loading and
factory adapter construction, and write the integration test against LocalStack.

**Files to create / modify:**
- `contract_sentinel/cli/__init__.py` — create (empty)
- `contract_sentinel/cli/main.py` — create (Typer app object, registered as `sentinel` script)
- `contract_sentinel/cli/validate.py` — create
- `tests/integration/test_cli_validate.py` — create
- `pyproject.toml` — modify (`uv add typer`; add `[project.scripts] sentinel = "contract_sentinel.cli.main:app"`)

**Done when:**
- [ ] `Settings()` is constructed **inside** the command handler function, not at module level —
      importing `contract_sentinel.cli.validate` must not trigger any env var reads
- [ ] `sentinel validate` runs the full validate flow and prints the violation report to stdout
- [ ] `sentinel validate` exits with code `1` when at least one violation is found
- [ ] `sentinel validate` exits with code `0` when all contracts pass
- [ ] `sentinel validate --skip-scan` skips local scanning and compares only S3 contracts
- [ ] Integration test uses `typer.testing.CliRunner` with a real LocalStack bucket pre-seeded
      with a producer and consumer contract; asserts exit code and stdout content
- [ ] `just check` passes

---

### TICKET-13 — CLI: sentinel publish

**Depends on:** TICKET-01, TICKET-11, TICKET-12
**Type:** CLI

**Goal:**
Expose `publish_contracts` as the `sentinel publish` CLI command and write the integration test
against LocalStack.

**Files to create / modify:**
- `contract_sentinel/cli/publish.py` — create
- `tests/integration/test_cli_publish.py` — create

**Done when:**
- [ ] `sentinel publish` scans, parses, and writes new or changed contracts to S3
- [ ] `sentinel publish` prints `"no change, skipping: <filename>"` for each unchanged schema
- [ ] `sentinel publish` exits `0` whether or not any schemas were written
- [ ] Integration test: run `sentinel publish` twice against LocalStack with the same schemas;
      assert exactly one S3 `put` on the first run and zero on the second (idempotency)
- [ ] `just check` passes
