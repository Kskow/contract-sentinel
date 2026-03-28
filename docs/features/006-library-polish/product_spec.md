# Product Spec — Library Polish & PyPI Release

**Feature slug:** `006-library-polish`
**Status:** `ready-for-dev`
**Created:** 2026-03-28

---

## Problem

Contract Sentinel is functional but invisible. It lives as a private repo with no discoverable package on PyPI, a README written for contributors rather than users, and no contributor guides beyond the rule how-to. Anyone evaluating the tool has to read source code to understand how to install it, mark schemas, or plug in a custom store.

---

## Goals

- A developer can `pip install contract-sentinel` from PyPI and be running within 5 minutes. ✅
- The README answers the three questions every new user asks: "What is it?", "How do I install it?", "How do I wire it into CI?". ✅
- Cutting a release is a single `git tag v0.x.y && git push --tags` — no manual PyPI interaction required. ✅
- Contributors have self-contained guides for adding rules, parsers, and stores. ✅

---

## Non-Goals (V1)

- Changelog automation or semantic-release tooling.
- A documentation site (Sphinx, MkDocs). Plain Markdown in `contributors/` is enough.
- Expanding the public Python API surface (`__init__.py` stays as-is: `contract`, `Role`, `__version__`).
- Publishing to TestPyPI — the quality CI gate already covers correctness.

---

## User-Facing Changes

| Audience | Change |
|---|---|
| Library users | Package installable via `pip install contract-sentinel` |
| Library users | README explains installation, marking schemas, and CI integration |
| Contributors | `contributors/` directory with onboarding guides |
| Maintainer | `git tag v0.0.1 && git push --tags` triggers automated PyPI publish |

---

## Acceptance Criteria

- [ ] `pyproject.toml` includes `readme`, `license`, `authors`, `keywords`, `classifiers`, and `[project.urls]`; `version` is `0.0.1` (aligned with `__init__.py`).
- [ ] `LICENSE` file (MIT, 2026, Kskow) exists at the repository root.
- [ ] `.github/workflows/publish.yml` triggers on `v*` tag push, builds with `uv build`, and publishes with `uv publish --trusted-publishing always`.
- [ ] README leads with badges (PyPI, Python, License, CI), explains what the library does, what's supported and what's on the roadmap, and shows a working GitHub Actions integration snippet.
- [ ] `contributors/contributing.md` covers local dev setup (Docker, `just` commands, PR workflow).
- [ ] `contributors/how-to-add-a-rule.md` exists (moved from `docs/how-to-add-a-rule.md`; `docs/` copy deleted).
- [ ] `contributors/how-to-add-a-parser.md` and `contributors/how-to-add-a-contract-store.md` exist.
- [ ] `just check` passes unchanged — no production or test code is modified.
