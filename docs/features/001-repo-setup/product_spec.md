# Product Spec — Repository Setup

**Feature slug:** `001-repo-setup`
**Status:** `ready-for-dev`
**Created:** 2026-03-16

---

## Problem

The repository is empty. Before any feature can be built, the project needs a consistent, reproducible foundation: package management, code quality tooling, a local dev environment via Docker, task automation via `just`, and a CI pipeline that enforces quality gates on every push.

## Goals

- Establish the canonical Python package structure (`domain/`, `ports/`, `adapters/`, `cli/`, `tests/`)
- Lock the toolchain: `uv` for packages, `ruff` for lint/format, `ty` for type-checking, `pytest` + `pytest-xdist` for tests
- Make the full quality check suite runnable with a single `just check` command
- Provide a Docker Compose environment for local development and integration tests (including LocalStack for future AWS emulation)
- Enforce all quality gates in a GitHub Actions CI pipeline with a pinned `uv` version

## Out of Scope

- Any business logic
- LocalStack seed scripts (deferred to first feature that needs AWS)
- Publishing / release pipeline (deferred)

## Acceptance Criteria

1. `uv sync` completes on a fresh clone
2. `just check` runs lint, format check, type check, and tests — all green
3. `docker compose up -d` starts without errors
4. Opening a PR triggers the GitHub Actions quality pipeline
