# Library Polish & PyPI Release — Dev Tickets

**Feature slug:** `006-library-polish`
**Spec:** `docs/features/006-library-polish/product_spec.md`
**Design:** `docs/features/006-library-polish/design.md`
**Created:** 2026-03-28

---

## Architecture Notes

### No production or test code changes
All four tickets touch only `pyproject.toml`, `LICENSE`, GitHub Actions workflows, Markdown
files, and the `contributors/` directory. `just check` must pass before and after with zero
changes to Python source.

### Version alignment
`pyproject.toml` currently says `version = "0.1.0"`. `__init__.py` says `__version__ = "0.0.1"`.
TICKET-01 fixes `pyproject.toml` to `0.0.1`. `__init__.py` is untouched — it stays as-is per spec.

### Trusted Publisher — one manual step required
The `.github/workflows/publish.yml` workflow uses OIDC (no secrets). Before the first tag is pushed,
the developer must register the Trusted Publisher on PyPI and create the `pypi` environment in GitHub.
Full instructions are in TICKET-02. Skipping this step means the publish job will fail with a 403.

### `docs/how-to-add-a-rule.md` is deleted
The file is moved to `contributors/how-to-add-a-rule.md`. No other file in the repo references
it by path — verified by search. The `docs/` directory retains only `docs/features/`.

### Ticket order
TICKET-01 through TICKET-04 are all independent of each other. They can be done in any order
or in parallel. Suggested order: 01 → 02 → 03 → 04 (metadata first since it underpins the
publish workflow, then the workflow, then the user-facing README, then contributor guides).

---

## Tickets

### TICKET-01 — `pyproject.toml` metadata + `LICENSE`

**Depends on:** —
**Type:** Infra

**Goal:**
Complete the package metadata so `uv build` produces a PyPI-publishable artifact with correct
classifiers, URLs, author info, and a `LICENSE` file at the repo root.

**Files to create / modify:**
- `pyproject.toml` — modify
- `LICENSE` — create

**`pyproject.toml` changes (exact fields to add/change):**

Under `[project]`:
- `version` — change from `"0.1.0"` to `"0.0.1"`
- `readme = "README.md"` — add
- `license = { text = "MIT" }` — add
- `authors = [{ name = "Kskow", email = "k.skowronski1993@gmail.com" }]` — add
- `keywords = ["contract testing", "schema validation", "marshmallow", "API contracts", "testing"]` — add
- `classifiers` — add the list:
  ```toml
  classifiers = [
      "Development Status :: 3 - Alpha",
      "Intended Audience :: Developers",
      "License :: OSI Approved :: MIT License",
      "Programming Language :: Python :: 3",
      "Programming Language :: Python :: 3.12",
      "Topic :: Software Development :: Testing",
      "Topic :: Software Development :: Libraries :: Python Modules",
  ]
  ```

Add a new `[project.urls]` table after `[project.optional-dependencies]`:
```toml
[project.urls]
Homepage   = "https://github.com/Kskow/contract-sentinel"
Repository = "https://github.com/Kskow/contract-sentinel"
Issues     = "https://github.com/Kskow/contract-sentinel/issues"
```

**`LICENSE` content:**
Standard MIT license text, copyright year `2026`, copyright holder `Kskow`.

**Done when:**
- [ ] `pyproject.toml` `version` field is `"0.0.1"`
- [ ] `pyproject.toml` contains `readme`, `license`, `authors`, `keywords`, `classifiers`, and `[project.urls]` exactly as specified above
- [ ] `LICENSE` exists at the repo root with MIT text, year 2026, holder Kskow
- [ ] `uv build` completes without errors and produces `dist/contract_sentinel-0.0.1-py3-none-any.whl` and `dist/contract_sentinel-0.0.1.tar.gz`
- [ ] `just check` still passes

---

### TICKET-02 — GitHub Actions publish workflow

**Depends on:** TICKET-01 (version must be `0.0.1` before tagging)
**Type:** Infra

**Goal:**
Add a publish workflow so that `git tag v0.0.1 && git push --tags` is the entire release
process — no manual PyPI interaction required after the one-time setup below.

**Files to create / modify:**
- `.github/workflows/publish.yml` — create

**Workflow spec:**

```yaml
name: Publish

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
      contents: read

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up uv
        uses: astral-sh/setup-uv@v5
        with:
          uv-version: "0.6.6"
          python-version: "3.12"

      - name: Build
        run: uv build

      - name: Publish
        run: uv publish --trusted-publishing always
```

Use the same `uv-version` and `python-version` pinned in `quality.yml` (`0.6.6` / `3.12`).

**One-time manual setup (do this before pushing the first tag):**

**On PyPI:**
1. Log in at https://pypi.org.
2. Go to **Account Settings → Publishing → Add a new pending trusted publisher**.
3. Fill in:
   - **Owner:** `Kskow`
   - **Repository name:** `contract-sentinel`
   - **Workflow filename:** `publish.yml`
   - **Environment name:** `pypi`
4. Click **Add**. PyPI will now accept the first upload from this workflow.

**On GitHub:**
1. Go to the repo → **Settings → Environments → New environment**.
2. Name it exactly `pypi` (case-sensitive — must match `environment: pypi` in the workflow).
3. No branch/tag protection rules needed for a single-maintainer project.

**How to cut a release after setup:**
```bash
git tag v0.0.1
git push origin v0.0.1
# Watch the Actions tab — "Publish" job should appear and succeed.
```

**Done when:**
- [ ] `.github/workflows/publish.yml` exists with the exact structure above
- [ ] The workflow triggers only on `v*` tags (not on branch pushes or PRs)
- [ ] `environment: pypi` and `id-token: write` permission are present
- [ ] `uv-version` and `python-version` match `quality.yml`
- [ ] The one-time PyPI and GitHub Environment setup steps are completed
- [ ] Pushing a `v0.0.1` tag causes the Actions workflow to run and the package appears on https://pypi.org/project/contract-sentinel/

---

### TICKET-03 — README rewrite

**Depends on:** —
**Type:** Docs

**Goal:**
Replace the contributor-centric README with a user-facing library README that answers
"What is it?", "How do I install it?", and "How do I wire it into CI?" without requiring
the reader to know anything about Docker or `just`.

**Files to create / modify:**
- `README.md` — rewrite

**Required sections and content:**

**Badge row** (top of file, before the `#` heading):
- PyPI version: `https://img.shields.io/pypi/v/contract-sentinel`
- Python versions: `https://img.shields.io/pypi/pyversions/contract-sentinel`
- License: `https://img.shields.io/badge/license-MIT-blue.svg`
- CI status: `https://github.com/Kskow/contract-sentinel/actions/workflows/quality.yml/badge.svg`

**`## What's Supported`** — a table with a "Planned" column:

| Concern | Supported | Planned |
|---|---|---|
| Schema frameworks | Marshmallow 3 & 4 | Pydantic, attrs, dataclasses |
| Contract stores | AWS S3 | GCS, Azure Blob |
| Validation | Hard Diff (deterministic) | AI Semantic Audit |

**`## Installation`** — show all install variants:
```bash
pip install contract-sentinel              # core only (no schema parser, no store)
pip install contract-sentinel[marshmallow] # + marshmallow parser
pip install contract-sentinel[s3]          # + S3 store
pip install contract-sentinel[all]         # everything
```

**`## Quickstart`** — three numbered steps:
1. **Mark your schemas** — show a minimal `@contract` + `Role` example with a marshmallow `Schema`.
2. **Publish on merge to main** — show the minimal GitHub Actions job snippet using `sentinel publish-contracts`.
3. **Validate on PR** — show the minimal GitHub Actions job snippet using `sentinel validate-local-contracts`.

The CI snippets must include all required environment variables:
`SENTINEL_NAME`, `S3_BUCKET`, `SENTINEL_S3_PATH`, `AWS_DEFAULT_REGION`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

**`## CLI Reference`** — a table of all three commands and their flags:

| Command | Flag | Default | Description |
|---|---|---|---|
| `sentinel publish-contracts` | `--path` | `.` | Directory to scan for `@contract` classes |
| | `--verbose` | off | Show unchanged schemas |
| `sentinel validate-local-contracts` | `--path` | `.` | Directory to scan |
| | `--dry-run` | off | Print report but always exit 0 |
| | `--verbose` | off | Show passing contracts |
| | `--how-to-fix` | off | Print copy-paste fix suggestions |
| `sentinel validate-published-contracts` | `--dry-run` | off | |
| | `--verbose` | off | |
| | `--how-to-fix` | off | |

**`## Contributing`** — a short paragraph directing readers to `contributors/contributing.md`.
No Docker commands, no `just` commands — those live in the contributor guide.

Content from the current README that must **not** appear in the new one:
- Docker commands table
- Project structure tree
- Tech stack table
- CI section (the lint/format/type/test pipeline is implementation detail, not user-facing)

**Done when:**
- [ ] README opens with the four badges
- [ ] All required sections are present: Why, How It Works, What's Supported, Installation, Quickstart, CLI Reference, Contributing
- [ ] The Quickstart's publish and validate snippets are syntactically valid GitHub Actions YAML
- [ ] No Docker commands, no `just` commands, no internal project structure tree
- [ ] All links in the README resolve (badges point to correct URLs, contributing pointer is correct path)

---

### TICKET-04 — `contributors/` directory

**Depends on:** —
**Type:** Docs

**Goal:**
Create a `contributors/` directory with four self-contained guides — one for general dev setup,
one moved rule guide, and two new guides for parsers and stores — so contributors have everything
they need without reading source code.

**Files to create / modify:**
- `contributors/contributing.md` — create
- `contributors/how-to-add-a-rule.md` — create (content moved from `docs/how-to-add-a-rule.md`)
- `contributors/how-to-add-a-parser.md` — create
- `contributors/how-to-add-a-contract-store.md` — create
- `docs/how-to-add-a-rule.md` — delete

**`contributing.md` must cover:**
- Prerequisites (Docker Engine)
- Local setup sequence: `cp .env.local .env` → `just docker-up` → `just docker-shell`
- Full `just` commands reference table (copy from current README / CLAUDE.md)
- PR workflow: branch off main, one logical commit per ticket, `just check` must pass before pushing
- Pointers to the three how-to guides for extending the library

**`how-to-add-a-rule.md`:**
Copy the full content of `docs/how-to-add-a-rule.md` verbatim. The source file is then deleted.
No content changes — this is a pure move.

**`how-to-add-a-parser.md` must cover:**

1. **Create the parser file** — `contract_sentinel/adapters/schema_parsers/<framework>.py`
   Extend `SchemaParser(ABC)` from `contract_sentinel.adapters.schema_parsers.parser`. Implement
   `parse(self, cls: type) -> ContractSchema`. Show a skeleton class with the correct import block.

2. **Register the framework** — `contract_sentinel/domain/framework.py`
   Add a new member to the `Framework` enum (e.g. `PYDANTIC = "pydantic"`).

3. **Register in the factory** — `contract_sentinel/factory.py`
   Add a `case Framework.PYDANTIC:` branch to `get_parser()` following the exact same pattern
   as the existing `Framework.MARSHMALLOW` branch (lazy import, `MissingDependencyError` on
   `ImportError`).

4. **Add to `pyproject.toml`** — add the framework package to `[project.optional-dependencies]`
   and to the `all` group.

5. **Write integration tests** — `tests/integration/test_adapters/test_<framework>_parser.py`
   Test against a real schema class (no mocking). Follow the pattern in
   `tests/integration/test_adapters/test_marshmallow_parser.py`.

6. **Checklist** — a checkbox list mirroring the five steps above, plus `just check` passes.

**`how-to-add-a-contract-store.md` must cover:**

1. **Create the store file** — `contract_sentinel/adapters/<provider>_contract_store.py`
   (or add a class to `contract_store.py` if the provider is closely related to S3).
   Extend `ContractStore(ABC)` from `contract_sentinel.adapters.contract_store`. Implement all
   five abstract methods: `get_file`, `put_file`, `list_files`, `file_exists`, `delete_file`.
   Show the method signatures and their contracts (return types, ordering guarantee for
   `list_files`, no-op guarantee for `delete_file`).

2. **Register in the factory** — `contract_sentinel/factory.py`
   Add a `case "provider":` branch to `get_store()` following the same pattern as `"s3"`
   (lazy import, `MissingDependencyError` on `ImportError`). The store name string must also
   be documented as the valid value for the `SENTINEL_STORE` env var.

3. **Add to `pyproject.toml`** — add the provider SDK to `[project.optional-dependencies]`
   and to the `all` group.

4. **Write integration tests** — `tests/integration/test_adapters/test_<provider>_store.py`
   Test all five methods against a real or emulated endpoint (e.g. LocalStack for AWS-compatible
   stores). Follow the pattern in `tests/integration/test_adapters/test_s3_contract_store.py`.

5. **Checklist** — a checkbox list mirroring the four steps above, plus `just check` passes.

**Done when:**
- [ ] `contributors/contributing.md` exists and contains the local setup sequence, full `just` table, PR workflow, and pointers to the three how-to guides
- [ ] `contributors/how-to-add-a-rule.md` exists with the full content of the original `docs/how-to-add-a-rule.md`
- [ ] `docs/how-to-add-a-rule.md` is deleted
- [ ] `contributors/how-to-add-a-parser.md` exists and covers all five steps with a skeleton class and a checklist
- [ ] `contributors/how-to-add-a-contract-store.md` exists and covers all four steps with method signatures and a checklist
- [ ] No broken internal links (the README Contributing pointer and any cross-references between guides resolve correctly)
