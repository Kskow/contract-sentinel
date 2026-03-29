# Contributing to Contract Sentinel

## Prerequisites

- **Docker Engine** — all dev tooling runs inside containers; nothing needs to be installed locally beyond Docker itself.

## Local Setup

```bash
# 1. Copy the env template (one-time)
cp .env.local .env

# 2. Start the app container and LocalStack
just docker-up

# 3. Open a shell inside the app container
just docker-shell

# 4. Run the full quality gate from inside the container
just check
```

`.env.local` is committed and contains static fake credentials for LocalStack.
`.env` is gitignored — never commit it.

## `just` Command Reference

| Command | What it does |
|---|---|
| `just check` | Full quality gate: lint + format-check + typecheck + test (mirrors CI) |
| `just fix` | Auto-fix lint violations and reformat all files |
| `just lint` | `ruff check .` — lint only |
| `just format` | `ruff format .` — format only |
| `just format-check` | `ruff format --check .` — CI-safe, no writes |
| `just typecheck` | `uv run ty check` |
| `just test` | `uv run pytest` (parallel via `-n auto`) |
| `just test-seq` | `uv run pytest -n0` — sequential, safe for `--pdb` debugging |
| `just test-cov` | Tests with coverage report |
| `just docker-up` | `docker compose up -d` — start app + LocalStack |
| `just docker-down` | `docker compose down` — stop all containers |
| `just docker-shell` | Open an interactive bash shell inside a fresh app container |
| `just docker-prune` | Stop all containers and wipe all images, volumes, and build cache |
| `just logs` | Tail all container logs |

## PR Workflow

1. Branch off `main` — one branch per feature or ticket.
2. Make one logical commit per ticket; keep commits focused and reviewable.
3. Run `just check` and ensure it passes before pushing.
4. Open a pull request against `main` — CI will run the same quality gate automatically.

## Extending the Library

See the how-to guides in this directory for step-by-step instructions:

- [`how-to-add-a-rule.md`](how-to-add-a-rule.md) — add a new contract validation rule
- [`how-to-add-a-parser.md`](how-to-add-a-parser.md) — add support for a new schema framework
- [`how-to-add-a-contract-store.md`](how-to-add-a-contract-store.md) — add support for a new storage backend
