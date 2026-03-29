# TICKET — CLI: `--markdown` output flag on both validate commands

**Created:** 2026-03-29

---

## Context

`print_validation_report` uses `typer.style()` for ANSI colouring (red header and contract lines
on failure). ANSI escape codes render as garbage inside GitHub/GitLab/Bitbucket PR comments.

The `--markdown` flag switches both renderers to plain-text output wrapped in fenced code blocks,
making the report paste-ready as a PR comment. The user captures stdout and posts it via their
platform's native comment action — Contract Sentinel stays platform-agnostic.

When `--markdown` is combined with `--how-to-fix`, the fix suggestions appear in a second fenced
code block immediately after the first.

---

## TICKET-01 — CLI: `--markdown` flag on both validate commands

**Depends on:** —
**Type:** CLI

**Goal:**
Add `--markdown` to `validate-local-contracts` and `validate-published-contracts` so the report
is emitted as plain text inside fenced code blocks, with no ANSI escape codes.

**Files to modify:**
- `contract_sentinel/cli/validate.py`

**Implementation notes:**
- `print_validation_report` and `print_fix_suggestions_report` each gain a `markdown: bool = False`
  keyword argument.
- When `markdown=True`, collect output lines into a `list[str]` instead of calling `typer.echo()`
  directly, then print the whole block fenced with ` ``` `.
- Skip all `typer.style()` calls when `markdown=True` — emit the plain string instead.
- When both `--markdown` and `--how-to-fix` are active, each renderer emits its own fenced block;
  they are separated by a blank line.
- When `--markdown` is omitted, behaviour is identical to today — no existing output changes.

**Done when:**
- [ ] `--markdown` flag exists on `validate-local-contracts`, defaults to `False`.
- [ ] `--markdown` flag exists on `validate-published-contracts`, defaults to `False`.
- [ ] `print_validation_report` accepts `markdown: bool = False`; the existing `verbose` call-sites
      are unchanged.
- [ ] `print_fix_suggestions_report` accepts `markdown: bool = False`; the existing `local_name`
      call-sites are unchanged.
- [ ] With `--markdown`, the full validation report is enclosed in a single fenced code block
      (` ```\n<content>\n``` `).
- [ ] With `--markdown`, no ANSI escape codes appear anywhere in stdout.
- [ ] With `--markdown --how-to-fix`, fix suggestions appear in a second fenced code block,
      separated from the first by a blank line.
- [ ] Without `--markdown`, stdout is byte-for-byte identical to the current output.
- [ ] `just check` passes.
