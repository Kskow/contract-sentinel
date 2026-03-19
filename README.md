# Contract Sentinel

> **Status: Early Development** 🚧

Contract Sentinel is an open-source contract testing tool for Python that **eliminates the need for a central broker**. It uses runtime introspection to extract schemas, your own cloud storage (S3) as the contract registry, and a Dual-Layer Validation strategy (Hard Diff + AI Semantic Audit) to catch breaking changes without blocking safe ones.

## Why Contract Sentinel?

| Problem | Solution |
|---|---|
| Pact/Broker = vendor lock-in | You own your contracts — stored in your S3 |
| Schema drift goes undetected until prod | CI gate fails on breaking changes before merge |
| AI false positives block safe changes | Hard Diff runs first; AI only invoked on real diffs |
| Opaque validation rules | All Hard Diff logic is open source and auditable |

## How It Works

1. **Discover** — Sentinel scans for classes decorated with `@contract`
2. **Compare** — Hard Diff compares local schema against the registry version
3. **Audit** — If a structural difference is found, an LLM decides if it's a *breaking* change
4. **Gate** — Exit `0` (safe) or `1` (breaking) drives your CI pass/fail

## Quickstart

> **Prerequisites:** Docker Engine must be installed.

```bash
# 1. Copy the env template
cp .env.local .env

# 2. Start the local dev environment (app + LocalStack)
just docker-up

# 3. Open a shell inside the container
just docker-shell

# 4. Run the full quality gate (lint + format + types + tests)
just check
```

## Docker Commands

| Command | What it does |
|---|---|
| `just docker-up` | Start app + LocalStack in the background |
| `just docker-down` | Stop all containers |
| `just docker-shell` | Open an interactive shell inside the app container |
| `just logs` | Tail all container logs |
| `just docker-prune` | Stop everything and wipe all images, volumes, and build cache |

## Project Structure

```
contract_sentinel/
├── domain/             # Pure business logic — no I/O, no infra imports
│   ├── participant.py  # @contract decorator, Role enum, ContractMeta
│   ├── schema.py       # ContractField, ContractSchema, UnknownFieldBehaviour
│   ├── rules/
│   │   ├── rule.py               # Rule(ABC) — check(producer | None, consumer | None)
│   │   ├── violation.py          # Violation dataclass
│   │   ├── type_mismatch.py
│   │   ├── nullability_mismatch.py
│   │   ├── requirement_mismatch.py
│   │   ├── direction_mismatch.py
│   │   ├── metadata_mismatch.py  # allowed_values, range, length + generic key checks
│   │   ├── missing_field.py      # fires when producer is None
│   │   ├── undeclared_field.py   # fires when consumer.unknown == FORBID
│   │   └── nested_field.py       # recursive sub-field validation
│   ├── framework.py    # Framework enum + detect_framework
│   ├── loader.py       # load_marked_classes — filesystem scanner
│   └── errors.py       # UnsupportedFrameworkError, UnsupportedStorageError, MissingDependencyError
├── adapters/           # ABC + implementation(s) per concern
│   ├── contract_store.py   # ContractStore(ABC) + S3ContractStore
│   └── schema_parser.py    # SchemaParser(ABC)  + Marshmallow3Parser
├── services/           # Use-case orchestration (validate, publish)
└── cli/                # Typer CLI entrypoints

tests/
├── unit/
│   └── domain/      # Pure logic tests — mirrors contract_sentinel/domain/
└── integration/
    └── adapters/    # Adapter tests — LocalStack / moto / real subprocess
```

## Tech Stack

| Concern | Tool |
|---|---|
| Runtime | Python 3.12 |
| Package manager | `uv` |
| Linting & formatting | `ruff` |
| Type checking | `ty` |
| Testing | `pytest` + `pytest-xdist` |
| Local AWS emulation | LocalStack |
| Task runner | `just` |
| CI | GitHub Actions |

## CI

Every push and pull request targeting `main` runs the full quality gate via GitHub Actions:

```
Lint → Format check → Type check → Test
```

Each step is isolated so the PR UI shows exactly which gate failed.

## Contributing

See `docs/features/` for planned work. Each feature directory contains a `product_spec.md` and a `tickets.md` that is the source of truth for implementation tasks.
