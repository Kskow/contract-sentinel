# Repository Setup — Dev Tickets

**Feature slug:** `001-repo-setup`
**Spec:** `docs/features/001-repo-setup/product_spec.md`
**Created:** 2026-03-16

---

## Architecture Notes

### Project Identity

- **Package name:** `contract_sentinel` (underscore — importable)
- **Distribution name:** `contract-sentinel` (hyphen — pip/uv installable)
- **Python version:** 3.12 (pinned via `.python-version`)
- **Package manager:** `uv` — single source of truth for deps and script execution

### Directory Layout (Target State)

```
contract-sentinel/
├── contract_sentinel/        # Installable Python package
│   ├── __init__.py
│   ├── domain/               # Pure business logic — no I/O, no infra imports
│   │   └── __init__.py
│   ├── ports/                # Abstract interfaces (Protocol)
│   │   └── __init__.py
│   ├── adapters/             # Concrete cloud + local implementations
│   │   └── __init__.py
│   └── cli/                  # Typer CLI entrypoints
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── unit/                 # Pure logic tests — no infra, no mocking of I/O
│   │   └── __init__.py
│   └── integration/          # Adapter tests — LocalStack / moto / real subprocess
│       └── __init__.py
├── .github/
│   └── workflows/
│       └── quality.yml
├── .python-version
├── .gitignore
├── .dockerignore
├── docker-compose.yml
├── Dockerfile
├── justfile
└── pyproject.toml
```

### Toolchain Decisions

| Concern | Tool | Rationale |
|---|---|---|
| Package management | `uv` | Fastest resolver, lockfile, `uv run` for script isolation |
| Linting | `ruff check` | Single tool replacing flake8 + isort + pyupgrade + bugbear |
| Formatting | `ruff format` | Replaces Black, consistent with ruff config |
| Type checking | `ty` | Astral's new checker; fast, strict, pairs naturally with ruff |
| Testing | `pytest` | Industry standard; `pytest-cov` for coverage |
| Parallel testing | `pytest-xdist` | `-n auto` maps one worker per CPU — free speedup as test suite grows |
| Task runner | `just` | Declarative, portable, one command per concern |

### Ruff Rules (Recommended)

Selected rule sets for a clean, modern Python 3.12 codebase:

| Code | Plugin | What it catches |
|---|---|---|
| `E`, `W` | pycodestyle | Style issues |
| `F` | Pyflakes | Undefined names, unused imports |
| `I` | isort | Import ordering |
| `UP` | pyupgrade | Outdated syntax (pre-312 patterns) |
| `B` | flake8-bugbear | Likely bugs and design problems |
| `SIM` | flake8-simplify | Unnecessary complexity |
| `TCH` | flake8-type-checking | Imports that should live under `TYPE_CHECKING` |
| `ANN` | flake8-annotations | Missing type annotations |
| `RUF` | Ruff-native | Ruff's own best-practice rules |

Ignored: `ANN101`, `ANN102` (annotating `self`/`cls` is noise, not value).

### Docker Strategy

- **Base image:** `python:3.12-slim` — minimal attack surface
- **`uv` in Docker:** install via the official `ghcr.io/astral-sh/uv` copy trick (no pip needed)
- **Docker Compose services:**
  - `app` — runs the container; mounts source for live reload during dev
  - `localstack` — AWS emulation on `http://localhost:4566` (ready for future adapter tickets; no seeding yet)
- The Dockerfile's primary job right now is reproducible test execution, not production deployment

### GitHub Actions Strategy

- Trigger: `push` and `pull_request` on `main`
- `uv` version is **pinned** in the workflow — reproducible installs, no surprise breakage from a new uv release
- Cache key is bound to `uv.lock` — cache is invalidated exactly when deps change, never otherwise
- Steps 5–8 are separate named steps, not `just check`, so the PR UI shows exactly which gate failed
- No secrets required at this stage (no cloud calls)

### Distributed Systems / Future Concerns

- **Nothing distributed yet.** LocalStack is seeded empty; no IAM, no buckets.
- The `scripts/` directory is created now so future `seed_local.py` has a home.
- `ENV=local` env var convention is established in `docker-compose.yml` today so adapters can toggle LocalStack endpoints later without changing Compose config.

---

## Tickets

---

### SETUP-01 — uv Project Scaffold & Directory Skeleton

**Depends on:** –
**Type:** Infra

**Goal:**
Initialize the `uv` project, create the canonical package + test directory tree, and add a `.gitignore` so the repo is in a clean, importable state from day one.

**Files to create:**
- `pyproject.toml` — `uv init` output, project metadata, `pytest` + `pytest-xdist` config section, no ruff/ty yet (SETUP-02)
- `.python-version` — single line: `3.12`
- `.gitignore` — standard Python gitignore (`.venv/`, `__pycache__/`, `*.pyc`, `.env`, `dist/`, `.pytest_cache/`, `.ruff_cache/`, `.ty_cache/`)
- `README.md` — project overview: what Contract Sentinel is, why it exists (no central broker), quickstart (`uv sync` → `just check`), and a "Status: Early Development" badge so early visitors set expectations correctly
- `CLAUDE.md` — Claude Code context file: project purpose, stack snapshot (Python 3.12, uv, ruff, ty, pytest, LocalStack), file placement conventions (`domain/`, `ports/`, `adapters/`, `cli/`), key `just` commands, and a note that `docs/features/<slug>/tickets.md` is the source of truth for planned work
- `contract_sentinel/__init__.py` — empty (or `__version__ = "0.1.0"`)
- `contract_sentinel/domain/__init__.py` — empty
- `contract_sentinel/ports/__init__.py` — empty
- `contract_sentinel/adapters/__init__.py` — empty
- `contract_sentinel/cli/__init__.py` — empty
- `tests/__init__.py` — empty
- `tests/unit/__init__.py` — empty
- `tests/integration/__init__.py` — empty
- `scripts/.gitkeep` — placeholder so the directory is tracked

**`pyproject.toml` must include:**
```toml
[project]
name = "contract-sentinel"
version = "0.1.0"
description = "Open-source contract testing without a central broker"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-n auto"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-xdist>=3.0",
]
```

> **Note on `addopts = "-n auto"`:** this bakes parallel execution into every `pytest` run by default.
> If you ever need to debug a single test with `--pdb`, pass `-n0` to override: `uv run pytest -n0 tests/unit/test_foo.py`.

**Done when:**
- [ ] `uv sync` exits 0 on a clean clone (lockfile committed)
- [ ] `uv run python -c "import contract_sentinel"` exits 0
- [ ] `uv run pytest` exits 0 (no tests yet — "no tests collected" is a pass)
- [ ] `uv run pytest --co -q` shows workers being spawned (confirms xdist is active)
- [ ] All directories listed above exist and are tracked by git
- [ ] `README.md` is present, renders correctly on GitHub, and includes a quickstart block
- [ ] `CLAUDE.md` is present and covers: project purpose, stack, file placement conventions, and key `just` commands

---

### SETUP-02 — Linting & Type-Checking Configuration

**Depends on:** SETUP-01
**Type:** Infra

**Goal:**
Configure `ruff` (lint + format) and `ty` (static type analysis) as dev dependencies with strict, opinionated rules baked into `pyproject.toml`. The empty scaffold must pass all checks clean.

**Files to modify:**
- `pyproject.toml` — add ruff and ty to `[dependency-groups] dev`, add `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.isort]`, and `[tool.ty]` sections

**Configuration to add:**
```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-xdist>=3.0",
    "ruff>=0.9",
    "ty>=0.0.0a1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "TCH", "ANN", "RUF"]
ignore = [
    "ANN101",  # `self` does not need a type annotation
    "ANN102",  # `cls` does not need a type annotation
]

[tool.ruff.lint.isort]
known-first-party = ["contract_sentinel"]

[tool.ty]
# Strict type checking — no implicit Any, no untyped defs
python-version = "3.12"
```

**Done when:**
- [ ] `uv sync` picks up `ruff` and `ty` (lockfile updated)
- [ ] `uv run ruff check .` exits 0 with no violations
- [ ] `uv run ruff format --check .` exits 0 (all files already formatted)
- [ ] `uv run ty check` exits 0 with no errors on the empty scaffold

---

### SETUP-03 — Justfile Task Runner

**Depends on:** SETUP-02
**Type:** Infra

**Goal:**
Define all developer-facing quality commands in a `justfile` so every check is one short, memorable command regardless of underlying tool invocation.

**Files to create:**
- `justfile`

**Recipes to implement:**

| Command | What it runs | When to use |
|---|---|---|
| `just lint` | `uv run ruff check .` | Check for lint violations |
| `just format` | `uv run ruff format .` | Auto-format all files |
| `just format-check` | `uv run ruff format --check .` | Assert formatting (CI-safe, no writes) |
| `just typecheck` | `uv run ty check` | Static type analysis |
| `just test` | `uv run pytest` | Run full test suite in parallel (`-n auto` via `addopts`) |
| `just test-seq` | `uv run pytest -n0` | Run tests sequentially — use when debugging with `--pdb` |
| `just test-cov` | `uv run pytest --cov=contract_sentinel --cov-report=term-missing` | Tests with coverage report (also parallel) |
| `just fix` | `uv run ruff check --fix . && uv run ruff format .` | Auto-fix lint + format in one shot |
| `just check` | `just lint && just format-check && just typecheck && just test` | Full quality gate (mirrors CI) |
| `just up` | `docker compose up -d` | Start local dev environment |
| `just down` | `docker compose down` | Stop local dev environment |
| `just logs` | `docker compose logs -f` | Tail all container logs |

**Justfile must start with:**
```just
set dotenv-load := true
```
So that a local `.env` file (gitignored) is auto-loaded for environment overrides.

**Done when:**
- [ ] `just --list` shows all recipes with no errors
- [ ] `just check` exits 0 (all four quality gates pass on the empty scaffold)
- [ ] `just fix` is idempotent — running it twice produces no diff
- [ ] `just test-seq` runs without the `-n auto` flag (confirmed via `pytest -v` output showing no worker lines)

---

### SETUP-04 — Docker & Docker Compose Local Environment

**Depends on:** SETUP-03
**Type:** Infra

**Goal:**
Create a `Dockerfile` using `uv` as the package manager and a `docker-compose.yml` that boots the app container alongside a LocalStack instance, giving a fully self-contained local dev environment.

**Files to create:**
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

**`Dockerfile` design (multi-stage):**
```
Stage 1 — deps:
  - Base: python:3.12-slim
  - Copy uv binary from ghcr.io/astral-sh/uv:latest
  - Copy pyproject.toml + uv.lock
  - RUN uv sync --frozen --no-install-project (install deps only, cached layer)

Stage 2 — app:
  - FROM deps
  - Copy full source
  - RUN uv sync --frozen (install the project itself)
  - Default CMD: uv run pytest (so `docker compose run app` runs the test suite)
```

**`docker-compose.yml` services:**

| Service | Image | Purpose |
|---|---|---|
| `app` | Built from `Dockerfile` | Runs tests / future CLI; mounts `./` as volume for dev |
| `localstack` | `localstack/localstack:3` | AWS emulation; exposes port `4566` |

**Key environment variables in Compose:**
```yaml
environment:
  - ENV=local
  - AWS_DEFAULT_REGION=us-east-1
  - AWS_ACCESS_KEY_ID=test
  - AWS_SECRET_ACCESS_KEY=test
  - AWS_ENDPOINT_URL=http://localstack:4566
```

**`.dockerignore` must exclude:**
`.venv/`, `__pycache__/`, `*.pyc`, `.env`, `.git/`, `.ruff_cache/`, `.ty_cache/`, `dist/`

**Done when:**
- [ ] `docker compose build` exits 0
- [ ] `docker compose up -d` starts both `app` and `localstack` without errors
- [ ] `docker compose run --rm app` executes `uv run pytest` and exits 0
- [ ] `just up` and `just down` work end-to-end
- [ ] LocalStack health check is reachable: `curl http://localhost:4566/_localstack/health` returns 200

---

### SETUP-05 — GitHub Actions Quality Pipeline

**Depends on:** SETUP-04
**Type:** Infra

**Goal:**
Create a CI pipeline that automatically runs the full quality gate on every push and every pull request targeting `main`, with a pinned `uv` version for reproducible installs.

**Files to create:**
- `.github/workflows/quality.yml`

**Pipeline design:**

```
Trigger: push → main, pull_request → main
OS: ubuntu-latest
Python: 3.12

Steps:
  1. actions/checkout@v4
  2. astral-sh/setup-uv@v5
       with:
         uv-version: "0.6.6"        ← pinned; update deliberately, not silently
         python-version: "3.12"
  3. uv sync --frozen               ← cache is automatic via setup-uv's built-in cache
  4. [Quality gate — separate named steps]:
       "Lint"          → uv run ruff check .
       "Format check"  → uv run ruff format --check .
       "Type check"    → uv run ty check
       "Test"          → uv run pytest
```

> **On `uv` version pinning:** `setup-uv@v5` handles `~/.cache/uv` caching internally when `enable-cache: true` (the default). You do **not** need a separate `actions/cache` step. The cache key is automatically derived from `uv.lock`.
>
> To upgrade `uv` in CI: bump `uv-version` in this file deliberately and commit — never let it float to `latest`.
>
> Check the latest stable release at: https://github.com/astral-sh/uv/releases

Steps 4a–4d are **separate named steps** (not `just check`) so the CI UI shows exactly which gate failed.

**No secrets needed** — this pipeline makes zero network calls outside of dep installation.

**Branch protection reminder (manual step, not codeable):**
> After the first pipeline run succeeds, enable "Require status checks to pass before merging" on `main` and select the `quality` job. This turns the pipeline into a hard merge gate.

**Done when:**
- [ ] `.github/workflows/quality.yml` is present and valid YAML
- [ ] `uv-version` is set to a specific semver string (e.g., `"0.6.6"`), not `"latest"`
- [ ] Pushing to a branch and opening a PR triggers the workflow
- [ ] All four quality steps appear as distinct named checks in the GitHub PR UI
- [ ] Intentionally breaking a type annotation causes the `Type check` step (and only that step) to fail, confirming gate isolation

---
