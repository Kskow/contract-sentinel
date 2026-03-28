# Design — Library Polish & PyPI Release

## 1. Package Metadata

### Version alignment

`pyproject.toml` currently says `version = "0.1.0"` while `contract_sentinel/__init__.py`
hardcodes `__version__ = "0.0.1"`. `pyproject.toml` is the single source of truth for the
build system — the `__init__.py` string is what users see at runtime (`import contract_sentinel;
contract_sentinel.__version__`). Align by updating `pyproject.toml` to `"0.0.1"`.

A proper `importlib.metadata` wiring is deferred to a future feature. The manual sync is
acceptable for V1 given a single maintainer and infrequent releases.

### Required `pyproject.toml` additions

```toml
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "Kskow", email = "k.skowronski1993@gmail.com" }]
keywords = ["contract testing", "schema validation", "marshmallow", "API contracts", "testing"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Testing",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

[project.urls]
Homepage   = "https://github.com/Kskow/contract-sentinel"
Repository = "https://github.com/Kskow/contract-sentinel"
Issues     = "https://github.com/Kskow/contract-sentinel/issues"
```

---

## 2. PyPI Publishing — Trusted Publisher (OIDC)

### Why Trusted Publisher over API token

| Concern | API token | Trusted Publisher |
|---|---|---|
| Secret rotation | Manual; token lives in GitHub secrets | No secret — OIDC token is ephemeral |
| Blast radius if leaked | Token can publish until revoked | Nothing to leak |
| Setup complexity | Add one GitHub secret | 5-minute one-time config on PyPI |

Trusted Publisher is the current PyPI best practice and the right default for a new project.

### How it works

1. GitHub Actions requests a short-lived OIDC token from GitHub's identity provider.
2. PyPI verifies the token against the registered trusted publisher configuration (owner, repo, workflow file, environment name).
3. PyPI issues a short-lived upload token scoped to that package only.
4. `uv publish` uses that token to upload.

No secrets are stored anywhere in the repository or GitHub.

### Workflow design

Trigger: `push` on tags matching `v*`. The quality gate (lint, types, tests) is a
separate workflow that runs on PR and push to main — by the time a tag is cut, the
developer has already passed CI. No `needs:` dependency on the quality job is required.

```
push tag v0.0.1
  └─ publish.yml
       ├─ uv build      → dist/contract_sentinel-0.0.1-py3-none-any.whl
       │                   dist/contract_sentinel-0.0.1.tar.gz
       └─ uv publish --trusted-publishing always
```

The job uses `environment: pypi` — this ties it to a named GitHub Actions environment, which
is the surface PyPI uses to identify the trusted publisher.

### One-time PyPI setup (manual — not scriptable)

This must be done once before the first tag is pushed:

1. Create an account at https://pypi.org if needed.
2. Go to **Account Settings → Publishing**.
3. Under **"Add a new pending trusted publisher"** fill in:
   - **Owner:** `Kskow`
   - **Repository name:** `contract-sentinel`
   - **Workflow filename:** `publish.yml`
   - **Environment name:** `pypi`
4. Submit. PyPI will accept the first upload from this workflow even before the package
   exists (pending trusted publisher).

Also create the matching **GitHub Actions environment**:

1. Go to the repo → **Settings → Environments → New environment**.
2. Name it `pypi`.
3. No protection rules required for a single-maintainer project (add branch protection
   later if contributors are added).

---

## 3. README Structure

The current README is written for contributors (Docker setup, project structure). After
this feature it is rewritten for library users. Developer/contributor content moves to
`contributors/contributing.md`.

### New README outline

```
[badges: PyPI | Python | License | CI]

# Contract Sentinel
One-line tagline

## Why Contract Sentinel      ← the existing comparison table (keep it)
## How It Works               ← high-level 4-step flow
## What's Supported           ← storage + schema frameworks table with roadmap column
## Installation               ← pip install variants
## Quickstart                 ← mark → publish → validate (3 concrete steps)
## GitHub Actions Integration ← the two workflow snippets users actually need
## CLI Reference              ← commands + flags table
## Contributing               ← one-paragraph pointer to contributors/
```

### Supported / Roadmap table (in README)

| Concern | Supported | Planned |
|---|---|---|
| Schema frameworks | Marshmallow 3 & 4 | Pydantic, attrs, dataclasses |
| Contract stores | AWS S3 | GCS, Azure Blob |
| Validation | Hard Diff (deterministic) | AI Semantic Audit |

---

## 4. `contributors/` Directory

### File map

| File | Content | Source |
|---|---|---|
| `contributors/contributing.md` | Dev env setup, `just` commands, PR workflow | Extracted from current README |
| `contributors/how-to-add-a-rule.md` | Rule authoring guide | **Moved** from `docs/how-to-add-a-rule.md` |
| `contributors/how-to-add-a-parser.md` | Parser authoring guide | New |
| `contributors/how-to-add-a-contract-store.md` | Store authoring guide | New |

`docs/how-to-add-a-rule.md` is deleted after the move. No other file in the repo
references it by path.

### Parser guide key content

- Implement `SchemaParser(ABC)` from `adapters/schema_parsers/parser.py`.
- Add a `Framework` member to `domain/framework.py`.
- Register a `case Framework.X:` branch in `factory.get_parser()`.
- Add the framework's package to `pyproject.toml` optional-dependencies.
- Write integration tests in `tests/integration/test_adapters/`.

### Store guide key content

- Implement `ContractStore(ABC)` from `adapters/contract_store.py` (5 abstract methods:
  `get_file`, `put_file`, `list_files`, `file_exists`, `delete_file`).
- Register a `case "provider":` branch in `factory.get_store()`.
- Add the provider SDK to `pyproject.toml` optional-dependencies.
- Write integration tests in `tests/integration/test_adapters/`.

---

## 5. Full File Changeset

| File | Action |
|---|---|
| `pyproject.toml` | Modify — add metadata fields; fix version to `0.0.1` |
| `LICENSE` | Create — MIT, 2026, Kskow |
| `.github/workflows/publish.yml` | Create — tag-triggered build + publish |
| `README.md` | Rewrite — user-facing |
| `docs/how-to-add-a-rule.md` | Delete — content moved to `contributors/` |
| `contributors/contributing.md` | Create |
| `contributors/how-to-add-a-rule.md` | Create (moved content) |
| `contributors/how-to-add-a-parser.md` | Create |
| `contributors/how-to-add-a-contract-store.md` | Create |
