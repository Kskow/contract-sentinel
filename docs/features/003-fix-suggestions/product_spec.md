# Product Spec — Fix Suggestions

**Feature slug:** `003-fix-suggestions`
**Status:** `ready-for-dev`
**Created:** 2026-03-27

---

## Problem

When `sentinel validate` or `sentinel validate-published-contracts` reports a CRITICAL violation,
the developer knows *what* broke but not *what to do*. They must manually read each violation,
reason about which side needs to change, and write out an instruction for themselves or their team.

In agentic workflows (Cursor, Claude Code, Copilot) this manual step is a bottleneck — the dev
needs a ready-made, copy-paste prompt they can hand directly to the agent, rather than
translating a diagnostic message into an imperative instruction themselves.

---

## Goals

- For every CRITICAL violation in a producer/consumer pair, generate two actionable fix messages:
  one telling the **producer side** what to change, one telling the **consumer side** what to change.
- Group all per-pair fix instructions into a single consolidated prompt block per side, so the
  developer can copy-paste one message per side to their agent without any editing.
- Expose fix suggestions via a `--how-to-fix` flag on both `sentinel validate-local-contracts` and
  `sentinel validate-published-contracts` — opt-in, not shown by default.
- On `sentinel validate` (local), label the blocks contextually: **"Fix on your side"** for the
  local schema's role and **"Fix on their side (alternative)"** for the counterpart.
- On `sentinel validate-published-contracts` (store), label the blocks symmetrically:
  **"Fix on Producer side"** and **"Fix on Consumer side"** — no local bias.
- All fix instruction generation lives in `domain/fix_suggestions.py` as pure transformation
  logic — no I/O, no CLI imports — so it is reusable and independently testable.

---

## Out of Scope
- `COUNTERPART_MISMATCH` fix instructions — this is a WARNING-severity workflow issue
  ("publish a producer"), not a schema field change.
- Framework-specific fix phrasing (e.g. `fields.Integer()` instead of `integer`) — deferred;
  framework info is not carried in `Violation` objects and adding it is a separate concern.
- JSON / machine-readable output of fix suggestions — deferred; CLI text output is sufficient
  for V1.
- Conflict detection across multiple consumers — if Consumer B and Consumer C demand
  incompatible changes from the same producer field, the messages will naturally contradict each
  other; surfacing this programmatically is deferred.

---

## Acceptance Criteria

1. `sentinel validate-local-contracts --how-to-fix` prints a **"Fix on your side"** and a
   **"Fix on their side (alternative)"** consolidated prompt block for every failing
   producer/consumer pair on the topic; blocks are omitted for passing pairs.

2. `sentinel validate-published-contracts --how-to-fix` prints a **"Fix on Producer side"** and a
   **"Fix on Consumer side"** consolidated prompt block for every failing pair.

3. Running either command **without** `--how-to-fix` produces identical output to today — no
   suggestions are shown.

4. Each consolidated prompt block is a self-contained, imperative message that names the schema
   class, lists every CRITICAL fix as a numbered instruction, and names the counterpart it
   satisfies. Example:

   ```
   In `OrderSchema`, make the following changes to satisfy the contract with B/OrderConsumer:

   1. Change the type of field `amount` from `string` to `integer`.
   2. Add `created_at` as a required field.
   ```

5. Fix instructions are generated for all eleven CRITICAL field-level rules: `TYPE_MISMATCH`,
   `REQUIREMENT_MISMATCH`, `NULLABILITY_MISMATCH`, `MISSING_FIELD`, `UNDECLARED_FIELD`,
   `DIRECTION_MISMATCH`, `STRUCTURE_MISMATCH`, `METADATA_ALLOWED_VALUES_MISMATCH`,
   `METADATA_RANGE_MISMATCH`, `METADATA_LENGTH_MISMATCH`, and `METADATA_KEY_MISMATCH`.

6. `domain/fix_suggestions.py` contains no imports from `cli/`, `adapters/`, or any I/O library.
   It accepts only domain types (`Violation`, `PairViolations`) and returns plain strings or
   dataclasses of plain strings.

7. Unit tests in `tests/unit/test_domain/` cover:
   - For each supported rule: the producer-side fix instruction text and the consumer-side fix
     instruction text are correct for a single violation.
   - The consolidated block correctly assembles a multi-violation pair into a numbered list
     under the right header.
