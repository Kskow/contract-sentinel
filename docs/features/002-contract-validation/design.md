# Design — Contract Validation

## Architecture Overview

```
Config Layer:    Settings (pydantic-settings, env vars) + SentinelConfig (pyproject.toml)
Domain Layer:    ContractSchema (value object), Violation, ValidationRule
Port Layer:      ContractStore (Protocol), SchemaParser (Protocol)
Adapter Layer:   S3ContractStore, MarshmallowParser
Factory Layer:   get_parser(config) -> SchemaParser, get_store(config, settings) -> ContractStore
Service Layer:   validate_contracts(), publish_contracts() use-cases
CLI Layer:       `sentinel validate`, `sentinel publish` commands
```

The Marker (decorator) and Loader (scanner) are pure domain utilities — no I/O, no ports.

### File Placement

| Module | File |
|---|---|
| Marker decorator + `Role` enum | `contract_sentinel/domain/marker.py` |
| Loader scanner | `contract_sentinel/domain/loader.py` |
| `ContractSchema` value object | `contract_sentinel/domain/contract.py` |
| `Violation` + `ValidationRule` Protocol | `contract_sentinel/domain/validation.py` |
| Domain errors | `contract_sentinel/domain/errors.py` |
| `ContractStore` port | `contract_sentinel/ports/contract_store.py` |
| `SchemaParser` port | `contract_sentinel/ports/schema_parser.py` |
| `S3ContractStore` adapter | `contract_sentinel/adapters/s3_contract_store.py` |
| `MarshmallowParser` adapter | `contract_sentinel/adapters/marshmallow_parser.py` |
| Adapter factory | `contract_sentinel/factory.py` |
| `Settings` (pydantic-settings) | `contract_sentinel/settings.py` |
| `SentinelConfig` (tomllib) | `contract_sentinel/config.py` |
| `validate` CLI command | `contract_sentinel/cli/validate.py` |
| `publish` CLI command | `contract_sentinel/cli/publish.py` |

### Test Strategy

| Layer | Test location | Tooling |
|---|---|---|
| `domain/` | `tests/unit/` | Pure pytest, no mocks |
| `factory.py` | `tests/unit/` | Assert correct type is returned per config value |
| `adapters/` | `tests/integration/` | LocalStack via Docker Compose |
| Service use-cases | `tests/unit/` | `unittest.mock.create_autospec` on ports |
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


## 3. Parser

**Port:** `SchemaParser` — `parse(cls: type) -> ContractSchema`

MVP adapter: `MarshmallowParser`. Interface is framework-agnostic.

### Canonical Field Format

| Property | Description |
|---|---|
| `name` | Field name as declared |
| `type` | `"string"`, `"integer"`, `"boolean"`, `"list"`, `"dict"`, `"object"` |
| `required` | `true` if no default and `allow_none=False` |
| `allow_none` | Whether `null` is a valid value |
| `default` | Default value, or absent if none |
| `fields` | Nested field list — present when `type` is `"object"` or `"list[object]"` |
| `members` | Enum member values — present when type is an enum |
| `unknown` | Framework-agnostic unknown-field policy — `"forbid"`, `"ignore"`, or `"allow"`; present only when `type` is `"object"`, representing the nested schema's own policy |

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

> **Canonical `UnknownFieldBehaviour` enum** (defined in `domain/contract.py`):
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
> `MarshmallowParser` is the only module that imports or references `marshmallow.RAISE` /
> `marshmallow.EXCLUDE` / `marshmallow.INCLUDE`. The mapping lives entirely inside
> `adapters/marshmallow_parser.py`.
>
> **`unknown` resolution:** The parser must read the effective value from the instantiated schema's
> `_meta.unknown` attribute — not directly from `class Meta`. Marshmallow resolves this through MRO,
> so reading `_meta.unknown` correctly handles inheritance. The default when unset is `FORBID`.

`field_path` uses dot notation for nested fields (e.g. `"metadata.discount_code"`, `"items[].sku"`).


---


## 4. Data Storage

**Port:** `ContractStore` — `get`, `put`, `list`, `exists`

MVP adapter: `S3ContractStore`.

### S3 Path Convention

```
<bucket>/<path>/<topic_name>/<version>/<role>_<repository_name>_<class_name>.json
```

`<path>` is the `storage.path` value from `pyproject.toml`, defaulting to `"contract_tests"`.

Example:
```
my-bucket/contract_tests/orders.created/1.1.0/producer_order-service_OrderSchema.json
my-bucket/contract_tests/orders.created/1.0.0/consumer_billing-service_InvoiceSchema.json
```

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

Each rule is a separate class implementing `ValidationRule`:
`check(producer_field, consumer_field) -> list[Violation]`

### MVP Rules

| Rule | Trigger | Severity |
|---|---|---|
| `TYPE_MISMATCH` | Type differs between producer and consumer | CRITICAL |
| `REQUIREMENT_MISMATCH` | Producer optional, consumer required (no default) | CRITICAL |
| `NULLABILITY_MISMATCH` | Producer allows `null`, consumer does not | CRITICAL |
| `MISSING_FIELD` | Field absent from producer, required by consumer (no default) | CRITICAL |
| `UNDECLARED_FIELD` | Producer has a field not declared in consumer schema **and** consumer `unknown == "RAISE"` | CRITICAL |

> **`UNDECLARED_FIELD` directionality:** The unknown-field policy only applies during `load()`
> (deserialization), which is what the **consumer** does. The producer serializes (`dump()`) its
> declared fields outward and is unaffected by this setting. Therefore only the consumer's
> `UnknownFieldBehaviour` is checked. When the consumer's policy is `IGNORE` or `ALLOW`, the rule
> returns no violation.
>
> **Rule constructor:** `UndeclaredFieldRule` carries `consumer_unknown: UnknownFieldBehaviour` as
> a constructor parameter. The service layer reads `ContractSchema.unknown` (or
> `ContractField.unknown` for nested objects) from the consumer contract and instantiates the rule
> with the correct value per schema pair. The `check(producer_field, consumer_field)` Protocol
> signature remains unchanged. The rule never references any framework-specific constant.

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
      "producer": { "required": false },
      "consumer": { "required": true },
      "message": "Field 'metadata.discount_code' is optional in Producer but required in Consumer."
    },
    {
      "rule": "MISSING_FIELD",
      "severity": "CRITICAL",
      "field_path": "items.sku",
      "producer": { "exists": false },
      "consumer": { "required": true },
      "message": "Field 'items.sku' is missing in Producer but required in Consumer."
    },
    {
      "rule": "NULLABILITY_MISMATCH",
      "severity": "CRITICAL",
      "field_path": "total_price",
      "producer": { "allow_none": true },
      "consumer": { "allow_none": false },
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

1. Load config.
2. Scan and parse local schemas (skippable via `--skip-scan`).
3. Fetch latest contracts from S3 per topic (by `LastModified`).
4. Run all `ValidationRule`s for each producer–consumer pair.
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

### `sentinel publish` — post-merge

1. Load config.
2. Scan and parse local schemas.
3. SHA-256 hash each canonical JSON (keys sorted).
4. Compare against current S3 object hash.
5. Write to S3 only if hash differs; log "no change, skipping" otherwise.
6. Exit `0` always.


---


## 7. Configuration

### `Settings` — env vars (pydantic-settings)

| Env Var | Type | Required | Default |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | `str` | Yes | — |
| `AWS_SECRET_ACCESS_KEY` | `str` | Yes | — |
| `AWS_DEFAULT_REGION` | `str` | No | `"us-east-1"` |
| `SENTINEL_REPO_NAME` | `str \| None` | No | `None` |

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

### Parser — driven by `framework`

| Value | Adapter |
|---|---|
| `"marshmallow"` | `MarshmallowParser` |
| other | `UnsupportedFrameworkError` |

### Store — driven by `storage.type`

| Value | Adapter |
|---|---|
| `"s3"` | `S3ContractStore` |
| other | `UnsupportedStorageError` |
