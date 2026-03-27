# Fix Suggestions — Dev Tickets

**Feature slug:** `003-fix-suggestions`
**Spec:** `docs/features/003-fix-suggestions/product_spec.md`
**Design:** `docs/features/003-fix-suggestions/design.md`
**Created:** 2026-03-27

---

## Architecture Notes

### No New Adapters, No New Services

This feature is entirely additive and touches only two layers:

- **Domain** — one new pure module `domain/fix_suggestions.py`. Zero I/O. Takes `PairViolations`
  (already a domain type) and returns `PairFixSuggestion` (a new plain dataclass). No changes to
  existing domain files.
- **CLI** — `cli/validate.py` gains a `--how-to-fix` flag on both commands and a new standalone
  renderer `print_fix_suggestions`. `print_report` is not modified.

### Data Flow

```
[CLI] validate-local-contracts --how-to-fix
  │
  ├── service: validate_local_contracts(store, parser, loader, config)
  │     └── returns ContractsValidationReport (unchanged)
  ├── print_report(report, verbose=verbose)             ← unchanged
  └── print_fix_suggestions(report, local_name=config.name)
        └── for each failing PairViolations:
              ├── infer local side per pair:
              │     producer_id.startswith(config.name+"/") → local is PRODUCER
              │     consumer_id.startswith(config.name+"/") → local is CONSUMER
              └── suggest_fixes(pair) → PairFixSuggestion | None
                    └── render with per-pair contextual labels

[CLI] validate-published-contracts --how-to-fix
  └── print_fix_suggestions(report, local_name=None)   ← symmetrical labels
```

### New Files

```
contract_sentinel/
└── domain/
    └── fix_suggestions.py    ← PairFixSuggestion, suggest_fixes, _instruction_for, _build_block

tests/
└── unit/
    └── test_domain/
        └── test_fix_suggestions.py
```

### Modified Files

```
contract_sentinel/cli/validate.py   ← --how-to-fix flag (both commands), print_fix_suggestions,
                                       loader-once pattern for local_role extraction
```

### Key Implementation Notes

- `suggest_fixes` filters to CRITICAL violations only before building instructions. Returns `None`
  when the filtered list is empty — caller skips rendering.
- `_instruction_for(violation)` matches on `violation.rule` and returns
  `tuple[str, str] | None` — `(producer_instruction, consumer_instruction)`. Returns `None`
  for `COUNTERPART_MISMATCH` (WARNING, not a schema change); the caller filters `None` out.
- `_build_block` extracts the bare class name from `schema_id` via `rsplit("/", 1)[1]`.
- `METADATA_KEY_MISMATCH`: extract the metadata key name via `next(iter(violation.consumer))`.
- `METADATA_ALLOWED_VALUES_MISMATCH` — unconstrained producer case: when
  `violation.producer == {"allowed_values": None}`, the producer instruction reads
  `"Add an allowed-values constraint to field '{path}' whose values are a subset of {c.allowed_values}."`
- `print_fix_suggestions` infers the local side **per pair** using `config.name`, not a global
  role — this correctly handles repos that contain both a producer and a consumer schema
  (e.g. a middleware service). A single global `local_role` would produce wrong labels for
  one of the two schemas in that scenario.
- No IAM, no env vars, no LocalStack — this feature has no infrastructure requirements.

---

## Tickets

### TICKET-01 — Domain: `PairFixSuggestion` dataclass and `suggest_fixes`

**Depends on:** —
**Type:** Domain

**Goal:**
Implement the pure domain module that maps a `PairViolations` into two consolidated fix
prompt blocks — one for the producer side and one for the consumer side.

**Files to create / modify:**
- `contract_sentinel/domain/fix_suggestions.py` — create
- `tests/unit/test_domain/test_fix_suggestions.py` — create

**Done when:**
- [ ] `PairFixSuggestion` dataclass exists with `producer_fix: str` and `consumer_fix: str` fields.
- [ ] `suggest_fixes(pair)` returns `None` when the pair contains no CRITICAL violations.
- [ ] `suggest_fixes(pair)` returns a `PairFixSuggestion` with non-empty `producer_fix` and
      `consumer_fix` when the pair contains at least one CRITICAL violation.
- [ ] For each of the eleven rules — `TYPE_MISMATCH`, `REQUIREMENT_MISMATCH`,
      `NULLABILITY_MISMATCH`, `MISSING_FIELD`, `UNDECLARED_FIELD`, `DIRECTION_MISMATCH`,
      `STRUCTURE_MISMATCH`, `METADATA_ALLOWED_VALUES_MISMATCH`, `METADATA_RANGE_MISMATCH`,
      `METADATA_LENGTH_MISMATCH`, `METADATA_KEY_MISMATCH` — a unit test asserts the producer
      instruction text and the consumer instruction text match the mapping table in `design.md`.
- [ ] A unit test with two violations in one pair asserts the consolidated block contains a
      numbered list (`1.`, `2.`) and the correct header naming both the schema class and the
      counterpart (e.g. `"In \`OrderSchema\`, make the following changes to satisfy the contract
      with B/OrderConsumer:"`).
- [ ] `domain/fix_suggestions.py` imports nothing from `cli/`, `adapters/`, or any I/O library.
- [ ] `just check` passes.

---

### TICKET-02 — CLI: `print_fix_suggestions` renderer and `--how-to-fix` on `validate-local-contracts`

**Depends on:** TICKET-01
**Type:** CLI

**Goal:**
Add `--how-to-fix` to `sentinel validate-local-contracts` and implement the standalone
`print_fix_suggestions` renderer with contextual "your side / their side" labelling.

**Files to create / modify:**
- `contract_sentinel/cli/validate.py` — modify

**Done when:**
- [ ] `--how-to-fix` flag exists on `sentinel validate-local-contracts` and defaults to `False`.
- [ ] `print_fix_suggestions(report, *, local_name: str | None)` is a standalone function,
      separate from `print_report`. `print_report` signature is unchanged.
- [ ] When `--how-to-fix` is passed, `print_fix_suggestions(report, local_name=config.name)`
      is called after `print_report`.
- [ ] Output mirrors the structure of `print_report`: a `"Fix Suggestions"` top-level header,
      then topic lines, then pair headers at the same indentation as `print_report`, then fix
      blocks indented one level further underneath each pair.
- [ ] For each failing pair, the local side is inferred dynamically: if `pair.producer_id`
      starts with `local_name + "/"` the producer block is labelled `"Fix on your side
      (Producer) — copy & paste to your agent:"` and the consumer block `"Fix on their side
      (Consumer) — copy & paste to your agent:"`; if `pair.consumer_id` starts with
      `local_name + "/"` the labels swap.
- [ ] A repo containing both a producer and a consumer schema produces correct "your side"
      labels for each pair independently — not a single global role applied to all pairs.
- [ ] Blocks are printed only for pairs that have CRITICAL violations; passing pairs produce
      no output.
- [ ] Running `sentinel validate-local-contracts` without `--how-to-fix` produces output
      identical to before — `print_fix_suggestions` is not called.
- [ ] `just check` passes.

---

### TICKET-03 — CLI: `--how-to-fix` on `validate-published-contracts`

**Depends on:** TICKET-02
**Type:** CLI

**Goal:**
Wire the existing `print_fix_suggestions` renderer to `sentinel validate-published-contracts`
with symmetrical "Producer / Consumer" labelling.

**Files to create / modify:**
- `contract_sentinel/cli/validate.py` — modify

**Done when:**
- [ ] `--how-to-fix` flag exists on `sentinel validate-published-contracts` and defaults to `False`.
- [ ] When `--how-to-fix` is passed, `print_fix_suggestions(report, local_name=None)` is called
      after `print_report`.
- [ ] With `local_name=None`, blocks are labelled `"Fix on Producer side — copy & paste to
      your agent:"` and `"Fix on Consumer side — copy & paste to your agent:"` — no "your
      side" language.
- [ ] Output mirrors `print_report` structure: `"Fix Suggestions"` header, topic lines, pair
      headers, fix blocks indented underneath.
- [ ] Running `sentinel validate-published-contracts` without `--how-to-fix` produces output
      identical to before.
- [ ] `just check` passes.
