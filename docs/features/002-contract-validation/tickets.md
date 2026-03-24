# Contract Validation — Dev Tickets

**Feature slug:** `002-contract-validation`
**Spec:** `docs/features/002-contract-validation/product_spec.md`
**Design:** `docs/features/002-contract-validation/design.md`
**Created:** 2026-03-16

---

## Architecture Notes

### Adapter Boundaries

Two external systems are abstracted behind ABCs co-located with their implementations:

- **S3** → `ContractStore(ABC)` + `S3ContractStore` in `adapters/contract_store.py`. Handles all
  object storage: read, write, list, existence check. The service layer never touches boto3 directly.
- **Marshmallow** → `SchemaParser(ABC)` + `Marshmallow3Parser` in `adapters/schema_parser.py`.
  Converts a schema class into a `ContractSchema` domain object. The service layer never imports
  marshmallow directly.

### Data Flow

```
User decorates schema class with @contract(...)
         ↓
sentinel validate-local / sentinel validate-published / sentinel publish  (CLI entry)
         ↓
Load Config (env vars — AWS_*, S3_BUCKET, SENTINEL_* prefix)
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
├── config.py
├── factory.py
├── domain/
│   ├── __init__.py
│   ├── participant.py
│   ├── loader.py
│   ├── schema.py
│   ├── rules/
│   │   ├── rule.py                   ← Rule(ABC)
│   │   ├── violation.py
│   │   ├── engine.py                 ← validate_pair / validate_group + recursion
│   │   ├── type_mismatch.py
│   │   ├── nullability_mismatch.py
│   │   ├── requirement_mismatch.py
│   │   ├── direction_mismatch.py
│   │   ├── metadata_mismatch.py      ← allowed_values, range, length + generic key checks
│   │   ├── missing_field.py
│   │   ├── undeclared_field.py
│   │   └── counterpart_mismatch.py   ← fires when producer has no matching consumer (or vice versa)
│   ├── framework.py
│   └── errors.py
├── adapters/
│   ├── __init__.py
│   ├── contract_store.py      ← ContractStore(ABC) + S3ContractStore
│   └── schema_parser.py       ← SchemaParser(ABC) + Marshmallow3Parser
├── services/
│   ├── __init__.py
│   ├── validate.py            ← validate_local_contracts, validate_published_contracts ✅
│   └── publish.py             ← publish_contracts ✅
└── cli/
    ├── __init__.py
    ├── main.py                ← Typer app entry-point, registered as `sentinel` script ✅
    ├── validate.py            ← sentinel validate-local / sentinel validate-published ✅
    └── publish.py             ← sentinel publish ✅

tests/
├── conftest.py                        ← clean_sys_modules fixture (suite-wide)
├── unit/
│   ├── test_domain/
│   │   ├── test_participant.py
│   │   ├── test_schema.py
│   │   ├── test_loader.py
│   │   ├── test_framework.py
│   │   └── test_rules/
│   │       ├── helpers.py
│   │       ├── test_violation.py
│   │       ├── test_type_mismatch.py
│   │       ├── test_nullability_mismatch.py
│   │       ├── test_requirement_mismatch.py
│   │       ├── test_direction_mismatch.py
│   │       ├── test_metadata_mismatch.py  ← covers allowed_values, range, length + generic key
│   │       ├── test_missing_field.py
│   │       ├── test_undeclared_field.py
│   │       ├── test_counterpart_mismatch.py
│   │       └── test_engine.py
│   ├── test_config.py
│   ├── test_factory.py
│   ├── test_services/
│   │   ├── test_validate.py           ✅
│   │   └── test_publish.py            ✅
│   └── test_cli/
│       └── test_publish.py            ✅
└── integration/
    ├── conftest.py                    ← s3_client, s3_bucket, s3_store fixtures
    ├── test_adapters/
    │   ├── test_contract_store.py
    │   └── test_schema_parser.py
    └── test_cli/
        ├── test_validate.py           ✅
        └── test_publish.py            ← pending (TICKET-13)
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
- **Multi-producer:** The service layer fetches all objects under `contract_tests/<topic>/` and
  groups them by role. Each consumer is validated against every producer on that topic.
  Failure of any pair fails the run.

### IAM / Environment Variables Required

| Variable | Where set | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `.env` (local), CI secret | `"test"` for LocalStack |
| `AWS_SECRET_ACCESS_KEY` | `.env` (local), CI secret | `"test"` for LocalStack |
| `AWS_DEFAULT_REGION` | `.env` (local), CI env | `"us-east-1"` |
| `AWS_ENDPOINT_URL` | `.env` (local) | `"http://localhost:4566"` for LocalStack; absent in prod |
| `SENTINEL_NAME` | `.env` (local), CI env | Repository / project name; required |
| `S3_BUCKET` | `.env` (local), CI env | S3 bucket for contract storage; required |
| `SENTINEL_S3_PATH` | `.env` (local), CI env | S3 key prefix; defaults to `"contract_tests"` |

All AWS vars are already present in `.env.local`. Add the `SENTINEL_*` vars to `.env.local` for local dev. No new CI secrets needed for this feature.

---

## Tickets

### TICKET-01 — Config

**Depends on:** —
**Type:** Infra config
**Status: ✅ Done**

**Goal:**
Establish the single `Config` class that every other layer depends on. All configuration comes
from environment variables — standard `AWS_*` vars for AWS credentials, `S3_BUCKET` for storage,
and `SENTINEL_`-prefixed vars for Sentinel-specific options. No config files are read at runtime.

**Files to create / modify:**
- `contract_sentinel/config.py` — create
- `tests/unit/test_config.py` — create

**Done when:**
- [x] `config.py` defines the `Config` class only — no module-level instantiation.
      `Config()` is only constructed inside CLI command handlers, never on import, so that
      importing any `contract_sentinel` module never crashes a user's environment
- [x] `Config.__init__` reads all values from `os.environ` directly — no third-party config library
- [x] Required variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`,
      `SENTINEL_NAME`) raise `ValueError` at instantiation when absent
- [x] `Config()` defaults `aws_default_region` to `"us-east-1"` when `AWS_DEFAULT_REGION` is not set
- [x] `Config()` defaults `aws_endpoint_url` to `None` when `AWS_ENDPOINT_URL` is not set
- [x] `Config()` defaults `s3_path` to `"contract_tests"` when `SENTINEL_S3_PATH` is not set
- [x] `just check` passes

---

### TICKET-02 — Domain: Marker

**Depends on:** —
**Type:** Domain
**Status: ✅ Done**

**Goal:**
Implement the `@contract` decorator and `Role` enum that users apply to their schema
classes.

**Files to create / modify:**
- `contract_sentinel/domain/__init__.py` — create (empty)
- `contract_sentinel/domain/participant.py` — create
- `tests/unit/test_participant.py` — create

**Done when:**
- [x] `Role` enum has exactly two members: `PRODUCER` and `CONSUMER`
- [x] `@contract(topic="t", role=Role.PRODUCER)` sets
      `__contract__` on the decorated class
- [x] `__contract__` contains the exact `topic` and `role` values
- [x] Applying the decorator to a class does not alter any other class attribute
- [x] `contract_sentinel/__init__.py` exports `contract` and `Role` in `__all__` —
      these are the only public API symbols users need to import
- [x] `just check` passes

---

### TICKET-03 — Domain: Contract Value Objects + Errors

**Depends on:** —
**Type:** Domain
**Status: ✅ Done**

**Goal:**
Define the canonical `ContractField` and `ContractSchema` value objects that every other layer
exchanges, plus the typed domain errors used by the factory.

**Files to create / modify:**
- `contract_sentinel/domain/schema.py` — create
- `contract_sentinel/domain/errors.py` — create
- `tests/unit/test_schema.py` — create

**Done when:**
- [x] `UnknownFieldBehaviour` is a `str`-based `Enum` in `schema.py` with three members:
      `FORBID = "forbid"`, `IGNORE = "ignore"`, `ALLOW = "allow"` — these are the only values
      that appear in the canonical JSON format; no Marshmallow constants appear in this file
- [x] `ContractField` is a dataclass with fields: `name`, `type`, `is_required`, `is_nullable`,
      `format` (optional `str` — JSON Schema format string refining `type`; omitted from
      serialised JSON when `None`), `default` (uses `MISSING` sentinel when absent — distinct from
      `default=None`), `fields` (optional list of `ContractField`), `metadata` (optional
      `dict[str, Any]` for type-specific extras), `unknown` (`UnknownFieldBehaviour | None` —
      only populated when `type == "object"`, carries the nested schema's own policy), `values`
      (optional sequence of allowed enum member values — populated only for enum fields)
- [x] `ContractSchema` is a dataclass with fields: `topic`, `role`, `repository`,
      `class_name`, `unknown` (`UnknownFieldBehaviour`), `fields` (list of `ContractField`) —
      no default values; always constructed with explicit arguments
- [x] `ContractSchema` can be serialised to a dict and round-tripped back without data loss
- [x] `UnsupportedFrameworkError` and `UnsupportedStorageError` are defined as domain exceptions
      (subclass `Exception`) in `errors.py`
- [x] `MissingDependencyError` is defined in `errors.py` — raised when an optional extra is
      required but not installed; message must include the `pip install` command as a hint
- [x] `just check` passes

---

### TICKET-03a — Domain: Framework Detector

**Depends on:** TICKET-03
**Type:** Domain
**Status:** ✅ Done

**Goal:**
Implement automatic schema framework detection so the service layer never needs a
`SENTINEL_FRAMEWORK` config value. Detection is pure class inspection — no framework is imported.

**Files to create / modify:**
- `contract_sentinel/domain/framework.py` — create
- `tests/unit/domain/test_framework.py` — create

**Done when:**
- [x] `Framework` is a `StrEnum` in `framework.py` with a single MVP member: `MARSHMALLOW = "marshmallow"`
- [x] `detect_framework(cls)` returns `Framework.MARSHMALLOW` when `cls` has `_declared_fields`
- [x] `detect_framework(cls)` raises `UnsupportedFrameworkError` for an unrecognised class,
      with a message that includes the class name and lists supported frameworks
- [x] No marshmallow or pydantic import appears anywhere in `detector.py`
- [x] `just check` passes

---

### TICKET-04 — Domain: Validation Rules

**Depends on:** TICKET-03
**Type:** Domain
**Status: ✅ Done**

**Goal:**
Implement the `Violation` dataclass, the single `Rule` ABC, and all rule classes.

**Files created:**
- `contract_sentinel/domain/rules/violation.py`
- `contract_sentinel/domain/rules/rule.py` — `Rule(ABC)`
- `contract_sentinel/domain/rules/` — one module per rule class
- `tests/unit/domain/rules/test_violation.py`
- `tests/unit/domain/rules/` — one test module per rule class

**Done when:**
- [x] `Violation` is a dataclass with fields: `rule`, `severity`, `field_path`, `producer` (dict),
      `consumer` (dict), `message`; exposes `to_dict() -> dict[str, Any]`
- [x] Single `Rule(ABC)` in `rules/rule.py` with signature
      `check(producer: ContractField | None, consumer: ContractField | None) -> list[Violation]`.
      Rules self-determine behaviour based on which side is `None` — no separate
      `ProducerOnlyRule` or `ConsumerOnlyRule` ABCs exist
- [x] `TypeMismatchRule` returns a `CRITICAL` violation when `producer.type != consumer.type`;
      returns `[]` when either side is `None`
- [x] `RequirementMismatchRule` returns a `CRITICAL` violation when `producer.is_required=False`
      and `consumer.is_required=True` with no default; returns `[]` when either side is `None`
- [x] `NullabilityMismatchRule` returns a `CRITICAL` violation when `producer.is_nullable=True`
      and `consumer.is_nullable=False`; returns `[]` when either side is `None`
- [x] `MissingFieldRule` returns a `CRITICAL` violation when `producer is None` and
      `consumer.is_required=True` with no default; returns `[]` when `producer is not None`
- [x] `UndeclaredFieldRule` returns a `CRITICAL` violation when `consumer.unknown == FORBID`;
      `consumer` is the *parent* container object (not a matched field) — its `.unknown` policy
      determines whether the absence is a violation; returns `[]` for `IGNORE`, `ALLOW`, or unset
- [x] `MetadataMismatchRule` is the single entry-point for all metadata validation. It dispatches
      on the metadata key: `allowed_values` → `METADATA_ALLOWED_VALUES_MISMATCH` (fires when the
      producer can emit a value the consumer does not accept, or when the producer is unconstrained
      but the consumer is); `range` → `METADATA_RANGE_MISMATCH` (fires when the producer's numeric
      range is wider than the consumer's, including inclusivity boundaries); `length` →
      `METADATA_LENGTH_MISMATCH` (fires when the producer's string/array length range is wider,
      supporting `min`, `max`, and `equal` constraints); all other keys → `METADATA_KEY_MISMATCH`
      (simple equality check). Returns `[]` when either side is `None`
- [x] `DirectionMismatchRule` returns a `CRITICAL` violation when a field is `load_only` in the
      producer (never serialised) but the consumer expects to receive it; returns `[]` when either
      side is `None`
- [x] `NestedFieldRule` recursively applies all rules to sub-fields of nested objects; iterates
      the union of producer and consumer field names in a single pass (producer declaration order
      first, consumer-only fields appended); `UndeclaredFieldRule` runs in a separate pass
      receiving the parent consumer object so it can read `.unknown`
- [x] `just check` passes

---

### TICKET-05 — Ports: ContractStore + SchemaParser

**Depends on:** TICKET-03
**Type:** Port
**Status: ✅ Done**

**Goal:**
Define the two `ABC` interfaces that decouple the service layer from all cloud and framework
dependencies.

**Files to create / modify:**
- `contract_sentinel/ports/__init__.py` — create (empty)
- `contract_sentinel/ports/contract_store.py` — create
- `contract_sentinel/ports/schema_parser.py` — create

**Done when:**
- [x] `ContractStore` is an `ABC` with methods: `get_file(key: str) -> str`,
      `put_file(key: str, content: str) -> None`, `list_files(prefix: str) -> list[str]`,
      `file_exists(key: str) -> bool`
- [x] `SchemaParser` is an `ABC` with method `parse(cls: type) -> ContractSchema`
- [x] Both ABCs are importable from their respective modules under `contract_sentinel.ports`
- [x] `just check` passes

---

### TICKET-06 — Domain: Loader

**Depends on:** TICKET-02
**Type:** Domain
**Status: ✅ Done**

**Goal:**
Implement the import-based scanner that walks `.py` files and returns all classes marked with
`@contract`.

**Files to create / modify:**
- `contract_sentinel/domain/loader.py` — create
- `tests/unit/domain/test_loader.py` — create (uses temporary `.py` files via `tmp_path` fixture)
- `tests/conftest.py` — create (`clean_sys_modules` fixture, shared across the suite)

**Done when:**
- [x] `load_marked_classes(path)` returns a list of classes whose `__contract__`
      attribute is set, for all `.py` files under `path`
- [x] Classes without `__contract__` are not included in the result
- [x] Non-`.py` files under `path` are silently skipped
- [x] Classes in nested subdirectories under `path` are discovered
- [x] `load_marked_classes` uses a retry loop — files that fail due to unresolved
      cross-file imports are retried each pass until no further progress is made,
      handling dependencies regardless of alphabetical ordering
- [x] `load_marked_classes` does not raise if a `.py` file fails to import — it logs a
      `WARNING` with the full message and file path after all retries are exhausted
- [x] `just check` passes

---

### TICKET-07 — Adapter: Marshmallow3Parser

**Depends on:** TICKET-03, TICKET-05
**Type:** Adapter
**Status: ✅ Done**

**Goal:**
Implement `Marshmallow3Parser`, the concrete `SchemaParser` adapter that converts a Marshmallow 3
schema class into a `ContractSchema`. Co-located with `SchemaParser(ABC)` in `schema_parser.py`.

**Files created / modified:**
- `contract_sentinel/adapters/schema_parser.py` — `SchemaParser(ABC)` + `Marshmallow3Parser` (co-located)
- `tests/integration/adapters/test_schema_parser.py` — integration tests
- `pyproject.toml` — `marshmallow>=3.13,<4.0` as optional `marshmallow` extra; `all` extra bundles both `s3` and `marshmallow`

**Done when:**
- [x] `marshmallow` is listed under `[project.optional-dependencies]` in `pyproject.toml`,
      not under `[project.dependencies]`
- [x] `Marshmallow3Parser` does **not** import marshmallow at the top level — the import
      lives inside `__init__` so that the module loads safely without the extra installed
- [x] `Marshmallow3Parser` extends `SchemaParser` ABC (type-checker agrees)
- [x] `parse(cls)` maps Marshmallow field types to canonical types and JSON Schema formats:
      `String` → `"string"`, `Integer` → `"integer"`, `Float`/`Decimal`/`TimeDelta` → `"number"`,
      `Boolean` → `"boolean"`, `List`/`Tuple` → `"array"`, `Dict`/`Mapping` → `"object"`,
      nested `Schema`/`Nested`/`Pluck` → `"object"`; datetime subtypes, email, URL, UUID, and IP
      variants carry a `format` string; unknown field types fall back to `("string", classname.lower())`
- [x] `parse(cls)` correctly sets `is_required` and `is_nullable` from `field.required` and `field.allow_none`
- [x] `parse(cls)` correctly captures `default` when a marshmallow field has one (`load_default`)
- [x] `parse(cls)` populates `fields` recursively for nested `Schema` fields
- [x] `parse(cls)` reads the effective unknown-field policy from `schema_instance.unknown`
      (not from `class Meta` directly — Marshmallow resolves this through MRO, so inheritance
      is handled correctly) and maps it to `UnknownFieldBehaviour`: `marshmallow.RAISE → FORBID`,
      `marshmallow.EXCLUDE → IGNORE`, `marshmallow.INCLUDE → ALLOW`; defaults to `FORBID`
- [x] `parse(cls)` sets `ContractField.unknown` for any field whose `type == "object"` by applying
      the same mapping to that nested schema's `unknown`; leaves `None` for all other types
- [x] `parse(cls)` captures `values` for `Enum` fields — the ordered list of member `.value`s
- [x] Integration tests cover: full field-to-dict round trip, all unknown-field policies,
      policy inheritance through schema MRO, nested schemas, `Pluck`, all field type mappings,
      and enum `values` capture
- [x] `just check` passes

---

### TICKET-08 — Adapter: S3ContractStore

**Depends on:** TICKET-01, TICKET-05
**Type:** Adapter
**Status: ✅ Done**

**Goal:**
Implement `S3ContractStore`, the concrete `ContractStore` adapter that reads and writes contract
JSON files to S3, and set up the shared integration test fixture for LocalStack.

**Files created / modified:**
- `contract_sentinel/adapters/contract_store.py` — `ContractStore(ABC)` + `S3ContractStore` (co-located, mirrors `rules.py` pattern)
- `contract_sentinel/adapters/schema_parser.py` — `SchemaParser(ABC)` (implementation added in TICKET-07)
- `tests/integration/conftest.py` — `s3_client`, `s3_bucket`, `s3_store` fixtures; reused by CLI tests
- `tests/integration/adapters/test_contract_store.py` — integration tests against LocalStack
- `pyproject.toml` — `boto3` as optional `s3` extra; `boto3` + `boto3-stubs[s3]` in dev group

**Done when:**
- [x] `boto3` is listed under `[project.optional-dependencies]` in `pyproject.toml`,
      not under `[project.dependencies]`
- [x] `contract_store.py` does **not** import boto3 at the top level — the import lives
      inside `__init__` so that the module loads safely without the extra installed
- [x] `S3ContractStore` extends `ContractStore` ABC (type-checker agrees)
- [x] `S3ContractStore` is constructed with a `path` argument and prepends it to every
      S3 key — callers always work with relative keys; no path is hardcoded inside the adapter
- [x] `put_file(key, content)` writes `content` as a UTF-8 string to the correct S3 key
- [x] `get_file(key)` returns the exact string previously written by `put_file`
- [x] `file_exists(key)` returns `True` after a `put_file` and `False` for a key never written
- [x] `list_files(prefix)` returns all keys sharing the prefix, ordered by `LastModified` descending;
      returns `[]` when no keys match
- [x] `conftest.py` creates a unique test bucket before each test and deletes all objects after;
      `s3_store` fixture wires a ready-to-use store to the test bucket
- [x] `just check` passes

---

### TICKET-09 — Factory

**Depends on:** TICKET-01, TICKET-03, TICKET-07, TICKET-08
**Type:** Service
**Status: ✅ Done**

**Goal:**
Implement the adapter factory that maps `Config` values to concrete adapter instances —
the single place in the codebase that knows which config value means which class, and the single
place that handles missing optional extras with actionable error messages.

**Files to create / modify:**
- `contract_sentinel/factory.py` — create
- `tests/unit/test_factory.py` — create

**Done when:**
- [x] `get_parser(framework, repository)` accepts a `Framework` enum value and a `repository`
      string (not a config object) — repository is threaded separately so parser factory stays
      independent from storage config
- [x] `get_parser(framework, repository)` uses a **lazy import** inside each branch — the
      framework adapter is only imported when selected, so the factory module is safe to import
      without any optional extra installed
- [x] `get_parser(framework, repository)` returns a `Marshmallow3Parser` instance when
      `framework == Framework.MARSHMALLOW`
- [x] `get_parser(framework, repository)` raises `MissingDependencyError` when the required
      extra for the detected framework is not installed (e.g. marshmallow package missing)
- [x] `get_parser(framework, repository)` raises `UnsupportedFrameworkError` for any `Framework`
      value that has no registered adapter
- [x] `get_store(config)` uses a **lazy import** inside the `match` branch — boto3 is only
      imported when the `s3` extra is the active storage backend
- [x] `get_store(config)` returns an `S3ContractStore` instance constructed with
      `bucket=config.s3_bucket`, `path=config.s3_path`, and AWS credentials from `config`
- [x] `get_store(config)` raises `MissingDependencyError` with the message
      `"storage backend 's3' requires the s3 extra.\nInstall it with: pip install contract-sentinel[s3]"`
      when boto3 is not installed
- [x] `get_store(config)` raises `UnsupportedStorageError` for an unrecognised storage backend,
      with a message listing `"s3"` as the valid option
- [x] `Config` gained a `storage_backend` field (reads `SENTINEL_STORAGE_BACKEND`, defaults to
      `"s3"`) so the factory can route and the `UnsupportedStorageError` branch is testable
- [x] `MissingDependencyError` updated to accept a plain `message: str` for full flexibility
- [x] `just check` passes

---

### TICKET-10 — Service: validate_local_contracts / validate_published_contracts

**Depends on:** TICKET-04, TICKET-05, TICKET-06, TICKET-09
**Type:** Service
**Status: ✅ Done**

**Goal:**
Implement two validation use-cases: `validate_local_contracts` (PR gate — local scan vs store)
and `validate_published_contracts` (S3 audit — store-only), both returning a structured report.

**Files to create / modify:**
- `contract_sentinel/services/__init__.py` — create (empty)
- `contract_sentinel/services/validate.py` — create
- `tests/unit/test_services/test_validate.py` — create

**Done when:**
- [x] `ValidationStatus` is a `StrEnum` with members `PASSED` and `FAILED`
- [x] `ContractReport` dataclass holds `topic`, `status`, and `violations` for a single topic
- [x] `ContractsValidationReport` dataclass holds a global `status` and a `reports: list[ContractReport]`;
      status is `FAILED` if any `ContractReport` is `FAILED`
- [x] `validate_local_contracts(store, parser, loader, config, topics=None)` returns a
      `ContractsValidationReport` with `status=ValidationStatus.PASSED` when all pairs are compatible.
      `parser` is a `Callable[[Framework, str], SchemaParser]` (the `get_parser` factory),
      `loader` is a zero-arg `Callable[[], list[type]]` with the scan path baked in.
      When `topics` is set, only schemas whose topic is in the list are validated
- [x] For each discovered class, `detect_framework(cls)` is called to resolve the framework,
      then `parser(framework, config.name)` is invoked to obtain the correct `SchemaParser`
- [x] Returns `status=ValidationStatus.FAILED` with the correct `Violation` objects when a
      breaking rule fires; a violation in any pair sets the status to `FAILED`
- [x] Each local schema is validated only against counterparts of the opposite role fetched from
      the store — counterparts are filtered by `/{role}/` in the key
- [x] `validate_published_contracts(store, topics=None)` fetches all contracts in a single
      `store.list_files("")` call, groups by `topic` in memory, and validates every
      `(producer, consumer)` pair. When `topics` is set, keys whose topic prefix is not in the
      list are skipped before fetching the file
- [x] Both functions emit a `logger.warning` for each requested topic that yields no schemas
- [x] Unit tests inject `create_autospec(ContractStore)` and `create_autospec(SchemaParser)` —
      no LocalStack required
- [x] `just check` passes

---

### TICKET-11 — Service: publish_contracts

**Depends on:** TICKET-05, TICKET-06, TICKET-09
**Type:** Service
**Status: ✅ Done**

**Goal:**
Implement the `publish_contracts` use-case that writes new or changed contracts to S3 and skips
unchanged ones using SHA-256 content hashing.

**Files created / modified:**
- `contract_sentinel/services/publish.py` — create
- `tests/unit/test_services/test_publish.py` — create

**Done when:**
- [x] `publish_contracts(store, parser, loader, config)` calls `store.put_file(key, content)` for
      each `ContractSchema` whose SHA-256 hash (of `sort_keys=True` JSON) differs from the current
      S3 object. `parser` and `loader` follow the same conventions as in `validate_local_contracts`
- [x] The S3 key for every write is `schema.to_store_key()` —
      `"{topic}/{role}/{repository}_{class_name}.json"`. `ContractSchema.to_store_key()`
      is added to `domain/schema.py` and is the single source of truth for the path convention
- [x] For each discovered class, `detect_framework(cls)` is called to resolve the framework,
      then `parser(framework, config.name)` is invoked to obtain the correct `SchemaParser`
- [x] `store.put_file()` is **not** called for a schema whose hash matches the current S3 object
- [x] `publish_contracts` returns a `PublishReport` with counts of `written` and `skipped` schemas
- [x] When a schema does not yet exist in S3 (`store.file_exists(key)` returns `False`), it is
      always written without a hash comparison
- [x] Unit tests inject `create_autospec(ContractStore)` — no LocalStack required
- [x] `just check` passes

---

### TICKET-12 — CLI: sentinel validate-local

**Depends on:** TICKET-01, TICKET-10
**Type:** CLI
**Status: ✅ Done**

**Goal:**
Expose `validate_local_contracts` as `sentinel validate-local` and `validate_published_contracts` as
`sentinel validate-published`, wire config loading and factory adapter construction, and
write integration tests against LocalStack.

**Files to create / modify:**
- `contract_sentinel/cli/__init__.py` — create (empty)
- `contract_sentinel/cli/main.py` — create (Typer app object, registered as `sentinel` script)
- `contract_sentinel/cli/validate.py` — create (`sentinel validate-local` command)
- `contract_sentinel/cli/validate_published.py` — create (`sentinel validate-published` command)
- `tests/integration/test_cli_validate.py` — create
- `pyproject.toml` — modify (`uv add typer`; add `[project.scripts] sentinel = "contract_sentinel.cli.main:app"`)

**Done when:**
- [x] `Config()` is constructed **inside** each command handler, not at module level —
      importing either CLI module must not trigger any env var reads
- [x] Each command that invokes `load_marked_classes` inserts `str(Path.cwd())` at the front of
      `sys.path` before scanning, so that app-relative imports (e.g. `from myapp.db import Base`
      inside a schema file's transitive dependencies) resolve correctly when sentinel is run from
      the project root
- [x] `sentinel validate-local` accepts an optional `--dry-run` flag (default: `False`). When set, the
      command prints the full violation report to stdout and exits `0` regardless of whether
      violations were found — no side-effects, no failure signal
- [x] `sentinel validate-local` calls `validate_local_contracts`, prints the violation report to stdout,
      exits `1` on violations (unless `--dry-run`), exits `0` on pass
- [x] `sentinel validate-published` accepts the same `--dry-run` flag with identical semantics
- [x] `sentinel validate-published` calls `validate_published_contracts`, prints the violation
      report to stdout, exits `1` on violations (unless `--dry-run`), exits `0` on pass
- [x] Integration test for `sentinel validate-local` uses `typer.testing.CliRunner` with a real
      LocalStack bucket pre-seeded with a producer and consumer contract stored at the canonical
      path (`{topic}/{role}/{repository}_{class_name}.json`); asserts exit code and
      stdout content
- [x] Integration test for `sentinel validate-local` with `--dry-run`: seeds LocalStack with an
      incompatible pair, asserts exit code is `0`, and asserts the violation report is still
      printed to stdout
- [x] Integration test for `sentinel validate-published` seeds LocalStack with compatible and
      incompatible contract pairs; asserts the correct exit code and stdout for each case
- [x] Integration test for `sentinel validate-published` with `--dry-run`: seeds LocalStack with
      an incompatible pair, asserts exit code is `0`, and asserts the violation report is still
      printed to stdout
- [x] `just check` passes

---

### TICKET-13 — CLI: sentinel publish

**Depends on:** TICKET-01, TICKET-11, TICKET-12
**Type:** CLI
**Status: ✅ Done**

**Goal:**
Expose `publish_contracts` as the `sentinel publish` CLI command and write the integration test
against LocalStack.

**Files to create / modify:**
- `contract_sentinel/cli/publish.py` — create ✅
- `tests/unit/test_cli/test_publish.py` — create ✅
- `tests/integration/test_cli/test_publish.py` — create ✅

**Done when:**
- [x] `sentinel publish` inserts `str(Path.cwd())` at the front of `sys.path` before scanning
      (same requirement as TICKET-12 — each command that calls `load_marked_classes` must do this)
- [x] `sentinel publish` scans, parses, and writes new or changed contracts to S3 using a
      two-phase approach: all classes are parsed first; if any parse fails the write phase is
      skipped entirely, preventing partial publishes
- [x] `sentinel publish` returns a `PublishReport` with four buckets — `published` (new keys),
      `updated` (hash-changed keys), `unchanged` (skipped), `failed` (parse or write errors) —
      and prints a structured summary to stdout; `--verbose` reveals unchanged schemas
- [x] `sentinel publish` exits `0` whether or not any schemas were written
- [x] Integration test: run `sentinel publish` twice against LocalStack with the same schemas;
      assert that objects are written to the canonical path (`{topic}/{role}/{repository}_{class_name}.json`),
      exactly one S3 write on the first run and zero on the second (idempotency). Additional
      cases cover content-change detection (updated bucket) and `--verbose` output
- [x] `just check` passes

---

### TICKET-13a — CLI: violation participant context in report output

**Depends on:** TICKET-12
**Type:** Enhancement
**Status: ✅ Done**

**Goal:**
Each violation line in `sentinel validate-local` and `sentinel validate-published` output currently
shows only the field path. When multiple producer/consumer pairs exist for the same topic, it is
impossible to tell which pair produced a given violation without cross-referencing the schema files
manually. This ticket threads the participant identity (`repository` + `class_name`) from
`ContractSchema` through to `Violation` so the rendered report can show it alongside each
violation.

**Design:**

Add two optional fields to `Violation`:

```python
@dataclasses.dataclass
class Violation:
    ...
    producer_id: str | None = None  # "{repository}/{class_name}" of the producer schema
    consumer_id: str | None = None  # "{repository}/{class_name}" of the consumer schema
```

`validate_pair` (in `engine.py`) receives the root `producer: ContractSchema` and
`consumer: ContractSchema` objects. It sets `producer_id` and `consumer_id` on every `Violation`
it creates before returning. Nested violations carry the same IDs (they come from the same pair).

`print_report` in `report.py` renders the IDs when present:

```
  ✗  orders
       [CRITICAL] TYPE_MISMATCH @ id  (orders-service/OrderSchema → my-service/OrderSchema)
       Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.
```

When both IDs are `None` (e.g. unit tests that construct `Violation` directly), the parenthetical
is omitted and the line renders exactly as before — no breaking change to existing tests.

**Files to create / modify:**
- `contract_sentinel/domain/rules/violation.py` — add `producer_id` and `consumer_id` fields
- `contract_sentinel/domain/rules/engine.py` — thread IDs through `validate_pair`
- `contract_sentinel/cli/report.py` — render IDs in violation line when present
- `tests/unit/test_domain/test_rules/test_engine.py` — assert IDs are set on returned violations
- `tests/unit/test_cli/test_report.py` — add cases asserting the parenthetical renders correctly

**Done when:**
- [x] `Violation` gains `producer_id: str | None = None` and `consumer_id: str | None = None`;
      both fields are included in `to_dict()` when not `None`
- [x] `validate_pair` is updated to accept `producer_id` and `consumer_id` as parameters and
      stamp every `Violation` it creates or recurses into with those values
- [x] `validate_group` passes `f"{schema.repository}/{schema.class_name}"` for both IDs when
      calling `validate_pair` for each producer/consumer combination
- [x] `CounterpartMismatchRule` violations carry the ID of the lonely schema in `producer_id`
      or `consumer_id` as appropriate; the absent side is `None`
- [x] `print_report` appends `  ({producer_id} → {consumer_id})` to the violation rule line
      when both IDs are present; renders nothing extra when either is `None`
- [x] All existing tests continue to pass without modification (IDs default to `None`)
- [x] `just check` passes

---

### TICKET-14 — Loader: scan exclusions

**Depends on:** TICKET-06, TICKET-12
**Type:** Enhancement

**Goal:**
Extend `load_marked_classes` and `Config` to support exclusion patterns so that common noise
directories (virtual environments, package trees, caches, JS dependencies) are always skipped, and
users can add their own patterns on top without displacing the built-ins.

**Files to create / modify:**
- `contract_sentinel/domain/loader.py` — add `BUILT_IN_EXCLUDE_PATTERNS` constant and `exclude`
  parameter to `load_marked_classes`
- `contract_sentinel/config.py` — add `exclude` field (user-supplied patterns, default empty)
- `contract_sentinel/cli/validate.py` — pass `config.exclude` to loader
- `contract_sentinel/cli/publish.py` — pass `config.exclude` to loader
- `tests/unit/test_domain/test_loader.py` — extend with exclusion tests

**Design:**

Exclusion uses two layers that are **always merged** — the built-ins can never be removed:

```
effective patterns = BUILT_IN_EXCLUDE_PATTERNS | set(config.exclude)
```

Patterns are **regular expressions** matched with `re.search()` against the file's path relative
to the scan root, with path separators normalised to `/` before matching. `re.search()` means a
pattern matches as long as it appears anywhere in the path — no anchoring boilerplate needed.

`BUILT_IN_EXCLUDE_PATTERNS` is a module-level `frozenset[str]` constant in `loader.py`:

```python
BUILT_IN_EXCLUDE_PATTERNS: frozenset[str] = frozenset({
    r"(^|/)\.venv/",         # virtual environment (dotdir form)
    r"(^|/)venv/",           # virtual environment (plain form)
    r"(^|/)__pycache__/",    # bytecode cache
    r"(^|/)site-packages/",  # installed packages inside any interpreter tree
    r"(^|/)node_modules/",   # JS/TS dependencies
    r"(^|/)\.git/",          # git internals
    r"(^|/)\.tox/",          # tox environments
    r"\.egg-info/",           # editable-install metadata
})
```

User patterns are supplied via `config.exclude` (a `list[str]` of additional regexes, default
`[]`) and are compiled and merged with the built-ins at the start of each scan. An invalid regex
in `config.exclude` raises `re.error` at scan time with a clear message identifying the offending
pattern.

`pyproject.toml` opt-in (additive — built-ins still apply):

```toml
[tool.sentinel]
path = "."
exclude = ["(^|/)tests/", "(^|/)scripts/"]
```

Matching is checked before `_try_import` is called — excluded files are never imported, not just
filtered from results.

**Done when:**
- [ ] `BUILT_IN_EXCLUDE_PATTERNS` is a `frozenset[str]` constant defined at the top of
      `loader.py`; it covers `.venv/`, `venv/`, `__pycache__/`, `site-packages/`,
      `node_modules/`, `.git/`, `.tox/`, and `.egg-info/`
- [ ] `load_marked_classes(path, exclude)` accepts `path: str | Path` (default `"."`) and
      `exclude: list[str] | None` (default `None`); resolves exclude internally with
      `exclude = exclude or []`; the effective pattern set is always
      `BUILT_IN_EXCLUDE_PATTERNS | set(exclude)` — there is no way for callers to remove
      built-in patterns
- [ ] Matching uses `re.search()` against the relative path with separators normalised to `/`;
      excluded files are never passed to `_try_import`
- [ ] An invalid regex in `exclude` raises `re.error` before any file is scanned, with the
      offending pattern included in the error message
- [ ] `config.exclude` defaults to `None`; `load_marked_classes` resolves it with
      `exclude = exclude or []` — avoids a mutable default argument and signals clearly that
      the built-ins alone are sufficient for the common case
- [ ] Both CLI commands pass `config.exclude` through to `load_marked_classes`
- [ ] Unit tests assert that a file under each built-in pattern directory is never imported
- [ ] Unit tests assert that a user-supplied pattern in `exclude` is applied on top of the
      built-ins without removing any of them
- [ ] Unit tests assert that a file outside all patterns is still discovered normally
- [ ] Unit test asserts that passing an invalid regex string raises `re.error`
- [ ] `just check` passes
