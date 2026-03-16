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

tests/
├── unit/        # Pure logic tests — no infra, no I/O mocking
└── integration/ # Adapter tests — LocalStack / moto / real subprocess
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
