set dotenv-load := true

# ── Quality gate (always runs inside the app container) ───────────────────────

# Run lint checks
lint:
    docker compose run --rm app uv run ruff check .

# Auto-format all files
format:
    docker compose run --rm app uv run ruff format .

# Assert formatting without writing (CI-safe)
format-check:
    docker compose run --rm app uv run ruff format --check .

# Static type analysis
typecheck:
    docker compose run --rm app uv run ty check

# Run full test suite in parallel (-n auto via addopts)
test:
    docker compose run --rm app uv run pytest

# Run tests sequentially — use when debugging with --pdb
test-seq:
    docker compose run --rm app uv run pytest -n0

# Run tests with coverage report
test-cov:
    docker compose run --rm app uv run pytest --cov=contract_sentinel --cov-report=term-missing

# Auto-fix lint violations and reformat in one shot
fix:
    docker compose run --rm app uv run ruff check --fix .
    docker compose run --rm app uv run ruff format .

# Full quality gate — mirrors CI
check:
    docker compose run --rm app sh -c "uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest"

# ── Docker ────────────────────────────────────────────────────────────────────

# Start local dev environment
docker-up:
    docker compose up -d

# Stop local dev environment
docker-down:
    docker compose down

# Tail all container logs
logs:
    docker compose logs -f

# Stop all containers and wipe all images, volumes, and build cache
docker-prune:
    docker stop $(docker ps -a -q) || true
    docker system prune --all --volumes --force

# Open an interactive shell inside a fresh app container
docker-shell:
    docker compose run --rm app bash
