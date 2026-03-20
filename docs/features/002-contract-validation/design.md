# Design — Contract Validation

## Architecture Overview

```
Config Layer:    Config (plain class, env vars)
Domain Layer:    ContractSchema (value object), Violation, BinaryRule (single ABC, optional args), Framework / detect_framework
Adapter Layer:   ContractStore(ABC) + S3ContractStore, SchemaParser(ABC) + Marshmallow3Parser
Factory Layer:   get_parser(framework) -> SchemaParser, get_store(config) -> ContractStore
Service Layer:   validate_local_contracts(), validate_published_contracts(), publish_contracts() use-cases
CLI Layer:       `sentinel validate`, `sentinel validate-published`, `sentinel publish` commands
```

The Marker (decorator) and Loader (scanner) are pure domain utilities — no I/O, no ports.

### File Placement

| Module | File |
|---|---|
| Marker decorator + `Role` enum | `contract_sentinel/domain/participant.py` |
| `Framework` enum + `detect_framework` | `contract_sentinel/domain/framework.py` |
| Loader scanner | `contract_sentinel/domain/loader.py` |
| `ContractSchema` value object | `contract_sentinel/domain/schema.py` |
| `Violation` | `contract_sentinel/domain/rules/violation.py` |
| `Rule(ABC)` | `contract_sentinel/domain/rules/rule.py` |
| `TypeMismatchRule` | `contract_sentinel/domain/rules/type_mismatch.py` |
| `NullabilityMismatchRule` | `contract_sentinel/domain/rules/nullability_mismatch.py` |
| `RequirementMismatchRule` | `contract_sentinel/domain/rules/requirement_mismatch.py` |
| `DirectionMismatchRule` | `contract_sentinel/domain/rules/direction_mismatch.py` |
| `MetadataMismatchRule` | `contract_sentinel/domain/rules/metadata_mismatch.py` |
| `MissingFieldRule` | `contract_sentinel/domain/rules/missing_field.py` |
| `UndeclaredFieldRule` | `contract_sentinel/domain/rules/undeclared_field.py` |
| `NestedFieldRule` | `contract_sentinel/domain/rules/nested_field.py` |
| Domain errors | `contract_sentinel/domain/errors.py` |
| `ContractStore` ABC + `S3ContractStore` | `contract_sentinel/adapters/contract_store.py` |
| `SchemaParser` ABC + `Marshmallow3Parser` | `contract_sentinel/adapters/schema_parser.py` |
| Adapter factory | `contract_sentinel/factory.py` |
| `Config` (plain class, env vars) | `contract_sentinel/config.py` |
| `SentinelConfig` (tomllib) | `contract_sentinel/config.py` |
| `validate` CLI command | `contract_sentinel/cli/validate.py` |
| `publish` CLI command | `contract_sentinel/cli/publish.py` |

### Test Strategy

| Layer | Test location | Tooling |
|---|---|---|
| `domain/` | `tests/unit/domain/` | Pure pytest, no mocks |
| `factory.py` | `tests/unit/` | Assert correct type is returned per config value |
| `adapters/` | `tests/integration/adapters/` | Real external dependency (`S3ContractStore` → LocalStack; `Marshmallow3Parser` → marshmallow library) |
| Service use-cases | `tests/unit/` | `unittest.mock.create_autospec` on adapter ABCs |
| CLI commands | `tests/integration/` | `typer.testing.CliRunner` + LocalStack |


---


## 1. Marker

Class-level decorator. Adds `__contract__` to the decorated schema class.

Arguments:
* `topic: str` — e.g. `"orders.created"`
* `role: Role` — `Role.PRODUCER` or `Role.CONSUMER`
* `version: str` — e.g. `"1.0.0"`

**Constraint:** Arguments must be string/enum literals, not variables.


---


## 2. Loader

Import-based scanner. Walks `.py` files under a configured path, imports each module via
`importlib`, and collects classes that carry `__contract__`.

Accepts an optional `path` argument to narrow the scan scope.


---


## 2a. Framework Detector

Pure introspection — no framework imports required. Inspects class attributes set by the
framework's own metaclass or base class to determine which adapter to use. MVP supports
Marshmallow only.
The service layer calls `detect_framework(cls)` for each discovered class and passes the result
to `get_parser(framework)`. `config.framework` does not exist — detection is always automatic.


---


## 3. Parser

**Abstract:** `SchemaParser` — `parse(cls: type) -> ContractSchema`

MVP adapter: `Marshmallow3Parser`. Interface is framework-agnostic.

### Canonical Field Format

| Property | Description |
|---|---|
| `name` | Field name as declared |
| `type` | `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"` |
| `format` | JSON Schema format string refining `type` (e.g. `"date-time"`, `"email"`, `"uuid"`, `"enum"`); omitted when absent |
| `is_required` | `true` if the field has no default |
| `is_nullable` | Whether `null` is a valid value |
| `default` | Default value, or absent if none |
| `fields` | Nested field list — present when `type` is `"object"` |
| `unknown` | Framework-agnostic unknown-field policy — `"forbid"`, `"ignore"`, or `"allow"`; present only when `type` is `"object"`, representing the nested schema's own policy |
| `values` | Ordered list of allowed enum member values — present only when `format` is `"enum"`; omitted otherwise |
| `metadata` | Optional dict of type-specific extras (e.g. `{"format": "iso8601"}`); omitted when absent |

### Contract Envelope

```json
{
  "topic": "orders.created",
  "role": "producer",
  "version": "1.1.0",
  "repository": "order-service",
  "class_name": "OrderSchema",
  "unknown": "forbid",
  "fields": [ ... ]
}
```

> **Canonical `UnknownFieldBehaviour` enum** (defined in `domain/schema.py`):
>
> | Enum member | JSON value | Meaning |
> |---|---|---|
> | `FORBID` | `"forbid"` | Unknown fields cause a validation error |
> | `IGNORE` | `"ignore"` | Unknown fields are silently dropped |
> | `ALLOW` | `"allow"` | Unknown fields are passed through as-is |
>
> The domain model and validation rules only reference `UnknownFieldBehaviour`. Framework-specific
> constants stay inside the relevant adapter:
>
> | Marshmallow constant | Maps to |
> |---|---|
> | `marshmallow.RAISE` | `UnknownFieldBehaviour.FORBID` |
> | `marshmallow.EXCLUDE` | `UnknownFieldBehaviour.IGNORE` |
> | `marshmallow.INCLUDE` | `UnknownFieldBehaviour.ALLOW` |
>
> `Marshmallow3Parser` is the only module that imports or references `marshmallow.RAISE` /
> `marshmallow.EXCLUDE` / `marshmallow.INCLUDE`. The mapping lives entirely inside
> `adapters/schema_parser.py`.
>
> **`unknown` resolution:** The parser reads the effective value from the instantiated schema's
> `unknown` attribute — not directly from `class Meta`. Marshmallow resolves this through MRO,
> so reading `schema_instance.unknown` correctly handles inheritance. The default when unset is `FORBID`.

`field_path` uses dot notation for nested fields (e.g. `"metadata.discount_code"`, `"items[].sku"`).


---


## 4. Data Storage

**Abstract:** `ContractStore` — `get_file`, `put_file`, `list_files`, `file_exists`

MVP adapter: `S3ContractStore`.

### S3 Path Convention

```
<bucket>/<path>/<topic_name>/<version>/<role>/<repository_name>_<class_name>.json
```

`<path>` is the `SENTINEL_S3_PATH` env var, defaulting to `"contract_tests"`.
`<role>` is a directory segment (`producer` or `consumer`), not a filename prefix.

Example:
```
my-bucket/contract_tests/orders.created/1.1.0/producer/order-service_OrderSchema.json
my-bucket/contract_tests/orders.created/1.0.0/consumer/billing-service_InvoiceSchema.json
```

`ContractSchema.to_store_key()` is the single source of truth for constructing the
relative key. The publish service calls it when writing; the validate service uses the
role directory segment to filter listed keys to the correct side of the contract.

### Version Resolution

Latest contract resolved by **S3 `LastModified` timestamp**. Version string in path is a
human-readable label only.

### Repository Name Precedence

1. `SENTINEL_REPO_NAME` environment variable
2. `name` in `[tool.sentinel]` in `pyproject.toml`

Fails fast with a clear error if neither is set.

### Multi-Producer

Each consumer is validated against every producer on the same topic. Any failing pair fails the run.


---


## 5. Contract Validator

Directional validation: "can the consumer safely consume what this producer sends?"

A single `Rule(ABC)` covers all rule types. Its signature is:

```python
def check(self, producer: ContractField | None, consumer: ContractField | None) -> list[Violation]
```

Each rule self-determines its behaviour based on which side is `None`:

- Both present → matched-field checks (type, nullability, requirement, metadata, etc.)
- `producer is None` → consumer-only checks (e.g. `MissingFieldRule`)
- `consumer is None` → not used in practice; all rules return `[]`

`UndeclaredFieldRule` is the one special case: `consumer` is the *parent* container object
(to read `.unknown`), not a matched field. It runs in a dedicated pass inside `NestedFieldRule`.

### MVP Rules

| Rule | Trigger | Severity |
|---|---|---|
| `TYPE_MISMATCH` | Type differs between producer and consumer | CRITICAL |
| `REQUIREMENT_MISMATCH` | Producer optional, consumer required (no default) | CRITICAL |
| `NULLABILITY_MISMATCH` | Producer allows `null`, consumer does not | CRITICAL |
| `MISSING_FIELD` | Field absent from producer (`producer is None`), required by consumer (no default) | CRITICAL |
| `UNDECLARED_FIELD` | Producer has a field not declared in consumer schema and consumer `unknown == "forbid"` | CRITICAL |
| `METADATA_KEY_MISMATCH` | A generic metadata key declared by consumer differs from (or is absent in) producer | CRITICAL |
| `METADATA_ALLOWED_VALUES_MISMATCH` | Producer can emit a value the consumer does not accept; also fires when producer is unconstrained but consumer is constrained | CRITICAL |
| `METADATA_RANGE_MISMATCH` | Producer's numeric range is wider than the consumer's (min/max, inclusive boundaries) | CRITICAL |
| `METADATA_LENGTH_MISMATCH` | Producer's string/array length range is wider than the consumer's | CRITICAL |
| `DIRECTION_MISMATCH` | Field is `load_only` in producer (never serialised) but consumer expects to receive it | CRITICAL |

> **`UNDECLARED_FIELD` directionality:** The unknown-field policy only applies during `load()`
> (deserialization), which is what the **consumer** does. The producer serializes (`dump()`) its
> declared fields outward and is unaffected by this setting. Therefore only the consumer's
> `UnknownFieldBehaviour` is checked. When the consumer's policy is `IGNORE` or `ALLOW`, the rule
> returns no violation.
>
> **`UndeclaredFieldRule`:** Takes `(producer, consumer_parent)` where `consumer` is the parent
> container object, not a matched field. Reads `consumer.unknown` directly to determine whether
> to fire. No constructor parameter needed — the FORBID check is internal to the rule.

### Violation Report Format

```json
{
  "status": "FAILED",
  "topic": "orders.created",
  "summary": {
    "producer": "order-service (OrderSchema v1.1.0)",
    "consumer": "billing-service (InvoiceSchema v1.0.0)",
    "total_violations": 3
  },
  "violations": [
    {
      "rule": "TYPE_MISMATCH",
      "severity": "CRITICAL",
      "field_path": "order_id",
      "producer": { "type": "string" },
      "consumer": { "type": "integer" },
      "message": "Field 'order_id' is a 'string' in Producer but Consumer expects an 'integer'."
    },
    {
      "rule": "REQUIREMENT_MISMATCH",
      "severity": "CRITICAL",
      "field_path": "metadata.discount_code",
      "producer": { "is_required": false },
      "consumer": { "is_required": true },
      "message": "Field 'metadata.discount_code' is optional in Producer but required in Consumer."
    },
    {
      "rule": "MISSING_FIELD",
      "severity": "CRITICAL",
      "field_path": "items.sku",
      "producer": { "exists": false },
      "consumer": { "is_required": true },
      "message": "Field 'items.sku' is missing in Producer but required in Consumer."
    },
    {
      "rule": "NULLABILITY_MISMATCH",
      "severity": "CRITICAL",
      "field_path": "total_price",
      "producer": { "is_nullable": true },
      "consumer": { "is_nullable": false },
      "message": "Field 'total_price' allows null in Producer but Consumer expects a value."
    },
    {
      "rule": "UNDECLARED_FIELD",
      "severity": "CRITICAL",
      "field_path": "promo_code",
      "producer": { "exists": true },
      "consumer": { "exists": false, "unknown": "forbid" },
      "message": "Field 'promo_code' is sent by Producer but is not declared in Consumer (unknown=forbid)."
    }
  ]
}
```


---


## 6. CLI Commands

### `sentinel validate` — PR gate

Calls `validate_local_contracts(store, parser, loader, config)`.

1. Load config.
2. Scan and parse local schemas.
3. For each local schema, fetch all counterpart schemas (opposite role, same topic) from S3.
4. Validate the local schema against every remote counterpart; collect all violations.
5. Print violation report.
6. Exit `1` on any violations, exit `0` on pass.

```
❌ Contract Broken for topic 'orders.created'
--------------------------------------------------
[MISSING_FIELD]        items.sku: Missing in Producer, Required in Consumer.
[TYPE_MISMATCH]        order_id: Producer is 'string', Consumer is 'integer'.
--------------------------------------------------
Total Violations: 2
```

### `sentinel validate-published` — S3 audit

Calls `validate_published_contracts(store, topics=None)`.

1. Load config.
2. Fetch all published contracts from S3.
3. Group by topic; validate every (producer, consumer) pair.
4. Print violation report.
5. Exit `1` on any violations, exit `0` on pass.

No local schema scan is performed. Intended as a scheduled cross-service consistency
check or for environments where the local codebase is not available.

### `sentinel publish` — post-merge

1. Load config.
2. Scan and parse local schemas.
3. SHA-256 hash each canonical JSON (keys sorted).
4. Compare against current S3 object hash.
5. Write to S3 only if hash differs; log "no change, skipping" otherwise.
6. Exit `0` always.


---


## 7. Configuration

### `Config` — env vars (plain class)

| Env Var | Required | Default |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Yes | — |
| `AWS_SECRET_ACCESS_KEY` | Yes | — |
| `AWS_DEFAULT_REGION` | No | `"us-east-1"` |
| `AWS_ENDPOINT_URL` | No | `None` (set for LocalStack) |
| `S3_BUCKET` | Yes | — |
| `SENTINEL_S3_PATH` | No | `"contract_tests"` |
| `SENTINEL_NAME` | Yes | — |


### `SentinelConfig` — `pyproject.toml` (tomllib + Pydantic `BaseModel`)

```toml
[tool.sentinel]
framework = "marshmallow"
path = "app/schemas"
name = "order-service"

[tool.sentinel.storage]
type = "s3"
bucket = "my-contracts-bucket"
path = "contract_tests"   # optional — defaults to "contract_tests"
```


---


## 8. Adapter Factory

Single module `contract_sentinel/factory.py`. Only place that maps config values to concrete
adapter types.

### Parser — driven by detected framework

| Value | Adapter |
|---|---|
| `"marshmallow"` | `Marshmallow3Parser` |
| other | `UnsupportedFrameworkError` |

### Store — driven by `storage.type`

| Value | Adapter |
|---|---|
| `"s3"` | `S3ContractStore` |
| other | `UnsupportedStorageError` |
