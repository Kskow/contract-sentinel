[![PyPI version](https://img.shields.io/pypi/v/contract-sentinel)](https://pypi.org/project/contract-sentinel/)
[![Python versions](https://img.shields.io/pypi/pyversions/contract-sentinel)](https://pypi.org/project/contract-sentinel/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Kskow/contract-sentinel/actions/workflows/quality.yml/badge.svg)](https://github.com/Kskow/contract-sentinel/actions/workflows/quality.yml)

# Contract Sentinel

Contract Sentinel is an open-source Python contract testing tool that **eliminates the need for a central broker**. It introspects your schema classes at runtime, stores contracts in your own S3 bucket, and runs a Hard Diff validation to distinguish safe schema changes from breaking ones — failing CI before a breaking change ever reaches production.

## Why Contract Sentinel?

| Problem | Solution |
|---|---|
| Pact/Broker = vendor lock-in | You own your contracts — stored in your S3 bucket |
| Schema drift goes undetected until prod | CI gate fails on breaking changes before merge |
| Opaque validation rules | All validation logic is open source and auditable |

## How It Works

1. **Discover** — Sentinel scans for classes decorated with `@contract`
2. **Publish** — Parsed schemas are serialised and stored in your S3 bucket on merge to main
3. **Compare** — Hard Diff compares the local schema against the published registry version on PR
4. **Gate** — Exit `0` (safe) or `1` (breaking) drives your CI pass/fail

## What's Supported

| Concern | Supported | Planned |
|---|---|---|
| Schema frameworks | Marshmallow 3 & 4 | Pydantic, attrs, dataclasses |
| Contract stores | AWS S3 | GCS, Azure Blob |
| Validation | Hard Diff (deterministic) | AI Semantic Audit |

## Installation

```bash
pip install contract-sentinel              # core only (no schema parser, no store)
pip install contract-sentinel[marshmallow] # + marshmallow parser
pip install contract-sentinel[s3]          # + S3 store
pip install contract-sentinel[all]         # everything
```

## Quickstart

### 1. Configure your project

Add a `[tool.sentinel]` table to your `pyproject.toml`. Non-secret config lives here — it's version-controlled alongside your code and automatically picked up by every `sentinel` command, so you never repeat it in CI:

```toml
[tool.sentinel]
name      = "my-service"     # identifies your service in the contract registry
s3_bucket = "my-contracts"   # S3 bucket where contracts are stored
s3_path   = "contract_tests" # key prefix inside the bucket
```

Alternatively, all three can be set as environment variables using the `SENTINEL_` prefix: `SENTINEL_NAME`, `SENTINEL_S3_BUCKET`, `SENTINEL_S3_PATH`. `pyproject.toml` takes precedence when both are present.

AWS credentials are the only values that must be supplied separately (as CI secrets) since they must never appear in version-controlled files.

### 2. Mark your schemas

Decorate your Marshmallow schemas with `@contract`, declaring the topic name and whether this service is the producer or consumer of that schema:

```python
from marshmallow import Schema, fields
from contract_sentinel import contract, Role

@contract(topic="orders", role=Role.PRODUCER)
class OrderSchema(Schema):
    id = fields.Integer(required=True)
    status = fields.String(required=True)
    amount = fields.Float(required=True)
```

### 3. Publish and validate on merge to main

Add a job that runs after your tests pass on `main`. It publishes your updated schemas and then immediately validates all contracts in the registry — catching cross-service breakage the moment it lands:

```yaml
publish-contracts:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: pip install contract-sentinel[all]
    - run: sentinel publish-contracts
      env:
        AWS_DEFAULT_REGION: us-east-1
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    - run: sentinel validate-published-contracts
      env:
        AWS_DEFAULT_REGION: us-east-1
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### 4. Validate on PR

Add a job that runs on every pull request. It compares local schemas against the published contracts and fails if a breaking change is detected:

```yaml
validate-contracts:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: pip install contract-sentinel[all]
    - run: sentinel validate-local-contracts
      env:
        AWS_DEFAULT_REGION: us-east-1
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## CLI Reference

| Command | Flag | Default | Description |
|---|---|---|---|
| `sentinel publish-contracts` | `--path` | `.` | Directory to scan for `@contract` classes |
| | `--verbose` | off | Show unchanged schemas |
| `sentinel validate-local-contracts` | `--path` | `.` | Directory to scan for `@contract` classes |
| | `--dry-run` | off | Print report but always exit 0 |
| | `--verbose` | off | Show passing contracts |
| | `--how-to-fix` | off | Print copy-paste fix suggestions for each failing pair |
| | `--markdown` | off | Format output as Markdown for use as a PR comment |
| `sentinel validate-published-contracts` | `--dry-run` | off | Print report but always exit 0 |
| | `--verbose` | off | Show passing contracts |
| | `--how-to-fix` | off | Print copy-paste fix suggestions for each failing pair |
| | `--markdown` | off | Format output as Markdown for use as a PR comment |

## Parser Limitations

The parser introspects schema classes **statically at import time**. Unsupported fields and validators fail silently — they are skipped and produce no contract entry, so the diff engine will not catch mismatches that involve them.

### Marshmallow

**Unsupported fields:**
- `fields.Tuple` — positional heterogeneous types have no JSON Schema equivalent
- `fields.Method`, `fields.Function` — return type is determined at runtime by a user-defined callable
- Custom field subclasses — any type not in the built-in type map
- `fields.Pluck` — treated as a full `Nested` object, but emits a bare scalar on the wire

**Unsupported validators:**
- Custom validator subclasses

**Other limitations:**
- Schema-level hooks (`@validates`, `@validates_schema`, `@pre_load`, `@post_load`) are not captured — constraints defined there are invisible to the diff engine.
- Callable `load_default` / `dump_default` values (e.g. `load_default=list` or `load_default=lambda: {}`) are silently omitted from the contract. A callable is a runtime factory with no static JSON representation, so it carries no meaningful contract information. Scalar defaults (strings, ints, booleans, lists, dicts) are captured normally.

---

## Contributing

See `contributors/contributing.md` for local setup instructions, the full `just` command reference, and the PR workflow. To extend the library — adding a new validation rule, schema parser, or contract store — see the how-to guides in the same directory.
