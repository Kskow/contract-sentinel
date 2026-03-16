set dotenv-load := true

# Run lint checks
lint:
    uv run ruff check .

# Auto-format all files
format:
    uv run ruff format .

# Assert formatting without writing (CI-safe)
format-check:
    uv run ruff format --check .

# Static type analysis
typecheck:
    uv run ty check

# Run full test suite in parallel (-n auto via addopts)
test:
    uv run pytest

# Run tests sequentially — use when debugging with --pdb
test-seq:
    uv run pytest -n0

# Run tests with coverage report
test-cov:
    uv run pytest --cov=contract_sentinel --cov-report=term-missing

# Auto-fix lint violations and reformat in one shot
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Full quality gate — mirrors CI
check:
    just lint
    just format-check
    just typecheck
    just test

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
